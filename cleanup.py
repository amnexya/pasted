#!/usr/bin/env python3
import os, sys, time
from app import app, db, die, warn
from app.models import File

GRACE_SECONDS = 600     # skip anything newer than this, it may be mid-upload
MAX_FRACTION = 0.05     # abort if we'd remove more than this fraction of files/rows
MIN_ALLOWED = 5         # always allow a handful, so tiny sites arent stuck

def main():
    dry_run = "--dry-run" in sys.argv
    force = "--force" in sys.argv
    app.app_context().push()
    data_dir = app.config["LOCAL_DATA"]

    in_db = {f.filename for f in File.query.all()}
    local = {f for f in os.listdir(data_dir) if os.path.isfile(os.path.join(data_dir, f)) and not f.startswith(".")}

    if force:
        warn("Running with --force ignores all warnings, and can result in your DB or storage directory being fully wiped. Do you still want to run? (y/N)\n")
        while True:
            c = input()
            if c.lower() == "y":
                break
            elif c.lower() == "n":
                sys.exit()
            else:
                print("Unknown value, please answer with 'y' or 'n'.")

    if in_db and not local and not force and not dry_run:
        die(f"{data_dir} is empty but the DB has {len(in_db)} files - is the storage mounted? Aborting. Run with --force to ignore this warning.\n")
    if local and not in_db and not force and not dry_run:
        die(f"DB is empty but {data_dir} has {len(local)} files - not continuing out of caution. Run with --force to ignore this warning.\n")

    now = time.time()

    # files on disk with no DB entry
    orphan_files = []
    for f in sorted(local - in_db):
        try:
            age = now - os.path.getmtime(os.path.join(data_dir, f))
        except FileNotFoundError:           # vanished since we listed it
            continue
        if age >= GRACE_SECONDS:            # young ones are probably mid-upload
            orphan_files.append(f)

    # DB entries with no file on disk
    orphan_rows = []
    for f in sorted(in_db - local):
        row = db.session.query(File).filter_by(filename=f).first()      # get db row
        if row is None:                                                 # deleted by someone else since we listed
            continue
        if now - row.date.timestamp() >= GRACE_SECONDS:                 # datetime -> number so it can be compared
            orphan_rows.append(row)                                     # young ones were probably only just uploaded

    # one check, before anything gets removed, against the totals
    if not force and not dry_run:
        if len(orphan_files) > max(MIN_ALLOWED, len(local) * MAX_FRACTION):
            die(f"Would remove {len(orphan_files)} of {len(local)} files (more than {MAX_FRACTION:.0%}). Not continuing. Run with --force to ignore this warning.\n")
        if len(orphan_rows) > max(MIN_ALLOWED, len(in_db) * MAX_FRACTION):
            die(f"Would remove {len(orphan_rows)} of {len(in_db)} DB rows (more than {MAX_FRACTION:.0%}). Not continuing. Run with --force to ignore this warning.\n")

    for f in orphan_files:
        if dry_run:
            print(f"Would remove orphan file {f}")
            continue
        print(f"Removing orphan file {f}")
        try:
            os.remove(os.path.join(data_dir, f))
        except FileNotFoundError:           # already gone, which is what we wanted anyway
            pass

    for row in orphan_rows:
        if dry_run:
            print(f"Would remove orphan DB entry {row.filename}")
            continue
        print(f"Removing orphan DB entry {row.filename}")
        db.session.delete(row)

    if not dry_run:
        db.session.commit()

    print(f"{'Dry run: ' if dry_run else ''}{len(orphan_files)} orphan files, {len(orphan_rows)} orphan DB entries.")

if __name__ == "__main__":
    main()