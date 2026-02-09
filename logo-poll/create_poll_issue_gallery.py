import requests
import os
import logging
from datetime import datetime

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/home/fred/xlibre_logo/poll_logs.txt'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Configuration
REPO_OWNER = "fredvs"
REPO_NAME = "test"
TITLE_POLL = "XLibre Logo Poll (Test)"  # Used for new issues or updates if PRESERVE_TITLE_ON_UPDATE is False
POLL_ISSUE_NUMBER = 88  # Set to None to create a new poll, or a number (e.g., 69) to update
PRESERVE_TITLE_ON_UPDATE = True  # Set to True to preserve existing title on update, False to use TITLE_POLL
CREATE_ON_NOT_FOUND = True  # Set to True to create a new issue if POLL_ISSUE_NUMBER is deleted/inaccessible
RESULTS_ISSUE_NUMBER = 33  # Your results issue
LOGO_BASE_URL = "https://raw.githubusercontent.com/fredvs/test/main/logos"
GITHUB_API_URL = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}"
UPLOAD_URL = f"{GITHUB_API_URL}/contents/logos"
DEADLINE = "2025-09-25 at 23:59 CEST"
LOGOS_PER_ROW = 3  # Number of logos per row (adjustable: 2-4 recommended)
AUTO_NUMBER = True  # Set to True for auto-numbered logos, False to use file name numbers and skip duplicates

# GitHub Personal Access Token
GITHUB_TOKEN = "ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"

HEADERS = {
    "Authorization": f"token {GITHUB_TOKEN}",
    "Accept": "application/vnd.github+json"
}

def read_logo_metadata():
    """Fetch logo metadata from the /logos directory in the GitHub repository."""
    logos = []
    seen_numbers = set()  # Track used logo numbers when AUTO_NUMBER is False
    try:
        response = requests.get(UPLOAD_URL, headers=HEADERS)
        if response.status_code != 200:
            logger.error(f"Failed to fetch logos from {UPLOAD_URL}: {response.status_code} {response.json().get('message', '')}")
            return logos

        graphic_extensions = {'.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp'}
        for file in sorted(response.json(), key=lambda x: x['name']):  # Sort for consistent order
            if file['type'] == 'file' and os.path.splitext(file['name'])[1].lower() in graphic_extensions and file['name'].startswith('logo_'):
                try:
                    parts = os.path.splitext(file['name'])[0].split('_', 2)
                    if len(parts) < 3:
                        logger.warning(f"Skipping malformed file name: {file['name']}")
                        continue
                    logo_num = int(parts[1])
                    username = parts[2]
                    if not AUTO_NUMBER and logo_num in seen_numbers:
                        logger.warning(f"Skipping duplicate logo number {logo_num} in {file['name']}")
                        continue
                    seen_numbers.add(logo_num)
                    logos.append((logo_num, username, file['name']))  # Store full file name
                except (ValueError, IndexError) as e:
                    logger.warning(f"Failed to parse file name: {file['name']} ({e})")
                    continue

        logger.info(f"Fetched {len(logos)} logos from {UPLOAD_URL}")
        return sorted(logos, key=lambda x: x[0])  # Sort by logo number
    except Exception as e:
        logger.error(f"Error fetching logos: {e}")
        return logos

