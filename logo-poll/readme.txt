This are python3 scripts to create a logo-poll for XLibre.

Prerequisites.
For Debian, install the following packages:
$ sudo apt install python3-venv python3-full
$ sudo python3 -m pip install --upgrade pip
Next, navigate to the /misc/logo-poll directory:
$ cd /directory_of//misc/logo-poll directory
Next, create the Python environment:
$ python3 -m venv xlibre_env
Activate it:
$ source xlibre_env/bin/activate
Add the Python dependencies:
$ pip install --upgrade pip
$ pip install requests beautifulsoup4 Pillow cairosvg

You are now ready to use all the scripts.

- resize_logos_with_users.py (to download all logos from https://github.com/X11Libre/xserver/issues/112 and resize them)

- rename_indexed_nodouble.py (to check for identical logos and reindex all logo names)

- create_poll_issue_gallery.py (to create the poll in github/issue)

- calculate_poll_results_restrict_user.py (to calculate the poll results; you can use crontab to update the results every xx minutes)

Have fun!
