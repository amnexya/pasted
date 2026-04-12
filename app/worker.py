from app import config, db, MARKDOWN_PATTERNS
from app.models import File, Quote
import random
import hashlib
import magic
import mimetypes
import base64
import os
import bcrypt
import io
import re
    
def save_file(file, filename):
    """Save a file to the local mount directory.

    Args:
        file (BytesIO or FileStorage): File to save.
        filename (str): Name to save the file as.
    """
    # Are we working with BytesIO or FileStorage?
    if isinstance(file, io.BytesIO):
        with open(os.path.join(config['local_data'], filename), 'wb') as f:
            f.write(file.getbuffer())
    else:
        file.save(os.path.join(config['local_data'], filename))

def upload_file(file, filename, mime):
    """Take user uploaded file and place it in local mount directory

    Args:
        file (_type_): _description_
        filename (_type_): _description_
        mime (_type_): _description_
    """
def create_db_entry(ip, date, filename, mgmt, size, mime, sha256, private, deleted):
    """
    Create a new file entry in the db.
    Returns True if successful, False otherwise and prints log.
    """
    try:
        new_file = File(ip=ip, date=date, filename=filename, mgmt=mgmt, size=size, mime=mime, sha256=sha256, private=private, deleted=deleted) # type: ignore
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
    return base64.b64encode(os.urandom(32)).decode('utf-8')
    
def sha256gen(file):
    # Get file hash
    file.seek(0)
    file_hash = hashlib.sha256(file.read()).hexdigest()
    file.seek(0)

    return file_hash

def get_file_from_storage(filename, mime):
    try:
        with open(os.path.join(config['local_mount'], filename), 'rb') as f:
            data = io.BytesIO(f.read())
            data.seek(0)
            return data
    except Exception as e:
        print(e)
        return None
    
def generate_hash(str_hash):
    return bcrypt.hashpw(str_hash.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def check_hash(str_hash, hashed):
    return bcrypt.checkpw(str_hash.encode('utf-8'), hashed.encode('utf-8'))

def name_randomiser():
    """Create a random name for a file.

    Returns:
        str: Random filename.
    """
    return ''.join(random.choices('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789', k=4))

def get_quote_from_db():
    try:
        quote = db.session.query(Quote).filter_by(id=random.randint(1, db.session.query(Quote).count())).first()
        return quote.quote, quote.author # type: ignore
    except ValueError:
        return "the quotes broke, i need to fix that!", "amnexya"
    
def generate_recent_pastes():
    try:
        # Query the db and get, lets say past 16 files uploaded, we need to check if the privacy shows listable.
        files = db.session.query(File).filter_by(deleted=False).order_by(File.date.desc()).limit(16).all()
        # Create a list of files
        file_list = []
        for file in files:
            if file.private:
                continue
            file_list.append({
                'filename': file.filename,
                'date': file.date,
                'size': round(file.size / 1024 / 1024, 2) if round(file.size / 1024 / 1024, 2) > 0.0 else round(file.size / 1024, 2),
                'size_unit': 'MB' if round(file.size / 1024 / 1024, 2) > 0.0 else 'KB',
            })
            if file_list.__len__() >= 8:
                break
        # Return the list of files
        return file_list
    except Exception as e:
        print(e)
        return None
    
def is_markdown(filename, content):
    if filename.endswith('.md'):
        return True
    
    matches = 0
    for pattern in MARKDOWN_PATTERNS:
        if re.search(pattern, content, re.MULTILINE):
            matches += 1
        if matches >= 2:  # if theres 2 matches, its probably markdown
            return True
        
    return False