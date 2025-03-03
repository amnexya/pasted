from app import db

class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(32), nullable=False)
    pass_hash = db.Column(db.String(128), nullable=False)
    admin = db.Column(db.Boolean, nullable=False)
    premium = db.Column(db.Boolean, nullable=False)
    banned = db.Column(db.Boolean, nullable=False)
    ban_end = db.Column(db.DateTime, nullable=True)
    files = db.relationship('File', backref='user', lazy=True)

    def __repr__(self):
        return f"<User {self.id}>"
class File(db.Model):
    __tablename__ = 'files'

    id = db.Column(db.Integer, primary_key=True)
    s3_path = db.Column(db.String(256), nullable=False)
    ip = db.Column(db.String(15), nullable=False)
    date = db.Column(db.DateTime, nullable=False)
    filename = db.Column(db.String(256), nullable=False)
    user = db.Column(db.String(256), nullable=True)
    mgmt = db.Column(db.String(64), nullable=False)
    size = db.Column(db.Integer, nullable=False)
    mime = db.Column(db.String(256), nullable=False)
    sha256 = db.Column(db.String(64), nullable=False)
    deleted = db.Column(db.Boolean, nullable=False)

    def __repr__(self):
        return f"<File {self.id}>"