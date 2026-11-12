# ![pasted.sh](app/static/img/pastedlogo.png)

## What is pasted.sh?
It's a file-hosting platform, it can also be used as a pastebin.

## What's it written in?
Mainly Python, production runs with waitress, and uses MariaDB for a DB by default, although this can be changed.

## Setup
This isn't really designed to be self hosted, someday it might though. If you want some help with selfhosting it, email je@amnexya.com.

## Info about .env keys
```
LOCAL_DATA  			- Directory files will be stored
SITE_ADMIN  			- Contact email for site admin
MAX_FILE_SIZE			- Maximum uploadable file size
MAX_PREVIEW_SIZE		- Maximum file size to load for a preview
SECRET_KEY				- Flask secret key (required)
ENC_KEY					- File encryption key (required)
VERSION					- Version number

HOST					- Host to run on (e.g. 127.0.0.1)
PORT					- Port to run on

MARIADB_USER			- DB Username
MARIADB_PASSWORD		- DB Password
MARIADB_ROOT_PASSWORD	- DB Root Password
MARIADB_DATABASE=		- DB Name

DB_URI 					- DB URI for SQLAlchemy
```
Those not labelled `required` can be left blank, and will be filled in with a default value.

## Contributing
If you want to contribute to pasted, fork the repo, make your changes, then create a pull request.

If you'd like to help moderate pasted, email je@amnexya.com.

## License
pasted.sh uses the MIT license, found [here](LICENSE).
