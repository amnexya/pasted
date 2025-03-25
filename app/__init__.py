from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from dataclasses import dataclass
import tomllib
import os
import boto3
import logging

@dataclass
class Colours:
    """Hold the ASCII escape sequences for printing colours."""

    red: str = "\033[31m" # Fatal Errors
    endc: str = "\033[m"
    green: str = "\033[32m" # Info
    yellow: str = "\033[33m" # Non-fatal warnings
    blue: str = "\033[34m" # Log info

# Check for config file either in .config or current directory
config_location = ["~/.config/pasted.toml", "pasted.toml"]

print(f"{Colours.green}[INFO] {Colours.endc}Starting up...")
print(f"{Colours.green}[INFO] {Colours.endc}Checking for config file...")
# Check for config file
config = None
for c in config_location:
    try:
        with open(os.path.expanduser(c), "rb") as f:
            config = tomllib.load(f)
            break # Just in case
    except FileNotFoundError:
        print(f"{Colours.yellow}[WARN] {Colours.endc}No config file found at {c}, attempting next location...")
        continue

if config is None:
    exit(f"{Colours.red}[ERROR] {Colours.endc} No config file found.")

print(f"{Colours.green}[INFO] {Colours.endc}Starting S3 client...")
# Open s3 storage
try:
    s3 = boto3.resource('s3',
    endpoint_url=config['endpoint'],
    aws_access_key_id=config['access'],
    aws_secret_access_key=config['secret'],
    aws_session_token=None,
    config=boto3.session.Config(signature_version='s3v4'),
    verify=True
    )

    s3_client = boto3.client('s3',
        endpoint_url=config['endpoint'],
        aws_access_key_id=config['access'],
        aws_secret_access_key=config['secret'],
        aws_session_token=None,
        config=boto3.session.Config(signature_version='s3v4'),
        verify=True
        )
except Exception as e:
    print(f"{Colours.red}[ERROR] {Colours.endc}S3 client could not be started, see error below.")
    exit(e)

print(f"{Colours.green}[INFO] {Colours.endc}S3 Client started.")

print(f"{Colours.green}[INFO] {Colours.endc}Starting WSGI...")

app = Flask(__name__)

# Database URI
app.config['SQLALCHEMY_DATABASE_URI'] = config['database_uri']


app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['VIEWABLE_FILE_TYPES'] = ['image/png',
                                     'image/jpeg',
                                     'image/gif',
                                     'image/bmp', 
                                     'image/webp', 
                                     'image/svg+xml', 
                                     'audio/mpeg', 
                                     'audio/wav', 
                                     'audio/ogg', 
                                     'video/mp4', 
                                     'video/webm', 
                                     'text/plain', 
                                     'text/html', 
                                     'text/xml', 
                                     'text/css', 
                                     'application/pdf']

db = SQLAlchemy(app)
migrate = Migrate(app, db)

from app import routes, models