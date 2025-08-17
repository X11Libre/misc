This are python3 scripts to create a logo-poll for XLibre.

# Prerequisites.

# Install Debian dependencies
sudo apt-get update
sudo apt-get install -y make build-essential libssl-dev zlib1g-dev \
libbz2-dev libreadline-dev libsqlite3-dev wget curl llvm \
libncurses5-dev libncursesw5-dev xz-utils tk-dev libffi-dev \
liblzma-dev python3 python3-pip python3-venv git

# Create environment directory
mkdir -p ~/xlibre_logo
cd ~/xlibre_logo
python3 -m venv xlibre_env
source xlibre_env/bin/activate

# Install Python dependencies
pip install --upgrade pip
pip install Pillow imagehash cairosvg PyGitHub requests beautifulsoup4

# You are now ready to use all the scripts.

- python3 resize_logos_with_users.py (to download all logos from https://github.com/X11Libre/xserver/issues/112 and resize them)

- python3 rename_indexed_nodouble.py (to check for identical logos and reindex all logo names)

- python3 upload_logos.py (to upload all the logos to a github directory)

- python3 create_poll_issue_gallery.py (to create the poll in github/issue)

- python3 calculate_poll_results_restrict_user.py (to calculate the poll results; you can use crontab to update the results every xx minutes)

Have fun!
