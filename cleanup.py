#!/usr/bin/env python3

import os

import tomllib

from app import app, models


def load_cfg():
    """Load the configuration from the config.toml file."""
    while True:
        if not os.path.exists(os.getcwd() + "/pasted.toml") and not os.path.exists(
            os.path.expanduser("~/.config/pasted.toml")
        ):
            cfg_path = input(
                "Config file not found in current directory, please enter absolute path to your config file: "
            )
        elif not os.path.exists(os.getcwd() + "/pasted.toml"):
            cfg_path = os.path.expanduser("~/.config/pasted.toml")
        else:
            cfg_path = os.getcwd() + "/pasted.toml"

        print("-- Got config file at " + cfg_path + " --")

        # Check if file selected is valid
        with open(cfg_path, "rb") as f:
            try:
                cfg = tomllib.load(f)
                return cfg
            except Exception as e:
                print(f"Error loading config file: {e}")
                continue


def main():
    # start db
    app.app_context().push()

    cfg = load_cfg()

    # Get local files
    files = os.listdir(cfg["local_data"])
    print("Local files found are " + ", ".join(files))

    # Get db files
    db_files = [f.filename for f in models.File.query.all()]
    print("DB files found are " + ", ".join(db_files))

    # Compare lists
    if [f for f in files if f not in db_files]:
        print("-- DISCREPANIES FOUND: Files not in DB but are in local. --")
        print([f for f in files if f not in db_files])
        print("Fixing discrepancies...")
        # get list of files not in db
        for f in [f for f in files if f not in db_files]:
            print("Removing file " + f + " from local...")
            os.remove(os.path.join(cfg["local_data"], f))
    else:
        print("-- No discrepancies found, files and DB are clean. --")


if __name__ == "__main__":
    main()
