from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from dataclasses import dataclass
import tomllib
import os

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

print(f"{Colours.green}[INFO] {Colours.endc}Starting WSGI...")

app = Flask(__name__)

# Database URI
app.config['SQLALCHEMY_DATABASE_URI'] = config['database_uri']
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['MAX_CONTENT_LENGTH'] = config['max_file_size'] * 1024 * 1024

db = SQLAlchemy(app)
migrate = Migrate(app, db)

from app import routes, models  # noqa: E402, F401
