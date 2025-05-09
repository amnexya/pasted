from app import s3_client, config, db
from app.models import File, Quote
from botocore.exceptions import ClientError
import random
import hashlib
import magic
import mimetypes
import base64
import os
import bcrypt
from werkzeug.datastructures import FileStorage
import requests
import io

def upload_s3(file, filename, mime):
    """
    Upload a file to s3.
    Returns True if successful, False otherwise and prints log.
    """

    # Get file hash
    file_hash = sha256gen(file)
    print(file_hash)

    try:
        response = s3_client.put_object(Body=file, Bucket="pasted", Key=filename, ChecksumSHA256=file_hash, ContentType=mime, ContentDisposition=f"attachment; filename={filename}")
        print(response)
        return True
    except ClientError as e:
        print(e)
        return False 
    
def create_db_entry(s3_path, ip, date, filename, mgmt, size, mime, sha256, private, deleted):
    """
    Create a new file entry in the db.
    Returns True if successful, False otherwise and prints log.
    """
    try:
        new_file = File(s3_path=s3_path, ip=ip, date=date, filename=filename, mgmt=mgmt, size=size, mime=mime, sha256=sha256, private=private, deleted=deleted)
        db.session.add(new_file)
        db.session.commit()
        return True
    except Exception as e:
        print(e)
        return False
    
def determine_mime_and_ext(file):
    """Determine the MIME type and extension of a file.

    Args:
        file (FileStorage): File to determine MIME type and extension of.

    Returns:
        str: MIME type of the file.
        str: Extension of the file.
    """

    # Get MIME
    mime = magic.Magic(mime=True).from_buffer(file.read())

    # Set pointer back to 0
    file.seek(0)

    # Get Extension
    ext_list = mimetypes.guess_all_extensions(mime)
    file.seek(0)

    try:
        if file.filename.find('.') != -1:
            ext = file.filename.split('.')[-1]
        else:
            ext = ext_list[0]
    except IndexError:
        # Been a bug where if the file doesnt have an extension, it will use the file name as it, cant have that.
        # Assuming its just returning a list with one value, so im just gonna set the extension to bin to play it safe.
        ext = 'bin'

    return mime, ext

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

def get_file_from_s3(s3_path, mime):
    try:
        # Fetch the file using requests
        file = requests.get(config['endpoint'] + "/" + s3_path)

        # Extract the file content, filename, and content type
        file_content = file.content
        content_type = file.headers.get('Content-Type', 'application/octet-stream')
        file_name = s3_path.split('/')[-1]  # Extract filename from the path

        # Create a file-like object
        file_like = io.BytesIO(file_content)

        # Wrap it in a FileStorage object
        file_storage = FileStorage(
            stream=file_like,
            filename=file_name,
            content_type=content_type
        )

        return file_storage
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
        return quote.quote, quote.author
    except ValueError:
        return "the quotes broke, i need to fix that!", "amnexya"
    
def generate_recent_pastes():
    try:
        # Query the db and get, lets say past 16 files uploaded, we need to check if the privacy shows listable.
        files = db.session.query(File).filter_by(deleted=False).order_by(File.date.desc()).limit(16).all()
        print(files)
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