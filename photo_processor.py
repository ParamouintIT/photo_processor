#!/usr/bin/env python3
"""
Image Processing Script for SFTP-received photos
- Monitors a directory for new images
- Detects if images are blurry (with special handling for bouquet photos)
- Organizes photos by capture time and blur status
- Moves processed files to an external HDD
"""

import os
import time
import shutil
import logging
from datetime import datetime
from pathlib import Path
import cv2
import numpy as np
from PIL import Image
from PIL.ExifTags import TAGS
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("image_processor.log"),
        logging.StreamHandler()
    ]
)

# Configuration parameters (adjust as needed)
SOURCE_DIR = "/Users/laszlo/Downloads/"  # Mac built-in HDD
DESTINATION_BASE_DIR = "/Users/laszlo/Downloads/processed_photos"  # External HDD
SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".nef", ".cr2", ".arw", ".raw", ".dng"}
CHECK_INTERVAL = 5  # seconds
LAPLACIAN_THRESHOLD = 100  # Threshold for blurriness detection
BOUQUET_COLOR_THRESHOLD = 0.15  # Threshold for potential bouquet detection

def create_directory_structure(base_dir):
    """Ensure the destination directory structure exists."""
    os.makedirs(base_dir, exist_ok=True)
    return base_dir

def get_image_datetime(file_path):
    """Extract capture time from image EXIF data."""
    try:
        image = Image.open(file_path)
        exif_data = image._getexif()
        
        if not exif_data:
            # If no EXIF data, use file creation time
            return datetime.fromtimestamp(os.path.getctime(file_path))
        
        # Look for DateTimeOriginal or DateTime EXIF tag
        date_time = None
        for tag_id, value in exif_data.items():
            tag = TAGS.get(tag_id, tag_id)
            if tag == "DateTimeOriginal" or tag == "DateTime":
                date_time = value
                break
        
        if date_time:
            # EXIF DateTime format: "YYYY:MM:DD HH:MM:SS"
            return datetime.strptime(date_time, "%Y:%m:%d %H:%M:%S")
        else:
            # If no relevant EXIF timestamp, use file creation time
            return datetime.fromtimestamp(os.path.getctime(file_path))
    except Exception as e:
        logging.warning(f"Error getting image datetime for {file_path}: {e}")
        # Fallback to file creation time
        return datetime.fromtimestamp(os.path.getctime(file_path))

def detect_possible_bouquet(image):
    """
    Detect if image might contain a bouquet based on color characteristics.
    Returns True if a bouquet is likely present.
    """
    # Convert to HSV color space
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    
    # Define color ranges for common flower colors
    color_ranges = [
        # Red flowers (wraps around hue spectrum)
        [(0, 100, 100), (10, 255, 255)],
        [(160, 100, 100), (180, 255, 255)],
        # Pink/purple flowers
        [(125, 50, 100), (155, 255, 255)],
        # Yellow flowers
        [(20, 100, 100), (40, 255, 255)],
        # White flowers (low saturation, high value)
        [(0, 0, 200), (180, 30, 255)]
    ]
    
    total_pixels = image.shape[0] * image.shape[1]
    flower_pixels = 0
    
    # Check each color range
    for lower, upper in color_ranges:
        mask = cv2.inRange(hsv, np.array(lower), np.array(upper))
        flower_pixels += cv2.countNonZero(mask)
    
    # Calculate the proportion of flower-colored pixels
    flower_ratio = flower_pixels / total_pixels
    
    # Return True if the ratio exceeds the threshold
    return flower_ratio > BOUQUET_COLOR_THRESHOLD

