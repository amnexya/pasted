# ![pasted.sh](app/static/img/pastedlogo.png)

## What is pasted.sh?
It's a file hosting / pastebin platform.

## What's it written in?
It's mostly written in python using flask, with the front-end using Tailwind for styling.

## Setup
Clone this repository using `git clone https://github.com/amnexya/pasted`.

Use `.env.example` to create your `.env` file, you need this for both the database and pasted under Docker, you can change these settings to your liking.

Please ensure your passwords in .env are 32+ characters long, and generated correctly, either through the provided command in `.env.example`, or through your own application.

### Docker
Check `compose.yml` to make sure you're happy with the settings, then run `docker compose up -d` to start pasted.

By default, pasted uses port 8080 under Docker, this can be changed though.

```
vim compose.yml

ports:
	- "8080:80"

# Change that line, keep your internal port the same, but change your external port.
# "external:internal" - don't change 80 unless you really need to.
```


## Need help?
Email je@amnexya.com

## License
pasted.sh is FOSS, and uses the MIT license, you can see that [here](LICENSE).
