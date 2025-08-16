import requests
import os
from bs4 import BeautifulSoup
from PIL import Image
import cairosvg
import re
import urllib.parse
from io import BytesIO
import logging
import mimetypes

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Configuration
REPO_OWNER = "X11Libre"
REPO_NAME = "xserver"
ISSUE_NUMBER = 112
OUTPUT_DIR = "resized_logos"
LOGO_FORMATS_FILE = "logo_formats.txt"
GITHUB_API_URL = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}"
COMMENTS_URL = f"{GITHUB_API_URL}/issues/{ISSUE_NUMBER}/comments"

# GitHub Personal Access Token
# GITHUB_TOKEN = os.getenv("GITHUB_TOKEN") or input("Enter your GitHub Personal Access Token: ")

GITHUB_TOKEN = "ghp_xxxxxxxxxxxxxxxxxxxxxxxx"

HEADERS = {
    "Authorization": f"token {GITHUB_TOKEN}",
    "Accept": "application/vnd.github.v3+json"
}

# Create output directory
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Initialize logo counter and metadata
logo_counter = 1
logo_metadata = []
skipped_images = []

def fetch_all_comments():
    """Fetch all comments from the issue, handling pagination."""
    comments = []
    page = 1
    while True:
        response = requests.get(f"{COMMENTS_URL}?page={page}&per_page=100", headers=HEADERS)
        if response.status_code != 200:
            logger.error(f"Error fetching comments: {response.status_code} {response.json().get('message', '')}")
            return comments
        page_comments = response.json()
        if not page_comments:
            break
        comments.extend(page_comments)
        page += 1
    return comments

def extract_images_from_html(html):
    """Extract image URLs from HTML content."""
    soup = BeautifulSoup(html, 'html.parser')
    img_tags = soup.find_all('img')
    return [img['src'] for img in img_tags if 'src' in img.attrs]

def extract_images_from_markdown(text):
    """Extract image URLs from Markdown image links (e.g., ![alt](url))."""
    pattern = r'!\[.*?\]\((https?://[^\s)]+)\)'
    return re.findall(pattern, text)

def extract_images_from_imgur(url):
    """Extract image URLs from Imgur albums."""
    try:
        response = requests.get(url)
        if response.status_code != 200:
            logger.warning(f"Failed to access Imgur URL: {url}")
            return []
        soup = BeautifulSoup(response.text, 'html.parser')
        img_tags = soup.find_all('meta', property='og:image')
        return [tag['content'] for tag in img_tags if tag['content'].endswith(('.png', '.jpg', '.jpeg', '.svg'))]
    except Exception as e:
        logger.warning(f"Error fetching Imgur album {url}: {e}")
        return []

def get_image_format(url, response):
    """Determine image format from Content-Type or URL extension."""
    content_type = response.headers.get('Content-Type', '').lower()
    if 'image/png' in content_type:
        return 'png'
    elif 'image/jpeg' in content_type or 'image/jpg' in content_type:
        return 'jpeg'
    elif 'image/svg+xml' in content_type:
        return 'svg'
    # Fallback to URL extension
    parsed = urllib.parse.urlparse(url)
    ext = os.path.splitext(parsed.path)[1].lower().lstrip('.')
    if ext in ['png', 'jpg', 'jpeg', 'svg']:
        return ext
    return None

def download_and_resize_image(url, username, logo_num):
    """Download and resize an image, returning the format."""
    try:
        response = requests.get(url, timeout=10)
        if response.status_code != 200:
            logger.warning(f"Failed to download image: {url}")
            return None

        img_format = get_image_format(url, response)
        if not img_format:
            logger.warning(f"Unknown image format for: {url}")
            return None

        img_data = response.content
        output_path = os.path.join(OUTPUT_DIR, f"logo_{logo_num}_{username}.{img_format}")

        if img_format == 'svg':
            # Convert SVG to PNG
            output_path = os.path.join(OUTPUT_DIR, f"logo_{logo_num}_{username}.png")
            cairosvg.svg2png(bytestring=img_data, write_to=output_path, output_width=100, output_height=100)
            img_format = 'png'
        else:
            # Resize PNG/JPEG
            img = Image.open(BytesIO(img_data))
            img = img.resize((100, 100), Image.Resampling.LANCZOS)
            img.save(output_path, format=img_format.upper())
            img_format = img_format.lower()

        return img_format
    except Exception as e:
        logger.error(f"Error processing image {url}: {e}")
        return None

# Fetch all comments
comments = fetch_all_comments()
logger.info(f"Fetched {len(comments)} comments from issue #{ISSUE_NUMBER}")

# Process each comment
for comment in comments:
    username = comment['user']['login']
    body = comment['body']

    # Extract images from HTML and Markdown
    img_urls = extract_images_from_html(body) + extract_images_from_markdown(body)

    # Check for Imgur albums
    imgur_pattern = r'https://imgur\.com/a/[^\s]+'
    imgur_urls = re.findall(imgur_pattern, body)
    for imgur_url in imgur_urls:
        img_urls.extend(extract_images_from_imgur(imgur_url))

    # Process each image
    for img_url in img_urls:
        logger.info(f"Processing image {logo_counter}: {img_url} (User: {username})")
        img_format = download_and_resize_image(img_url, username, logo_counter)
        if img_format:
            logo_metadata.append(f"Logo {logo_counter}: {img_url} (User: {username}, Original format: {img_format})")
            logo_counter += 1
        else:
            skipped_images.append(f"Image {logo_counter}: {img_url} (User: {username}, Reason: Failed to download or process)")
            logo_counter += 1

# Save metadata
with open(LOGO_FORMATS_FILE, 'w') as f:
    f.write('\n'.join(logo_metadata))
    if skipped_images:
        f.write('\n\nSkipped Images:\n' + '\n'.join(skipped_images))

logger.info(f"Processed {logo_counter-1} images. Metadata saved to {LOGO_FORMATS_FILE}")
if skipped_images:
    logger.warning(f"Skipped {len(skipped_images)} images. Check {LOGO_FORMATS_FILE} for details.")
