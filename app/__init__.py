from flask import Flask
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from werkzeug.middleware.proxy_fix import ProxyFix
import os
import sys
import tomllib

from dotenv import load_dotenv
from time import sleep

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
        r"\*.*\*",             # italic
        r"\[.*\]\(.*\)",       # links
        r"^- ",                # unordered list
        r"^\d+\.\s",           # ordered list
        r"`.*`",               # inline code
        r"```",                # code blocks
    ]

SAFE_MIME = ["image/", "audio/", "video/", "font/", "application/pdf"]

# Define logging
def info(msg: str) -> None:
    print(f"{c_fg.BLUE}[INFO]{c_fg.RESET} {msg}")

def warn(msg: str) -> None:
    print(f"{c_fg.YELLOW}[WARN]{c_fg.RESET} {msg}")

def error(msg: str) -> None:
    print(f"{c_fg.RED}[ERROR]{c_fg.RESET} {msg}")

def die(msg: str="Exiting...") -> None:
    error(msg)
    sys.exit()

info("Starting up...")
app = Flask(__name__)

app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1)

# We need .env unless we're running under docker.
info("Looking for .env")
if os.getenv("RUN_MODE") == "docker":
    info("Skipping check, running in Docker")
elif not os.path.exists(".env"):
    die("Could not find your .env file, please create this file from .env.example.")
else:
    load_dotenv()
    info(f"Found .env")

# Config
info("Setting all app configs")
app.config['LOCAL_DATA'] = os.getenv("LOCAL_DATA", "data") # store data in pwd if no var
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv("DB_URI", "sqlite:///pasted.db") # store db in pwd if no var
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False # static value
app.config['MAX_FILE_SIZE'] = int(os.getenv("MAX_FILE_SIZE", 1024))
app.config['MAX_CONTENT_LENGTH'] = int(app.config['MAX_FILE_SIZE'] * 1024 * 1024) # give max file size in mb
app.config['SECRET_KEY'] = os.getenv("SECRET_KEY") # secret key for flask
app.config['ENC_KEY'] = os.getenv("ENC_KEY") # encryption key for fernet
app.config['SITE_ADMIN'] = os.getenv("SITE_ADMIN", "Admin Email not provided.") # Site admin email
app.config['VERSION'] = os.getenv("VERSION", "main")

info("Checking SECRET_KEY and ENC_KEY are set")
# Check for keys
if app.config['SECRET_KEY'] is None or app.config['ENC_KEY'] is None:
    die("You have set up your config file incorrectly, please go back and set values for SECRET_KEY and ENC_KEY.")

info("Checking SECRET_KEY and ENC_KEY aren't the same.")
# Check if keys are the same
if app.config['SECRET_KEY'] == app.config['ENC_KEY']:
    die("Your secret key and encryption key have the same value, pasted will not start until these are different values.")

info("Looking for data directory")
# check for local datadir
if not os.path.exists(app.config['LOCAL_DATA']):
    warn("Data directory not found, creating it now")
    try:
        # create directory if able to
        os.mkdir(app.config['LOCAL_DATA'])
        info("Data directory created")
    except:
        die(f"Unable to write to {app.config['LOCAL_DATA']}, please check if the path exists, and your user has the correct permissions and try again.")

info("Starting database")

# loop to account for docker delays on starting db
tries=0
max_tries=5
db=None
migrate=None
while True:
    try:
        # loop 5 times, then give up
        info(f"Attempt {tries+1} to connect.")
        sleep(0.5)
 
        db = SQLAlchemy(app)
        sleep(1)
        
        migrate = Migrate(app, db)
        sleep(1)

        # update db
        # same as running flask init, upgrade, and migrate all in one.
        info("Updating DB if needed")
        from app.models import File
        with app.app_context():
            db.create_all()

        break

    except Exception as e:
        if tries <= max_tries:
            db=None
            migrate=None
            warn(e) # type: ignore
            tries+=1
            continue
        else:
            # die if something broke
            print(e)
            print(app.config["DB_URI"])
            die("Database couldn't start, check your database_uri is correct.")


from app import routes, models
