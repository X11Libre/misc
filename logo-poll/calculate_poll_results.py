import requests
import re
import logging
import os
from datetime import datetime

# Set up logging to console and file
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
PAGE_TITLE = "XLibre Logo Poll (Test) Results three columns"
POLL_ISSUE_NUMBER = 63  # Your poll issue
RESULTS_ISSUE_NUMBER = None  # Your results issue, None to create a new
MAX_VOTES_PER_USER = 3  # Maximum votes allowed per user
GITHUB_API_URL = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}"
LOGO_BASE_URL = "https://raw.githubusercontent.com/fredvs/test/main/logos"
UPLOAD_URL = f"{GITHUB_API_URL}/contents/logos"
AUTO_NUMBER = True  # Set to True for auto-numbered logos, False to use file name numbers and skip duplicates
LOGOS_PER_ROW = 3  # Number of logos per row in the results table (adjustable: 2-4 recommended)
MAX_CHARS = 15 # Maximum chars when copying bad comment.

# GitHub Personal Access Token
GITHUB_TOKEN = "ghp_xxxxxxxxxxxxxxxxxxxxx"

HEADERS = {
    "Authorization": f"token {GITHUB_TOKEN}",
    "Accept": "application/vnd.github.v3+json"
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
                    logos.append((logo_num, username, file['name']))  # Store full file name for URL
                except (ValueError, IndexError) as e:
                    logger.warning(f"Failed to parse file name: {file['name']} ({e})")
                    continue

        logger.info(f"Fetched {len(logos)} logos from {UPLOAD_URL}")
        return sorted(logos, key=lambda x: x[0])  # Sort by logo number
    except Exception as e:
        logger.error(f"Error fetching logos: {e}")
        return logos
        
def fetch_issue_creation_date(issue_number):
    """Get the creation date of the poll issue."""
    response = requests.get(f"{GITHUB_API_URL}/issues/{issue_number}", headers=HEADERS)
    if response.status_code == 200:
        return datetime.strptime(response.json()['created_at'], '%Y-%m-%dT%H:%M:%SZ')
    logger.error(f"Failed to fetch issue {issue_number}: {response.status_code} {response.json().get('message', '')}")
    return None

def fetch_comments():
    """Fetch all comments from the poll issue."""
    comments = []
    page = 1
    while True:
        response = requests.get(
            f"{GITHUB_API_URL}/issues/{POLL_ISSUE_NUMBER}/comments?page={page}&per_page=100",
            headers=HEADERS
        )
        if response.status_code != 200:
            logger.error(f"Failed to fetch comments: {response.status_code} {response.json().get('message', '')}")
            return []
        page_comments = response.json()
        if not page_comments:
            break
        comments.extend(page_comments)
        page += 1
    logger.info(f"Fetched {len(comments)} comments from issue #{POLL_ISSUE_NUMBER}")
    return comments

def check_user_creation_date(username, issue_creation_date):
    """Check if a user was created after the poll issue."""
    response = requests.get(f"https://api.github.com/users/{username}", headers=HEADERS)
    if response.status_code != 200:
        logger.warning(f"Failed to fetch user {username}: {response.status_code}")
        return False
    user_creation_date = datetime.strptime(response.json()['created_at'], '%Y-%m-%dT%H:%M:%SZ')
    return user_creation_date > issue_creation_date

def count_votes(comments, valid_logo_numbers):
    """Calculate poll results and create/update results issue.""" 
    if not POLL_ISSUE_NUMBER:
        logger.error("Please set POLL_ISSUE_NUMBER to the poll issue number")
        return
    
    issue_creation_date = fetch_issue_creation_date(POLL_ISSUE_NUMBER)
    if not issue_creation_date:
        logger.error("No creation date found")
        return
   
    """Count votes from comments, limiting to MAX_VOTES_PER_USER per user."""
    vote_counts = {num: 0 for num, _, _ in valid_logo_numbers}
    user_votes = {}  # Track votes per user
   
    vote_pattern = re.compile(r'Vote:\s*Logo\s*(\d+)')
     
    warnings = []  # Collect warnings for results page

    for comment in comments:
        user = comment['user']['login']
        body = comment['body'].strip()
        match = vote_pattern.match(body)
        if not match:
            # Truncate comment to first MAX_CHARS characters + ***
            truncated_body = body[:MAX_CHARS] + "***" if len(body) > MAX_CHARS else body
            logger.warning(f"Invalid vote format in comment by {user}: {truncated_body}")
            warnings.append(f"Invalid vote format by {user}: {truncated_body}")
            continue
        try:
            logo_num = int(match.group(1))
            if logo_num not in [num for num, _, _ in valid_logo_numbers]:
                logger.warning(f"Invalid logo number {logo_num} by {user}")
                warnings.append(f"Invalid logo number {logo_num} by {user}")
                continue
          
            if check_user_creation_date(user, issue_creation_date):
                logger.warning(f"User {user} (voted Logo {logo_num}) created after poll start")
                warnings.append(f"User {user} (voted Logo {logo_num}) created after poll start")
                continue
     
            if user not in user_votes:
                user_votes[user] = []
            if len(user_votes[user]) < MAX_VOTES_PER_USER:
                if logo_num not in user_votes[user]:
                    user_votes[user].append(logo_num)
                    vote_counts[logo_num] += 1
                    logger.info(f"Counted vote for Logo {logo_num} by {user}")
                else:
                    logger.warning(f"Duplicate vote for Logo {logo_num} by {user} ignored")
                    warnings.append(f"Duplicate vote for Logo {logo_num} by {user} ignored")
            else:
                logger.warning(f"User {user} exceeded {MAX_VOTES_PER_USER} votes, ignoring vote for Logo {logo_num}")
                warnings.append(f"User {user} exceeded {MAX_VOTES_PER_USER} votes, ignoring vote for Logo {logo_num}")
        except ValueError:
             # Truncate comment to first MAX_CHARS characters + ***
            truncated_body = body[:MAX_CHARS] + "***" if len(body) > MAX_CHARS else body
            logger.warning(f"Invalid vote format in comment by {user}: {truncated_body}")
            warnings.append(f"Invalid vote format by {user}: {truncated_body}")
    
    return vote_counts, user_votes, warnings

def update_results_issue(vote_counts, valid_logo_numbers, warnings):
    """Update the results issue with a multi-column table of logos with votes and warnings."""
    current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S %Z')  # Use local timezone
    logger.info(f"Generating results with timestamp: {current_time}")
    total_votes = sum(vote_counts.values())
    body = f"""# XLibre Logo Poll Results (Updated {current_time})
[🟢 **Logo Poll** 🟢](https://github.com/{REPO_OWNER}/{REPO_NAME}/issues/{POLL_ISSUE_NUMBER})

## Total: {total_votes} valid vote{'s' if total_votes != 1 else ''}.

## Vote Results
| {" | ".join([''] * LOGOS_PER_ROW)} |
| {" | ".join([':---:' for _ in range(LOGOS_PER_ROW)])} |
"""

    # Sort logos by vote count (descending) and logo number (ascending)
    sorted_logos = sorted(
        [(logo_num, username, file_name, vote_counts.get(logo_num, 0)) for logo_num, username, file_name in valid_logo_numbers if vote_counts.get(logo_num, 0) > 0],
        key=lambda x: (-x[3], x[0])  # Sort by votes (descending), then logo number (ascending)
    )

    if sorted_logos:
        # Group logos into rows
        for i in range(0, len(sorted_logos), LOGOS_PER_ROW):
            row_logos = sorted_logos[i:i + LOGOS_PER_ROW]
            row_images = []
            for logo_num, username, file_name, votes in row_logos:
                logo_url = f"{LOGO_BASE_URL}/{file_name}"
                row_images.append(f"![Logo {logo_num}]({logo_url})<br>**Logo {logo_num}** (by {username}): **{votes}** vote{'s' if votes != 1 else ''}")
            # Fill empty cells if the row is not complete
            row_images += [''] * (LOGOS_PER_ROW - len(row_images))
            body += f"| {' | '.join(row_images)} |\n"
    else:
        body += "No valid votes recorded yet.\n"

    # Add Invalid Votes section
    body += "\n## Invalid Votes\n"
    if warnings:
        body += "\n".join(f"- {warning}" for warning in warnings) + "\n"
    else:
        body += "No invalid votes recorded.\n"

    # Debug: Print the body to verify content
    logger.debug("Results issue body:\n%s", body)

    issue_data = {
        "title": PAGE_TITLE,
        "body": body
    }
    if RESULTS_ISSUE_NUMBER:
        logger.info(f"Attempting to update issue #{RESULTS_ISSUE_NUMBER} with timestamp: {current_time}")
        check_response = requests.get(f"{GITHUB_API_URL}/issues/{RESULTS_ISSUE_NUMBER}", headers=HEADERS)
        if check_response.status_code != 200:
            logger.error(f"Cannot access issue #{RESULTS_ISSUE_NUMBER}: {check_response.status_code} {check_response.json().get('message', '')}")
            return
        issue_state = check_response.json().get('state', 'unknown')
        issue_locked = check_response.json().get('locked', False)
        logger.info(f"Issue #{RESULTS_ISSUE_NUMBER} state: {issue_state}, locked: {issue_locked}")
        if issue_locked:
            logger.error(f"Issue #{RESULTS_ISSUE_NUMBER} is locked and cannot be updated")
            return
        if issue_state == 'closed':
            logger.error(f"Issue #{RESULTS_ISSUE_NUMBER} is closed and cannot be updated")
            return

        response = requests.patch(
            f"{GITHUB_API_URL}/issues/{RESULTS_ISSUE_NUMBER}",
            headers=HEADERS,
            json=issue_data
        )
        if response.status_code == 200:
            logger.info(f"Successfully updated results issue: {response.json()['html_url']} with timestamp: {current_time}")
        else:
            logger.error(f"Failed to update results issue #{RESULTS_ISSUE_NUMBER}: {response.status_code} {response.json().get('message', '')}")
    else:
        logger.info(f"Creating new results issue with timestamp: {current_time}")
        response = requests.post(
            f"{GITHUB_API_URL}/issues",
            headers=HEADERS,
            json=issue_data
        )
        if response.status_code == 201:
            new_issue_number = response.json()['number']
            logger.info(f"Created results issue: {response.json()['html_url']}")
            logger.info(f"Set RESULTS_ISSUE_NUMBER = {new_issue_number} in your script")
        else:
            logger.error(f"Failed to create results issue: {response.status_code} {response.json().get('message', '')}")

def main():
    """Main function to calculate and update poll results."""
    valid_logo_numbers = read_logo_metadata()
    if not valid_logo_numbers:
        logger.error("No valid logos found, exiting")
        return
    comments = fetch_comments()
    vote_counts, user_votes, warnings = count_votes(comments, valid_logo_numbers)
    update_results_issue(vote_counts, valid_logo_numbers, warnings)

if __name__ == "__main__":
    main()