def is_image_blurry(file_path):
    """
    Detect if an image is blurry.
    Returns True for blurry images, False for sharp images.
    Adjusts threshold if a bouquet is detected.
    """
    try:
        # Read image
        image = cv2.imread(file_path)
        if image is None:
            # For RAW files that cv2 can't read directly, just assume not blurry
            # In production, you might want to use a RAW conversion library
            if any(file_path.lower().endswith(ext) for ext in [".nef", ".cr2", ".arw", ".raw", ".dng"]):
                logging.info(f"Cannot process RAW file for blur detection: {file_path}")
                return False
            logging.warning(f"Failed to load image: {file_path}")
            return False
        
        # Convert to grayscale
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        # Calculate Laplacian variance (measure of focus)
        laplacian = cv2.Laplacian(gray, cv2.CV_64F)
        laplacian_var = laplacian.var()
        
        # Check if image likely contains a bouquet
        has_bouquet = detect_possible_bouquet(image)
        
        # Adjust threshold if bouquet detected (bouquets tend to have more intrinsic blur)
        adjusted_threshold = LAPLACIAN_THRESHOLD * 0.7 if has_bouquet else LAPLACIAN_THRESHOLD
        
        logging.info(f"Image: {file_path}, Laplacian var: {laplacian_var}, " 
                    f"Bouquet detected: {has_bouquet}, Threshold: {adjusted_threshold}")
        
        # Return True if blurry (laplacian variance below threshold)
        return laplacian_var < adjusted_threshold
    
    except Exception as e:
        logging.error(f"Error detecting blurriness for {file_path}: {e}")
        # Default to not blurry on error
        return False

def determine_destination_path(file_path, base_dir):
    """
    Determine the destination path based on capture time and blur status.
    Returns the full destination path.
    """
    # Get capture datetime
    capture_time = get_image_datetime(file_path)
    
    # Check if image is blurry
    blurry = is_image_blurry(file_path)
    blur_status = "blurry" if blurry else "sharp"
    
    # Create directory structure: YYYY-MM-DD/HH/blur_status
    date_str = capture_time.strftime("%Y-%m-%d")
    hour_str = capture_time.strftime("%H")
    
    destination_dir = os.path.join(base_dir, date_str, hour_str, blur_status)
    os.makedirs(destination_dir, exist_ok=True)
    
    # Preserve original filename
    filename = os.path.basename(file_path)
    destination_path = os.path.join(destination_dir, filename)
    
    # Handle filename conflicts by adding a counter
    counter = 1
    name, ext = os.path.splitext(filename)
    while os.path.exists(destination_path):
        new_filename = f"{name}_{counter}{ext}"
        destination_path = os.path.join(destination_dir, new_filename)
        counter += 1
    
    return destination_path

def process_image(file_path, base_dir):
    """Process a single image file."""
    try:
        # Skip processing if not an image file
        if not any(file_path.lower().endswith(ext) for ext in SUPPORTED_EXTENSIONS):
            logging.debug(f"Skipping non-image file: {file_path}")
            return False
        
        # Determine destination path
        dest_path = determine_destination_path(file_path, base_dir)
        
        # Move the file
        shutil.move(file_path, dest_path)
        logging.info(f"Processed {file_path} -> {dest_path}")
        return True
    
    except Exception as e:
        logging.error(f"Error processing {file_path}: {e}")
        return False

class ImageHandler(FileSystemEventHandler):
    """File system event handler for new image files."""
    
    def __init__(self, base_dir):
        self.base_dir = base_dir
    
    def on_created(self, event):
        """Handle file creation events."""
        if event.is_directory:
            return
        
        file_path = event.src_path
        logging.info(f"New file detected: {file_path}")
        
        # Wait a short time to ensure file is fully written
        time.sleep(1)
        
        # Process the image
        process_image(file_path, self.base_dir)

def process_existing_files(source_dir, base_dir):
    """Process any existing files in the source directory."""
    logging.info(f"Processing existing files in {source_dir}")
    for root, _, files in os.walk(source_dir):
        for filename in files:
            file_path = os.path.join(root, filename)
            process_image(file_path, base_dir)

def main():
    """Main function to run the image processing system."""
    logging.info("Starting image processing system")
    
    # Create destination directory structure
    create_directory_structure(DESTINATION_BASE_DIR)
    
    # Process any existing files
    process_existing_files(SOURCE_DIR, DESTINATION_BASE_DIR)
    
    # Set up file system observer for new files
    event_handler = ImageHandler(DESTINATION_BASE_DIR)
    observer = Observer()
    observer.schedule(event_handler, SOURCE_DIR, recursive=True)
    observer.start()
    
    try:
        logging.info(f"Monitoring {SOURCE_DIR} for new images...")
        while True:
            time.sleep(CHECK_INTERVAL)
    except KeyboardInterrupt:
        logging.info("Stopping image monitoring")
        observer.stop()
    observer.join()

if __name__ == "__main__":
    main()