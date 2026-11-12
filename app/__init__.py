from flask import Flask
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
import os
import sys

from dotenv import load_dotenv

# Set constants
# make logging look pretty
class c_fg:
    # foreground text colours
    BLACK   = '\033[30m'
    RED     = '\033[31m'
    GREEN   = '\033[32m'
    YELLOW  = '\033[33m'
    BLUE    = '\033[34m'
    MAGENTA = '\033[35m'
    CYAN    = '\033[36m'
    WHITE   = '\033[37m'
    RESET   = '\033[39m'

MARKDOWN_PATTERNS = [
        r"^#{1,6}\s",          # headings
        r"\*\*.*\*\*",         # bold
        r"\[.*\]\(.*\)",       # links
        r"^- ",                # unordered list
        r"^\d+\.\s",           # ordered list
        r"```",                # code blocks
    ]

SAFE_MIME = ("image/", "audio/", "video/", "font/", "application/pdf")

# Define logging
def info(msg: str) -> None:
    print(f"{c_fg.BLUE}[INFO]{c_fg.RESET} {msg}")

def warn(msg: str) -> None:
    print(f"{c_fg.YELLOW}[WARN]{c_fg.RESET} {msg}")

def error(msg: str) -> None:
    print(f"{c_fg.RED}[ERROR]{c_fg.RESET} {msg}")

def die(msg: str="Exiting...") -> None:
    error(msg)
    sys.exit(1)

info("Starting up...")

load_dotenv()

app = Flask(__name__)

info("Setting app variables from env")
app.config['LOCAL_DATA'] = os.getenv("LOCAL_DATA") or "data" # store data in pwd if no var
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv("DB_URI") or "sqlite:///pasted.db" # store db in pwd if no var
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False # static value
app.config['MAX_FILE_SIZE'] = int(os.getenv("MAX_FILE_SIZE", 1024) or 1024)
app.config['MAX_PREVIEW_SIZE'] = int(os.getenv("MAX_PREVIEW_SIZE", 1) or 1) * 1024 * 1024
app.config['MAX_CONTENT_LENGTH'] = int(app.config['MAX_FILE_SIZE'] * 1024 * 1024) # give max file size in mb
app.config['SITE_ADMIN'] = os.getenv("SITE_ADMIN") or "Admin Email not provided." # Site admin email
app.config['VERSION'] = os.getenv("VERSION") or "main"
app.config['MAX_FORM_MEMORY_SIZE'] = 10 * 1024 * 1024

## REQUIRED ##
app.config['SECRET_KEY'] = os.getenv("SECRET_KEY")
app.config['ENC_KEY'] = os.getenv("ENC_KEY")

info("Checking SECRET_KEY and ENC_KEY are set")
# Check for keys
if app.config['SECRET_KEY'] is None or app.config['ENC_KEY'] is None:
    die("SECRET_KEY and ENC_KEY are required environment variables. Please set these before running.")

info("Checking SECRET_KEY and ENC_KEY aren't the same.")
# Check if keys are the same
if app.config['SECRET_KEY'] == app.config['ENC_KEY']:
    die("Your secret key and encryption key have the same value, pasted will not start until these are different values.")

info("Checking length of SECRET_KEY and ENC_KEY")
if len(app.config['SECRET_KEY']) < 32 or len(app.config['ENC_KEY']) < 32:
    die("Your secret key and encryption key are too short, pasted will not launch with insecure keys.")

info("Checking for local data directory...")
if not os.path.exists(app.config['LOCAL_DATA']):
    warn("Local data directory not found, creating it now.")
    try:
        os.mkdir(app.config['LOCAL_DATA'])
        info("Data directory created")
    except:
        die("Couldn't create data directory, ensure the path selected is correct and your user has permissions to create it.")

info("Starting database...")
db = SQLAlchemy(app)
migrate = Migrate(app, db)

from app import routes, models  # noqa: E402, F401
