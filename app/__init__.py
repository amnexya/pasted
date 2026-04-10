from dataclasses import dataclass
from flask import Flask
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
import os
import tomllib

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

print(f"{Colours.green}[INFO] {Colours.endc}Checking for local file directory...")
if not os.path.exists(config['local_data']):
    exit(f"{Colours.red}[ERROR] {Colours.endc}Local data directory not found.")

print(f"{Colours.green}[INFO] {Colours.endc}Checking for key.txt...")
if not os.path.exists("key.txt"):
    exit(f"{Colours.red}[ERROR] {Colours.endc}key.txt not found, this file should contain a random string used for at-rest encryption, generate one with `head -c 32 /dev/urandom | base64 > key.txt`")

print(f"{Colours.green}[INFO] {Colours.endc}Starting WSGI...")

app = Flask(__name__)

# Database URI
app.config['SQLALCHEMY_DATABASE_URI'] = config['database_uri']
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['MAX_CONTENT_LENGTH'] = config['max_file_size'] * 1024 * 1024
app.config['SECRET_KEY'] = config['flask_secret_key']

with open("key.txt", "rb") as f:
    app.config['encryption_key'] = f.read()

db = SQLAlchemy(app)
migrate = Migrate(app, db)

from app import routes, models  # noqa: E402, F401
