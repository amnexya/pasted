from app import s3, s3_client, config, db
from app.models import File
from botocore.exceptions import ClientError
import random

def upload_s3(file, filename):
    """
    Upload a file to s3.
    Returns True if successful, False otherwise and prints log.
    """
    try:
        response = s3_client.upload_fileobj(file, "pasted", filename)
        print(response)
        return True
    except ClientError as e:
        print(e)
        return False 
    
def create_db_entry(s3_path, ip, date, filename, user, mgm, size, mime, deleted):
    """
    Create a new file entry in the db.
    Returns True if successful, False otherwise and prints log.
    """
    try:
        new_file = File(s3_path=s3_path, ip=ip, date=date, filename=filename, user=user, mgmt=mgm, size=size, mime=mime, deleted=deleted)
        db.session.add(new_file)
        db.session.commit()
        return True
    except Exception as e:
        print(e)
        return False
    
def name_randomiser():
    """
    Generate a random name for a file.
    """
    return ''.join(random.choices('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789', k=4))