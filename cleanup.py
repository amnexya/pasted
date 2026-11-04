#!/usr/bin/env python3
import os, sys, time
from app import app, db, die
from app.models import File

GRACE_SECONDS = 600  # skip files newer than this, they may be mid-upload

def main():
    dry_run = "--dry-run" in sys.argv
    app.app_context().push()
    data_dir = app.config["LOCAL_DATA"]
    local = {f for f in os.listdir(data_dir) if os.path.isfile(os.path.join(data_dir, f))}
    in_db = {f.filename for f in File.query.all()}

    if in_db and not local:
        die(f"{data_dir} is empty but the DB has {len(in_db)} files - is the storage mounted? Aborting.")

    for f in sorted(local - in_db):
        path = os.path.join(data_dir, f)
        if time.time() - os.path.getmtime(path) < GRACE_SECONDS:
            continue
        print(f"Removing orphan file {f}")
        if not dry_run:
            os.remove(path)

    for f in sorted(in_db - local):
        print(f"Removing orphan DB entry {f}")
        if not dry_run:
            db.session.query(File).filter_by(filename=f).delete()
    if not dry_run:
        db.session.commit()

if __name__ == "__main__":
    main()