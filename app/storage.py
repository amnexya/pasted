"""Chunked, streaming file encryption for pasted.

On-disk format (v1):

    header  = b"PSTD" | version (1 byte) | salt (16 bytes)          -> 21 bytes
    chunk_i = AES-256-GCM(file_key, nonce_i, plaintext_i, aad=header) -> len(plaintext_i) + 16

* Plaintext is split into 64 KiB chunks. Every chunk is full except the last.
* file_key = HKDF-SHA256(ENC_KEY, salt) so each file gets its own key, and
  counter nonces are therefore safe.
* nonce_i = i (11 bytes, big endian) | final flag (1 byte). The final flag means
  a truncated file fails to decrypt instead of silently coming back shorter
  (the STREAM construction).
* Chunks are fixed size, so a byte range maps straight to chunk indices. That
  gives cheap HTTP Range support (video seeking) without decrypting the whole file.

Files written by the old code are a single Fernet token. They're detected
by the missing magic header and still readable (in memory), so nothing
breaks before you run migrate_storage.py.
"""

import base64
import hashlib
import os

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from app import app

MAGIC = b"PSTD"
VERSION = 1
SALT_LEN = 16
HEADER_LEN = len(MAGIC) + 1 + SALT_LEN
CHUNK = 64 * 1024
TAG = 16
CT_CHUNK = CHUNK + TAG


class StorageError(Exception):
    pass


def _file_key(salt: bytes) -> bytes:
    master = base64.urlsafe_b64decode(app.config["ENC_KEY"])
    return HKDF(algorithm=hashes.SHA256(), length=32, salt=salt, info=b"pasted file v1").derive(master)


def _nonce(index: int, final: bool) -> bytes:
    return index.to_bytes(11, "big") + (b"\x01" if final else b"\x00")


def _read_full(src, n: int) -> bytes:
    """read() can return short reads on some streams, so keep reading until we have n bytes or hit EOF."""
    buf = bytearray()
    while len(buf) < n:
        part = src.read(n - len(buf))
        if not part:
            break
        buf += part
    return bytes(buf)


def encrypt_stream(src, dst):
    """Encrypt everything readable from src into dst, one chunk at a time.

    Returns (plaintext_size, sha256_hexdigest). Peak memory is a couple of chunks
    whatever size the file is.
    """
    salt = os.urandom(SALT_LEN)
    header = MAGIC + bytes([VERSION]) + salt
    aes = AESGCM(_file_key(salt))
    dst.write(header)

    sha = hashlib.sha256()
    size = 0
    index = 0
    chunk = _read_full(src, CHUNK)
    while True:
        # Only a full chunk can have more after it; peek to know if this one is the last.
        nxt = _read_full(src, CHUNK) if len(chunk) == CHUNK else b""
        final = not nxt
        sha.update(chunk)
        size += len(chunk)
        dst.write(aes.encrypt(_nonce(index, final), chunk, header))
        if final:
            return size, sha.hexdigest()
        chunk = nxt
        index += 1


def is_legacy(path: str) -> bool:
    with open(path, "rb") as f:
        return f.read(len(MAGIC)) != MAGIC


def legacy_plaintext(path: str) -> bytes:
    with open(path, "rb") as f:
        return Fernet(app.config["ENC_KEY"]).decrypt(f.read())


def _layout(path: str):
    """Return (n_chunks, plaintext_size) for a v1 file, worked out from its length on disk."""
    ct_len = os.path.getsize(path) - HEADER_LEN
    if ct_len < TAG:
        raise StorageError("file too short")
    n = -(-ct_len // CT_CHUNK)  # ceil
    return n, ct_len - n * TAG


def plaintext_size(path: str) -> int:
    if is_legacy(path):
        return len(legacy_plaintext(path))
    return _layout(path)[1]


def read_range(path: str, start: int = 0, stop: int | None = None):
    """Yield decrypted bytes [start, stop). Only the chunks covering the range are read."""
    if is_legacy(path):
        yield legacy_plaintext(path)[start:stop]
        return

    n, size = _layout(path)
    stop = size if stop is None else min(stop, size)
    if start >= stop:
        return

    with open(path, "rb") as f:
        header = f.read(HEADER_LEN)
        if header[len(MAGIC)] != VERSION:
            raise StorageError(f"unknown storage version {header[len(MAGIC)]}")
        aes = AESGCM(_file_key(header[len(MAGIC) + 1:]))

        first, last = start // CHUNK, (stop - 1) // CHUNK
        f.seek(HEADER_LEN + first * CT_CHUNK)
        for i in range(first, last + 1):
            # raises cryptography.exceptions.InvalidTag if tampered with or truncated
            pt = aes.decrypt(_nonce(i, i == n - 1), f.read(CT_CHUNK), header)
            lo = start - i * CHUNK if i == first else 0
            hi = stop - i * CHUNK if i == last else len(pt)
            yield pt[lo:hi]


def write_file(src, final_path: str):
    """Encrypt src to final_path atomically. A crash mid-upload leaves only a
    .part file (cleanup.py removes it), never a half-written real file.
    Returns (plaintext_size, sha256_hexdigest)."""
    tmp = os.path.join(os.path.dirname(final_path), f".{os.path.basename(final_path)}.part")
    try:
        with open(tmp, "wb") as out:
            result = encrypt_stream(src, out)
            out.flush()
            os.fsync(out.fileno())
        os.replace(tmp, final_path)
        return result
    except BaseException:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise
