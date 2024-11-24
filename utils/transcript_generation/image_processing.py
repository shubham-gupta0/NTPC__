import cv2
import os
import numpy as np
from PIL import Image

def preprocess_image(id, image_path, output_folder):
    """Apply preprocessing to enhance the image for OCR."""
    img = cv2.imread(image_path)
    adjusted_img = np.clip(3.0 * img - 180, 0, 255).astype(np.uint8)
    gray_img = cv2.cvtColor(adjusted_img, cv2.COLOR_BGR2GRAY)
    _, binary_img = cv2.threshold(gray_img, 150, 255, cv2.THRESH_BINARY)
    processed_path = os.path.join(output_folder, f"processed_image_{id}.png")
    cv2.imwrite(processed_path, binary_img)
    return processed_path
