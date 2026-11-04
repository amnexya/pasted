# ![pasted.sh](app/static/img/pastedlogo.png)

## What is pasted?
It's a file hosting / pastebin platform.

## What's it written in?
It's mostly written in python using flask, with the front-end using Tailwind for styling.

## Setup
Clone this repository using `git clone https://github.com/amnexya/pasted`.

Use `.env.example` to create your `.env` file, you need this for both the database and pasted under Docker, you can change these settings to your liking.

Please ensure your passwords in .env are 32+ characters long, and generated correctly, either through the provided command in `.env.example`, or through your own application.

### WSGI
You will need a database server already running before starting pasted, or be happy using an SQLite DB.
```
# Create your .venv and activate it
python3 -m venv .venv && source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Create your .env
cp .env.example .env && vim .env
# In this .env, you're expected to know what your database URI is,
# You should set this to an already installed and running server or to an sqlite file.
# For everything else, use the instructions above

# OPTIONAL: Set up a cron job for cleanup.py
crontab -e

# This will run every day at 3am.
# cleanup.py removes any files without a db entry, or db entries without a file.
0 3 * * * /path/to/cleanup.py

# Finally, start pasted
# (If you want to change host, port, or debug mode, run ./pasted --help for more info)
./pasted
```

### Docker
In `.env`, uncomment the line for the key `RUN_MODE`, and set your other values as you see fit.

Once you have done that, check `compose.yml` to make sure you're happy with the settings, then run `docker compose up -d` to start pasted.

By default, pasted uses port 5000 under Docker, this can be changed though.

```
vim compose.yml

ports:
	- "5000:80"

# Change that line, keep your internal port the same, but change your external port.
# "external:internal" - don't change 80 unless you really need to.
```

## Contributing
If you want to contribute to pasted, fork the repo, make your changes, then create a pull request.

If you'd like to help moderate pasted, email je@amnexya.com.

## Need help?
Email je@amnexya.com for assistance.

## License
pasted.sh is FOSS, and uses the MIT license, you can see that [here](LICENSE).