def create_poll_issue():
    """Create or update a GitHub issue for the logo poll with logos in a gallery table."""
    logos = read_logo_metadata()
    if not logos:
        logger.error("No logos found, cannot create or update poll issue")
        return

    # Build issue body
    current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S %Z')
    body = f"""# XLibre Logo Poll (Updated {current_time})

Please vote for your favorite logo by commenting **exactly** `Vote: Logo X` (e.g., **`Vote: Logo 1`**).
Only 3 votes per user will be counted; additional votes will be ignored.
You can only vote once for the same logo.
Suspicious accounts (e.g., newly created) may be excluded.
Each person is limited to voting with one GitHub account.

**Deadline to vote**: {DEADLINE}.

[🟢 **Poll Results** 🟢](https://github.com/{REPO_OWNER}/{REPO_NAME}/issues/{RESULTS_ISSUE_NUMBER if RESULTS_ISSUE_NUMBER else 'TBD'})

## Logos
| {" | ".join([''] * LOGOS_PER_ROW)} |
| {" | ".join([':---:' for _ in range(LOGOS_PER_ROW)])} |
"""

    # Group logos into rows
    for i in range(0, len(logos), LOGOS_PER_ROW):
        row_logos = logos[i:i + LOGOS_PER_ROW]
        row_images = []
        for logo_num, username, file_name in row_logos:
            logo_url = f"{LOGO_BASE_URL}/{file_name}"
            row_images.append(f"![Logo {logo_num}]({logo_url})<br>**Logo {logo_num}** (by {username})")
        # Fill empty cells if the row is not complete
        row_images += [''] * (LOGOS_PER_ROW - len(row_images))
        body += f"| {' | '.join(row_images)} |\n"

    # Debug: Print the body to verify content
    logger.debug("Issue body:\n%s", body)

    if POLL_ISSUE_NUMBER:
        # Try to update existing issue
        logger.info(f"Attempting to update poll issue #{POLL_ISSUE_NUMBER} with timestamp: {current_time}")
        try:
            check_response = requests.get(f"{GITHUB_API_URL}/issues/{POLL_ISSUE_NUMBER}", headers=HEADERS)
            if check_response.status_code == 410:  # Issue deleted
                logger.error(f"Issue #{POLL_ISSUE_NUMBER} was deleted (410 Gone)")
                if CREATE_ON_NOT_FOUND:
                    logger.info(f"Creating new issue since #{POLL_ISSUE_NUMBER} is deleted")
                    create_new_issue(body)
                    return
                else:
                    logger.error("Cannot update deleted issue and CREATE_ON_NOT_FOUND is False")
                    return
            check_response.raise_for_status()  # Raise for other errors (e.g., 404, 401)
            issue_state = check_response.json().get('state', 'unknown')
            issue_locked = check_response.json().get('locked', False)
            existing_title = check_response.json().get('title', TITLE_POLL)  # Fetch existing title
            logger.info(f"Issue #{POLL_ISSUE_NUMBER} state: {issue_state}, locked: {issue_locked}, title: {existing_title}")
            if issue_locked:
                logger.error(f"Issue #{POLL_ISSUE_NUMBER} is locked and cannot be updated")
                return
            if issue_state == 'closed':
                logger.error(f"Issue #{POLL_ISSUE_NUMBER} is closed and cannot be updated")
                return

            # Use existing title if PRESERVE_TITLE_ON_UPDATE is True, otherwise use TITLE_POLL
            issue_title = existing_title if PRESERVE_TITLE_ON_UPDATE else TITLE_POLL
            issue_data = {
                "title": issue_title,
                "body": body,
                "labels": ["poll"]
            }
            response = requests.patch(
                f"{GITHUB_API_URL}/issues/{POLL_ISSUE_NUMBER}",
                headers=HEADERS,
                json=issue_data
            )
            response.raise_for_status()
            logger.info(f"Successfully updated poll issue: {response.json()['html_url']} with timestamp: {current_time}")
        except requests.exceptions.HTTPError as e:
            logger.error(f"Failed to update poll issue #{POLL_ISSUE_NUMBER}: {e.response.status_code} {e.response.json().get('message', '')}")
            if e.response.status_code in (404, 410) and CREATE_ON_NOT_FOUND:
                logger.info(f"Creating new issue since #{POLL_ISSUE_NUMBER} is not found or deleted")
                create_new_issue(body)
            else:
                logger.error("Update failed and CREATE_ON_NOT_FOUND is False or error not recoverable")
        except Exception as e:
            logger.error(f"Unexpected error updating poll issue #{POLL_ISSUE_NUMBER}: {e}")
    else:
        # Create new issue
        create_new_issue(body)

def create_new_issue(body):
    """Helper function to create a new poll issue."""
    current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S %Z')
    logger.info(f"Creating new poll issue with timestamp: {current_time}")
    issue_data = {
        "title": TITLE_POLL,
        "body": body,
        "labels": ["poll"]
    }
    try:
        response = requests.post(f"{GITHUB_API_URL}/issues", headers=HEADERS, json=issue_data)
        response.raise_for_status()
        new_issue_number = response.json()['number']
        logger.info(f"Created poll issue: {response.json()['html_url']}")
        logger.info(f"Set POLL_ISSUE_NUMBER = {new_issue_number} in your script for future updates")
    except requests.exceptions.HTTPError as e:
        logger.error(f"Failed to create poll issue: {e.response.status_code} {e.response.json().get('message', '')}")
    except Exception as e:
        logger.error(f"Unexpected error creating poll issue: {e}")

def main():
    """Main function to create or update the poll issue."""
    create_poll_issue()

if __name__ == "__main__":
    main()
