from app import db

class File(db.Model):
    __tablename__ = 'files'

    id = db.Column(db.Integer, primary_key=True)
    s3_path = db.Column(db.String(256), nullable=False)
    ip = db.Column(db.String(15), nullable=False)
    date = db.Column(db.DateTime, nullable=False)
    filename = db.Column(db.String(256), nullable=False)
    mgmt = db.Column(db.String(64), nullable=False)
    size = db.Column(db.Integer, nullable=False)
    mime = db.Column(db.String(256), nullable=False)
    sha256 = db.Column(db.String(64), nullable=False)
    deleted = db.Column(db.Boolean, nullable=False)

    def __repr__(self):
        return f"<File {self.id}>"