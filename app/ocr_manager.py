import os
import shutil
import pytesseract
from PIL import Image

def find_tesseract_binary():
    """Attempts to find the Tesseract OCR binary path on Windows/Linux."""
    # Check if already in PATH
    if shutil.which("tesseract") is not None:
        return "tesseract"
        
    # Common Windows installation directories
    common_windows_paths = [
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
        r"C:\Users\PB915\AppData\Local\Programs\Tesseract-OCR\tesseract.exe"
    ]
    for path in common_windows_paths:
        if os.path.exists(path):
            return path
            
    # Try custom folder under user profiles if any
    user_profile = os.environ.get("USERPROFILE")
    if user_profile:
        user_path = os.path.join(user_profile, "AppData", "Local", "Programs", "Tesseract-OCR", "tesseract.exe")
        if os.path.exists(user_path):
            return user_path
            
    return None

# Configure pytesseract path at startup
tesseract_path = find_tesseract_binary()
if tesseract_path:
    pytesseract.pytesseract.tesseract_cmd = tesseract_path
    print(f"Tesseract OCR path configured: {tesseract_path}")
else:
    print("Tesseract OCR binary not found in standard paths. Local image OCR will be disabled. Manual text input will still be available.")

def perform_ocr(image_file) -> str:
    """Performs OCR on an uploaded file-like image object or PIL Image.
    
    Returns:
        Extracted text as string. Raises ValueError if OCR fails or is not supported.
    """
    if not tesseract_path:
        raise FileNotFoundError(
            "Tesseract OCR engine is not installed or not found on your system. "
            "Please install Tesseract OCR or type/paste your question in the text area."
        )
        
    try:
        image = Image.open(image_file)
        text = pytesseract.image_to_string(image)
        return text.strip()
    except Exception as e:
        raise ValueError(f"Failed to process image OCR: {e}")
