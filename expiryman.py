#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from datetime import datetime, timedelta
from botocore.exceptions import ClientError
import tomllib
import os
import boto3
from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime
from sqlalchemy.orm import sessionmaker, declarative_base

Base = declarative_base()

class File(Base):
    __tablename__ = 'files'

    id = Column(Integer, primary_key=True)
    s3_path = Column(String(256), nullable=False)
    ip = Column(String(15), nullable=True)
    date = Column(DateTime, nullable=False)
    filename = Column(String(256), nullable=False)
    mgmt = Column(String(64), nullable=False)
    size = Column(Integer, nullable=False)
    mime = Column(String(256), nullable=False)
    sha256 = Column(String(64), nullable=False)
    deleted = Column(Boolean, nullable=False)

# Load config
config_location = ["~/.config/pasted.toml", "pasted.toml"]
config = None

for c in config_location:
    try:
        with open(os.path.expanduser(c), "rb") as f:
            config = tomllib.load(f)
            break
    except FileNotFoundError:
        print(f"[WARN] No config file found at {c}, attempting next location...")

if config is None:
    exit("[ERROR] No config file found.")

# Set up the database connection
DATABASE_URI = config["database_uri"]
engine = create_engine(DATABASE_URI)
Session = sessionmaker(bind=engine)
session = Session()

# Set up S3 client
try:
    s3_client = boto3.client(
        's3',
        endpoint_url=config['endpoint'],
        aws_access_key_id=config['access'],
        aws_secret_access_key=config['secret'],
        config=boto3.session.Config(signature_version='s3v4'),
        verify=True
    )
except Exception as e:
    exit(f"[ERROR] S3 client could not be started.\n{e}")

def cleanup():
    """Remove expired files from S3 and mark them as deleted in the database."""
    files = session.query(File).all()
    expiry_days = config['expiry_days']

    for file in files:
        if file.date + timedelta(days=expiry_days) < datetime.now() or file.deleted:
            try:
                s3_client.delete_object(Bucket="pasted", Key=file.filename)
                print(f"[INFO] Deleted {file.filename} from S3.")
            except ClientError as e:
                print(f"[ERROR] Failed to delete {file.filename}: {e}")
                continue

            session.delete(file)
            session.commit()
            print(f"[INFO] Marked {file.filename} as deleted in the database.")

        if file.date + timedelta(days=3) < datetime.now():
            file.ip = None
            session.commit()
            print(f"[INFO] Removed IP address from {file.filename}.")

if __name__ == "__main__":
    cleanup()
    session.close()