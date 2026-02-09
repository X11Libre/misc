import requests
import os
import logging
import base64

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Configuration
REPO_OWNER = "fredvs"
REPO_NAME = "test"
GITHUB_API_URL = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}"
UPLOAD_URL = f"{GITHUB_API_URL}/contents/logos"
RESIZED_LOGOS_DIR = "resized_logos"  # Local directory with resized graphic files
BRANCH = "main"  # Target branch for uploads and deletions
AUTO_NUMBER = True  # Set to True for auto-numbering, False to use file name numbers

# GitHub Personal Access Token (must have repo scope)
GITHUB_TOKEN = "ghp_xxxxxxxxxxxxxxxxxxxxxxxxxx"

# Supported graphic file extensions (case-insensitive)
GRAPHIC_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp'}

HEADERS = {
    "Authorization": f"token {GITHUB_TOKEN}",
    "Accept": "application/vnd.github.v3+json"
}

def delete_all_logos():
    """Delete all files in the /logos directory of the repository."""
    try:
        # Fetch the list of files in the /logos directory
        response = requests.get(UPLOAD_URL, headers=HEADERS)
        if response.status_code == 404:
            logger.info("No /logos directory found in repository, skipping deletion")
            return True
        if response.status_code != 200:
            logger.error(f"Failed to fetch logos: {response.status_code} {response.json().get('message', '')}")
            return False

        files = response.json()
        if not isinstance(files, list):
            logger.error("Unexpected response format when fetching logos")
            return False

        # Delete each file
        for file in files:
            if file['type'] == 'file':
                file_path = file['path']
                sha = file['sha']
                delete_url = f"{GITHUB_API_URL}/contents/{file_path}"
                delete_data = {
                    "message": f"Delete {file_path} for logo refresh",
                    "sha": sha,
                    "branch": BRANCH
                }
                response = requests.delete(delete_url, headers=HEADERS, json=delete_data)
                if response.status_code == 200:
                    logger.info(f"Deleted {file_path}")
                else:
                    logger.error(f"Failed to delete {file_path}: {response.status_code} {response.json().get('message', '')}")
                    return False
        return True
    except Exception as e:
        logger.error(f"Error deleting logos: {e}")
        return False

def get_logo_files():
    """Get list of graphic files from RESIZED_LOGOS_DIR with logo number and username."""
    if not os.path.exists(RESIZED_LOGOS_DIR):
        logger.error(f"Local directory {RESIZED_LOGOS_DIR} not found")
        return []

    logo_files = []
    seen_numbers = set()  # Track used logo numbers when AUTO_NUMBER is False

    for file_name in sorted(os.listdir(RESIZED_LOGOS_DIR)):  # Sort for consistent order
        file_ext = os.path.splitext(file_name)[1].lower()
        if file_ext not in GRAPHIC_EXTENSIONS or not file_name.startswith('logo_'):
            logger.warning(f"Skipping non-graphic or non-logo file: {file_name}")
            continue

        file_path = os.path.join(RESIZED_LOGOS_DIR, file_name)
        if not os.path.isfile(file_path):
            logger.warning(f"Skipping non-file entry: {file_name}")
            continue

        # Parse file name
        try:
            parts = os.path.splitext(file_name)[0].split('_', 2)
            if len(parts) < 3:
                logger.warning(f"Skipping malformed file name: {file_name}")
                continue
            original_logo_num = parts[1]
            try:
                logo_num = int(original_logo_num)  # Validate number
            except ValueError:
                logger.warning(f"Invalid logo number in {file_name}: {original_logo_num}")
                continue
            username = parts[2]
            if not username:
                logger.warning(f"Empty username in {file_name}")
                continue

            if AUTO_NUMBER:
                # Assign new number based on index (will be set later)
                logo_files.append((file_name, username, file_ext, file_path))
            else:
                # Use file name number, skip duplicates
                if logo_num in seen_numbers:
                    logger.warning(f"Skipping duplicate logo number {logo_num} in {file_name}")
                    continue
                seen_numbers.add(logo_num)
                new_file_name = file_name  # Keep original name
                logo_files.append((new_file_name, username, file_ext, file_path))
        except Exception as e:
            logger.warning(f"Failed to parse file name {file_name}: {e}")
            continue

    if AUTO_NUMBER:
        # Reassign logo numbers sequentially
        logo_files = [(f"logo_{i+1}_{username}{ext}", username, ext, path) 
                      for i, (_, username, ext, path) in enumerate(logo_files)]

    logger.info(f"Found {len(logo_files)} valid logo files")
    return logo_files

def upload_logos():
    """Upload graphic files from RESIZED_LOGOS_DIR to the /logos directory."""
    logo_files = get_logo_files()
    if not logo_files:
        logger.error("No valid graphic files found to upload")
        return False

    uploaded = 0
    for file_name, _, _, file_path in logo_files:
        # Read and encode the file content
        try:
            with open(file_path, 'rb') as f:
                content = base64.b64encode(f.read()).decode('utf-8')
        except Exception as e:
            logger.error(f"Failed to read {file_name}: {e}")
            continue

        # Upload the file to /logos
        upload_url = f"{GITHUB_API_URL}/contents/logos/{file_name}"
        upload_data = {
            "message": f"Upload logo {file_name}",
            "content": content,
            "branch": BRANCH
        }
        response = requests.put(upload_url, headers=HEADERS, json=upload_data)
        if response.status_code in (201, 200):
            logger.info(f"Uploaded {file_name}")
            uploaded += 1
        else:
            logger.error(f"Failed to upload {file_name}: {response.status_code} {response.json().get('message', '')}")
            return False

    logger.info(f"Successfully uploaded {uploaded} logos")
    return uploaded > 0

def main():
    """Main function to delete existing logos and upload new ones."""
    logger.info("Starting logo refresh process")
    
    # Step 1: Delete all existing logos
    logger.info("Deleting existing files in /logos directory")
    if not delete_all_logos():
        logger.error("Aborting due to deletion failure")
        return

    # Step 2: Upload new logos
    logger.info(f"Uploading graphic files from {RESIZED_LOGOS_DIR}")
    if not upload_logos():
        logger.error("No graphic files uploaded")
        return

    logger.info("Logo refresh completed successfully")

if __name__ == "__main__":
    main()
