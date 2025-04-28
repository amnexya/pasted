from app import db

class File(db.Model):
    __tablename__ = 'files'

    id = db.Column(db.Integer, primary_key=True) # Auto-incrementing ID
    s3_path = db.Column(db.String(256), nullable=False) # Path to the file in S3
    ip = db.Column(db.String(15), nullable=True) # IP address of the user who uploaded the file
    date = db.Column(db.DateTime, nullable=False) # Date and time of upload
    filename = db.Column(db.String(256), nullable=False) # Filename
    mgmt = db.Column(db.String(64), nullable=False) # Management ID, stored hashed
    size = db.Column(db.Integer, nullable=False) # Size of the file in bytes
    mime = db.Column(db.String(256), nullable=False) # MIME type of the file
    sha256 = db.Column(db.String(64), nullable=False) # SHA256 hash of the file
    private = db.Column(db.Boolean, nullable=False) # Allow the file to be listed in the recent list or not
    deleted = db.Column(db.Boolean, nullable=False) # Soft delete flag

    def __repr__(self):
        return f"<File {self.id}>"
    
class Quote(db.Model):
    __tablename__ = 'quotes'

    id = db.Column(db.Integer, primary_key=True) # Auto-incrementing ID
    quote = db.Column(db.String(256), nullable=False) # Quote text
    author = db.Column(db.String(64), nullable=False) # Author of the quote

    def __repr__(self):
        return f"<Quote {self.id}>"