import os
import re
import logging
import shutil
from pathlib import Path
from datetime import datetime
from PIL import Image
import imagehash
import cairosvg
import tempfile

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
SOURCE_LOGOS_DIR = "resized_logos"  # Source directory with original logo files
DEST_LOGOS_DIR = "renamed_logos"  # Temporary destination directory for renamed logo files
ALLOWED_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp', '.svg'}  # Supported extensions
DRY_RUN = False  # Set to True to preview copying without modifying files
REPLACE_ORIGINAL_DIR = False  # Set to True to delete SOURCE_LOGOS_DIR and rename DEST_LOGOS_DIR to SOURCE_LOGOS_DIR
FILTER_DUPLICATE_IMAGES = True  # Set to True to filter duplicate images based on content
HASH_THRESHOLD = 0  # Hamming distance threshold for image similarity (0 for exact matches)
DUPLICATE_LOG_FILE = "/home/fred/xlibre_logo/logo_duplicate.txt"  # File to log duplicate logos

def compute_image_hash(file_path):
    """Compute perceptual hash of an image file, converting SVG to PNG if needed."""
    try:
        if file_path.suffix.lower() == '.svg':
            # Create a temporary PNG file for hashing
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as temp_file:
                temp_path = temp_file.name
                cairosvg.svg2png(url=str(file_path), output_path=temp_path, output_width=100, output_height=100)
                with Image.open(temp_path) as img:
                    hash_value = str(imagehash.average_hash(img))
                os.unlink(temp_path)  # Clean up temporary file
                return hash_value
        else:
            with Image.open(file_path) as img:
                return str(imagehash.average_hash(img))
    except Exception as e:
        logger.warning(f"Failed to compute hash for {file_path.name}: {e}")
        return None

def write_duplicate_log(duplicates):
    """Write duplicate logos to DUPLICATE_LOG_FILE."""
    if not duplicates:
        logger.info(f"No duplicates found, skipping {DUPLICATE_LOG_FILE}")
        return
    try:
        with open(DUPLICATE_LOG_FILE, 'w') as f:
            for duplicate_file, original_file in duplicates:
                f.write(f"Duplicate: {duplicate_file.name} matches Original: {original_file.name}\n")
        logger.info(f"Wrote {len(duplicates)} duplicates to {DUPLICATE_LOG_FILE}")
    except Exception as e:
        logger.error(f"Failed to write to {DUPLICATE_LOG_FILE}: {e}")

def copy_and_rename_logos():
    """Copy unique logo files from SOURCE_LOGOS_DIR to DEST_LOGOS_DIR with sequential indices."""
    # Convert to absolute paths
    source_dir = Path(SOURCE_LOGOS_DIR).resolve()
    dest_dir = Path(DEST_LOGOS_DIR).resolve()
    if not source_dir.exists() or not source_dir.is_dir():
        logger.error(f"Source directory {source_dir} does not exist or is not a directory")
        return

    if DRY_RUN:
        logger.info(f"DRY_RUN enabled: Previewing copy and rename without modifying files")
    else:
        # Clear destination directory if it exists
        if dest_dir.exists():
            shutil.rmtree(dest_dir)
            logger.info(f"Cleared existing destination directory {dest_dir}")
        dest_dir.mkdir(exist_ok=True)
        logger.info(f"Created destination directory {dest_dir}")

    # Regex to match logo files (e.g., logo_124_username.png)
    pattern = re.compile(r'^logo_\d+_(.*?)(?=\.)(.*)$')

    # Collect valid logo files
    logo_files = []
    for file in source_dir.iterdir():
        if not file.is_file():
            continue
        ext = file.suffix.lower()
        if ext not in ALLOWED_EXTENSIONS:
            logger.warning(f"Skipping file with unsupported extension: {file.name}")
            continue
        match = pattern.match(file.name)
        if not match:
            logger.warning(f"Skipping file with invalid name format: {file.name}")
            continue
        username = match.group(1)
        extension = match.group(2)  # Preserve original case
        logo_files.append((file, username, extension))

    if not logo_files:
        logger.error(f"No valid logo files found in {source_dir}")
        return

    # Sort files by original filename for consistent ordering
    logo_files.sort(key=lambda x: x[0].name)
    logger.info(f"Found {len(logo_files)} valid logo files to process")

    # Filter duplicates based on image content
    unique_logos = []
    image_hashes = {}
    duplicates = []
    if FILTER_DUPLICATE_IMAGES:
        for file, username, extension in logo_files:
            image_hash = compute_image_hash(file)
            if image_hash is None:
                continue  # Skip invalid images
            if image_hash in image_hashes:
                logger.warning(f"Duplicate image detected: {file.name} matches {image_hashes[image_hash][0].name}")
                duplicates.append((file, image_hashes[image_hash][0]))
                continue
            image_hashes[image_hash] = (file, username, extension)
            unique_logos.append((file, username, extension))
    else:
        unique_logos = logo_files

    logger.info(f"Found {len(unique_logos)} unique logo files after filtering")

    # Write duplicate log
    if FILTER_DUPLICATE_IMAGES:
        write_duplicate_log(duplicates)

    # Copy and rename files
    for i, (file, username, extension) in enumerate(unique_logos, 1):
        new_name = f"logo_{i}_{username}{extension}"
        dest_path = dest_dir / new_name
        if DRY_RUN:
            logger.info(f"Would copy {file.name} to {dest_path}")
        else:
            try:
                shutil.copy2(file, dest_path)  # Copy with metadata
                logger.info(f"Copied {file.name} to {new_name}")
            except Exception as e:
                logger.error(f"Failed to copy {file.name} to {new_name}: {e}")
                return

    # Replace original directory if requested
    if not DRY_RUN and REPLACE_ORIGINAL_DIR:
        # Verify destination has same number of files
        dest_files = list(dest_dir.glob('logo_*'))
        if len(dest_files) != len(unique_logos):
            logger.error(f"Destination directory {dest_dir} has {len(dest_files)} files, expected {len(unique_logos)}. Aborting replacement.")
            return
        try:
            # Delete source directory
            shutil.rmtree(source_dir)
            logger.info(f"Deleted original directory {source_dir}")
            # Rename destination to source
            dest_dir.rename(source_dir)
            logger.info(f"Renamed {dest_dir} to {source_dir}")
        except Exception as e:
            logger.error(f"Failed to replace original directory: {e}")
            return

    logger.info(f"{'Previewed' if DRY_RUN else 'Successfully copied and renamed'} {len(unique_logos)} logo files to {dest_dir if not (REPLACE_ORIGINAL_DIR and not DRY_RUN) else source_dir}")

def main():
    """Main function to copy and rename logo files."""
    # Backup recommendation
    source_dir = Path(SOURCE_LOGOS_DIR).resolve()
    backup_dir = source_dir.parent / f"resized_logos_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    logger.info(f"Recommendation: Backup {source_dir} to {backup_dir} before copying")
    if not DRY_RUN:
        logger.info(f"To backup, run: cp -r {source_dir} {backup_dir}")
    copy_and_rename_logos()

if __name__ == "__main__":
    main()
