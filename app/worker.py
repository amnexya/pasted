import base64
import datetime
import hashlib
import io
import mimetypes
import os
import random
import re

import bcrypt
import magic

from app import MARKDOWN_PATTERNS, SAFE_MIME, db, app
from app.models import File, Quote, Announcement, BanList


def save_file(file, filename):
    """Save a file to the local mount directory.

    Args:
        file (BytesIO or FileStorage): File to save.
        filename (str): Name to save the file as.
    """
    # Are we working with BytesIO or FileStorage?
    if isinstance(file, io.BytesIO):
        with open(os.path.join(app.config["LOCAL_DATA"], filename), "wb") as f:
            f.write(file.getbuffer())
    else:
        file.save(os.path.join(app.config["LOCAL_DATA"], filename))


def create_db_entry(ip, date, filename, mgmt, size, mime, sha256, private, deleted):
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
            private=private, # type: ignore
            deleted=deleted # type: ignore
        )
        db.session.add(new_file)
        db.session.commit()
        return True
    except Exception as e:
        db.session.rollback()
        print(e)
        return False


def create_mgmt_token():
    """Create a random management token for a file.

    Returns:
        str: Management token for the user.
    """
    return base64.b64encode(os.urandom(32)).decode("utf-8")


def sha256gen(file):
    # Get file hash
    file.seek(0)
    file_hash = hashlib.sha256(file.read()).hexdigest()
    file.seek(0)

    return file_hash


def generate_hash(str_hash):
    return bcrypt.hashpw(str_hash.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def check_hash(str_hash, hashed):
    return bcrypt.checkpw(str_hash.encode("utf-8"), hashed.encode("utf-8"))


def name_randomiser():
    """Create a random name for a file.

    Returns:
        str: Random filename.
    """
    return "".join(
        random.choices("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789", k=4)
    )


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


def is_markdown(filename, content):
    if filename.endswith(".md"):
        return True

    sample = content[:10000]
    matches = 0
    for pattern in MARKDOWN_PATTERNS:
        if re.search(pattern, content, re.MULTILINE):
            matches += 1
        if matches >= 2:  # if theres 2 matches, its probably markdown
            return True

    return False


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
        print("Banned successfully")
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

