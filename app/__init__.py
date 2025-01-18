from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from dataclasses import dataclass
import tomllib
import os
import boto3

@dataclass
class Colours:
    """Hold the ASCII escape sequences for printing colours."""

    red: str = "\033[31m"
    endc: str = "\033[m"
    green: str = "\033[32m"
    yellow: str = "\033[33m"
    blue: str = "\033[34m"


# Check for config file
try:
    with open(os.path.expanduser('~/.config/pasted.toml'), "rb") as f:
        config = tomllib.load(f)
except FileNotFoundError:
    exit(f"{Colours.red}Error: {Colours.endc}No config file found at ~/.config/pasted.toml")

# Open s3 storage
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

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = config['database_uri']
db = SQLAlchemy(app)
migrate = Migrate(app, db)

from app import routes, models