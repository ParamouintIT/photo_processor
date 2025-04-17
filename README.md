# 📷 Image Processing Script for SFTP-received Photos

A Python script that monitors a directory for new images, detects if they are blurry (with special handling for bouquet photos), organizes them by capture time and blur status, and moves them to an external HDD.

---

## 🚀 Features

- Monitors a local folder for new image files in real time  
- Detects blur using Laplacian variance  
- Adjusts detection if flowers/bouquets are likely present  
- Organizes photos into folders by:
  ```
  YYYY-MM-DD / HH / [sharp | blurry]
  ```
- Automatically handles filename conflicts  
- Logs all activity to `image_processor.log`

---

## 🔧 Setup

### 1. Clone the repository

```bash
git clone https://github.com/your-username/your-repo-name.git
cd your-repo-name
```

### 2. Create a virtual environment

```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

---

## 🏁 Usage

Make sure your source and destination folders are correctly set in the script:

```python
SOURCE_DIR = "/Users/yourname/Downloads/"
DESTINATION_BASE_DIR = "/Volumes/ExternalDrive/processed_photos"
```

Then run:

```bash
python your_script_name.py
```

Or:

```bash
chmod +x your_script_name.py
./your_script_name.py
```

---

## 📦 Dependencies

- `opencv-python-headless`  
- `numpy`  
- `Pillow`  
- `watchdog`  

---

## 📝 Notes

- RAW image formats are not analyzed for blurriness due to OpenCV limitations, but are still organized.
- To stop the script safely, use `Ctrl+C`.

---

## 📂 Example Output Structure

```
processed_photos/
└── 2025-04-17/
    ├── 14/
    │   ├── blurry/
    │   └── sharp/
```

---

## 👤 Author

**Your Name**  
📫 your.email@example.com

---

## 🧪 License

This project is licensed under the MIT License.
