from app import s3, s3_client, config, db
from app.models import File
from botocore.exceptions import ClientError
import random
import hashlib
import magic
import mimetypes
import base64
import os
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
    
def create_db_entry(s3_path, ip, date, filename, user, mgmt, size, mime, sha256, deleted):
    """
    Create a new file entry in the db.
    Returns True if successful, False otherwise and prints log.
    """
    try:
        new_file = File(s3_path=s3_path, ip=ip, date=date, filename=filename, user=user, mgmt=mgmt, size=size, mime=mime, sha256=sha256, deleted=deleted)
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

    if file.filename.find('.') != -1:
        ext = file.filename.split('.')[-1]
    else:
        ext = ext_list[0]
    
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

def name_randomiser():
    """Create a random name for a file.

    Returns:
        str: Random filename.
    """
    return ''.join(random.choices('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789', k=4))