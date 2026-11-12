import base64
import hashlib
import io
import os
import random
import re
import bcrypt
import datetime
import struct

from app import MARKDOWN_PATTERNS, SAFE_MIME, db, app
from app.models import File, Quote, Announcement, BanList


class sha256gen:
    """Generates sha256 in chunks to save on memory usage."""
    def __init__(self):
        self.hash = hashlib.sha256()
        self.size = 0

    def __call__(self, chunk):
        self.hash.update(chunk)
        self.size += len(chunk)

    def hexdigest(self):
        return self.hash.hexdigest()

def save_file(file, filename):
    """Save a file to the local mount directory.

    Args:
        file (BytesIO or FileStorage): File to save.
        filename (str): Name to save the file as.
    """
    with open(os.path.join(app.config["LOCAL_DATA"], filename), "xb") as f:
        f.write(file.getbuffer())


def create_db_entry(ip, date, filename, mgmt, size, mime, sha256, private):
    """
    Create a new file entry in the db.
    Returns True if successful, False otherwise and prints log.
    """
    try:
        new_file = File(
            ip=ip, # type: ignore
            date=date, # type: ignore
            filename=filename, # type: ignore
            mgmt=mgmt, # type: ignore
            size=size, # type: ignore
            mime=mime, # type: ignore
            sha256=sha256, # type: ignore
            private=private # type: ignore
        )
        db.session.add(new_file)
        db.session.commit()
        return True
    except Exception as e:
        print(e)
        return False


def create_mgmt_token():
    """Create a random management token for a file.

    Returns:
        str: Management token for the user.
    """
    return base64.b64encode(os.urandom(32)).decode("utf-8")


def generate_hash(str_hash):
    return bcrypt.hashpw(str_hash.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def check_hash(str_hash, hashed):
    return bcrypt.checkpw(str_hash.encode("utf-8"), hashed.encode("utf-8"))


def name_randomiser(k=4):
    """Create a random name for a file.

    Returns:
        str: Random filename.
    """
    return "".join(random.choices("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789", k=k))


def get_quote_from_db():
    count = db.session.query(Quote).count()
    if count == 0:
        return "oops! quotes are broken. fixing it soon!", "amnexya"
    quote = db.session.query(Quote).offset(random.randrange(count)).first()
    return quote.quote, quote.author # type: ignore


def get_announcements():
    try:
        announcements = db.session.query(Announcement).order_by(Announcement.date_posted.desc()).limit(5).all()
        return announcements
    except Exception as e:
        print(e)
        return []


def ban_ip(ip, reason):
    """Ban an IP from uploading files.

    Args:
        ip (str): the ip to ban
        reason (str): reason for ban
    """
    try:
        ban = BanList(
            ip=ip, # type: ignore
            reason=reason, # type: ignore
            date=datetime.datetime.now() # type: ignore
        )
        db.session.add(ban)
        db.session.commit()

        print("Banned successfully, removing files.")

        # remove all ip's files
        for file in db.session.query(File).filter_by(ip=ip):
            try:
                os.remove(os.path.join(app.config['LOCAL_DATA'], file.filename))
            except FileNotFoundError:
                pass
            db.session.delete(file)
        db.session.commit()
    except Exception as e:
        print(e)
        print("something went wrong, check above for info")


def is_renderable(mime):
    """This prevents HTML, CSS, and JS from rendering/running under serve_files

    Args:
        mime (str): the mime to check

    Returns:
        str: the mime to swap with, or "download" if the file shouldn't be rendered.
    """
    # Check if it is something we can render as plain text, including svg's with the +xml as they can contain scripts.
    if mime.endswith("+xml") or mime.endswith("/xml") or mime.startswith("text/") or mime in {"application/json", "application/javascript"}:
        return "text/plain"

    # If we have it in safe, return the regular mime
    if mime in SAFE_MIME or mime.startswith(SAFE_MIME):
        return mime

    # Otherwise download it
    return "download"

def is_markdown(filename, content):
    if filename.endswith(".md"):
        return True

    sample = content[:10000]
    matches = 0
    for pattern in MARKDOWN_PATTERNS:
        if re.search(pattern, sample, re.MULTILINE):
            matches += 1
        if matches >= 2:  # if theres 2 matches, its probably markdown
            return True

    return False

def enc_stream(src, dst, fernet, on_chunk=None):
    dst.write(b'PST1')                                  # write file header

    index=0
    while True:
        chunk = src.read(1024*1024)                     # read chunk of file
        if not chunk:                                   # if chunk empty, break
            break

        if on_chunk:
            on_chunk(chunk)

        hdr = struct.pack(                              # chunk header
        ">QB",                                          # big endian, 8 byte unsigned int (index), 1 byte unsigned int (finished)
        index,                                          # index
        0)                                              # sets to 1 when complete
        
        enc_chunk = fernet.encrypt(hdr+chunk)           # encrypt the single chunk, not the whole file

        dst.write(struct.pack(">I", len(enc_chunk)))    # write chunk length (goes before chunk)
        dst.write(enc_chunk)                            # write the chunk
        index += 1

    # If we're here, its hit the end
    hdr = struct.pack(                              # chunk header
    ">QB",                                          # big endian, 8 byte unsigned int (index), 1 byte unsigned int (finished)
    index,                                          # index
    1)                                              # finished

    enc_chunk = fernet.encrypt(hdr+b'')             # encrypt the single chunk, not the whole file

    dst.write(struct.pack(">I", len(enc_chunk)))    # write chunk length (goes before chunk)
    dst.write(enc_chunk)                            # write the chunk

def dec_stream(src, fernet):
    # we check for gAAA outside of this function and seek(0) before calling it
    if src.read(4) != b'PST1':                          # check file header
        raise Exception("File header is not PST1, this is not a chunked file.")

    index = 0
    while True:
        raw_len = src.read(4)                           # read chunk length
        if len(raw_len) < 4:                            # file ended before the finished chunk
            raise Exception("Reached unexpected EOF where there should be a chunk length. File is likely truncated.")

        length = struct.unpack(">I", raw_len)[0]        # bytes -> int
        if length > 2*1024*1024:                        # corrupt length, dont try to read gigabytes
            raise Exception("Chunk length is impossibly large. File is likely corrupted.")

        enc_chunk = src.read(length)                    # get encrypted chunk from that
        if len(enc_chunk) != length:                    # short read, file cut off mid chunk
            raise Exception("Reached unexpected EOF inside a chunk. File is likely truncated.")

        chunk = fernet.decrypt(enc_chunk)               # decrypt chunk, raises InvalidToken if tampered with
        if len(chunk) < 9:                              # cant even hold a header
            raise Exception("Chunk is too short to contain a header. File is likely corrupted.")

        chunk_index, finished = struct.unpack(">QB", chunk[:9])   # split header
        data = chunk[9:]                                # split data

        if chunk_index != index:                        # frames reordered, dropped or duplicated
            raise Exception("Header in chunk index does not match current chunk index. File is likely corrupted.")

        if finished:
            if data != b'':                             # finished chunk should always be empty
                raise Exception("Finished chunk contains data. File is likely corrupted.")
            if src.read(1) != b'':                      # nothing should come after it
                raise Exception("Found extra data after the finished chunk. File is likely corrupted.")
            return                                      # all done

        yield data                                      # hand back just the data, not the header
        index += 1

def shard_path(filename):
    """Avoid the 10,000 files per directory limit pixeldrain has.

    First two characters become nested directories, e.g. hKLz.txt becomes <LOCAL_DATA>/h/K/hKLz.txt
    """
    return os.path.join(app.config['LOCAL_DATA'], filename[0], filename[1], filename)