#!/usr/bin/env python3
"""One-off: convert files from the old single-Fernet-token format to the
chunked format in app/storage.py, and fix up their stored SHA256 (old
rows hashed the ciphertext, so their hashes are wrong anyway).

Run with pasted stopped, or at least quiet:   ./migrate_storage.py [--dry-run]
Safe to re-run; files already converted are skipped.
"""
import io
import os
import sys

from app import app, db, storage
from app.models import File


def main():
    dry_run = "--dry-run" in sys.argv
    app.app_context().push()
    data_dir = app.config["LOCAL_DATA"]

    done = skipped = failed = 0
    for row in File.query.all():
        path = os.path.join(data_dir, row.filename)
        if not os.path.isfile(path):
            print(f"missing  {row.filename} (cleanup.py will deal with it)")
            continue
        if not storage.is_legacy(path):
            skipped += 1
            continue
        try:
            plaintext = storage.legacy_plaintext(path)  # one file in memory at a time
        except Exception as e:
            print(f"FAILED   {row.filename}: can't decrypt ({type(e).__name__})")
            failed += 1
            continue

        print(f"convert  {row.filename} ({len(plaintext)} bytes)")
        if dry_run:
            continue
        size, sha256 = storage.write_file(io.BytesIO(plaintext), path)  # atomic replace
        row.size, row.sha256 = size, sha256
        db.session.commit()
        done += 1

    print(f"\nconverted {done}, already new format {skipped}, failed {failed}")


if __name__ == "__main__":
    main()
