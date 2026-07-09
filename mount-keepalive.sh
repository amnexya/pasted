#!/bin/sh

# This is used to keep an rclone mount alive, as it seems to go to sleep and prevent flask from reading files after a while.
# All this script does is does a listdir on the mount, you should set this up on a cron job with the following options:
# */5 * * * * /path/to/mount-keepalive.sh

ls /srv/pasted-data/ > /dev/null 2>&1
