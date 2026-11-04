from app import db


class File(db.Model):
    __tablename__ = "files"

    id = db.Column(db.Integer, primary_key=True)  # Auto-incrementing ID
    ip = db.Column(db.String(45), nullable=True)  # IP address of the user who uploaded the file
    date = db.Column(db.DateTime, nullable=False)  # Date and time of upload
    filename = db.Column(db.String(256), nullable=False, unique=True, index=True)  # Filename
    mgmt = db.Column(db.String(64), nullable=False)  # Management ID, stored hashed
    size = db.Column(db.BigInteger, nullable=False)  # Size of the file in bytes
    mime = db.Column(db.String(256), nullable=False)  # MIME type of the file
    sha256 = db.Column(db.String(64), nullable=False)  # SHA256 hash of the file
    private = db.Column(db.Boolean, nullable=False)  # Allow the file to be listed in the recent list or not

    def __repr__(self):
        return f"<File {self.id}>"


class Quote(db.Model):
    __tablename__ = "quotes"

    id = db.Column(db.Integer, primary_key=True)  # Auto-incrementing ID
    quote = db.Column(db.String(256), nullable=False)  # Quote text
    author = db.Column(db.String(64), nullable=False)  # Author of the quote

    def __repr__(self):
        return f"<Quote {self.id}>"

class Announcement(db.Model):
    __tablename__ = "announcements"

    id = db.Column(db.Integer, primary_key=True)  # Auto-incrementing ID
    message = db.Column(db.String(512), nullable=False)  # Announcement message
    date_posted = db.Column(db.DateTime, nullable=False)  # Date and time of posting
    title = db.Column(db.String(256), nullable=False)  # Title of the announcement

    def __repr__(self):
        return f"<Announcement {self.id}>"

class BanList(db.Model):
    __tablename__ = "banlist"

    id = db.Column(db.Integer, primary_key=True)
    ip = db.Column(db.String(45), nullable=False)
    date = db.Column(db.DateTime, nullable=False)
    reason = db.Column(db.String(512), nullable=False)