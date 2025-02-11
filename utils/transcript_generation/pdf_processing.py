import os
from PIL import Image
from pdf2image import convert_from_path
import pdfkit
from config import *

def convert_pdf_to_image(id, pdf_path, output_folder, poppler_path):
    """Convert PDF pages into a single vertically joined image."""
    images = convert_from_path(pdf_path, dpi=300, poppler_path=poppler_path)
    if not images:
        raise ValueError(f"No images generated for {pdf_path}.")

    total_height = sum(img.height for img in images)
    max_width = max(img.width for img in images)
    combined_image = Image.new('RGB', (max_width, total_height))

    y_offset = 0
    for img in images:
        combined_image.paste(img, (0, y_offset))
        y_offset += img.height

    output_path = os.path.join(output_folder, f"combined_image_{id}.png")
    combined_image.save(output_path, "PNG")
    return output_path

# Specify the path to wkhtmltopdf
config = pdfkit.configuration(wkhtmltopdf=wkhtmltopdf_PATH)

def HtmlToPdf(id, html_path, output_dir, config=config):
    pdfkit.from_file(html_path, os.path.join(output_dir, f'comparison_result_{id}.pdf'), configuration=config)
    return os.path.join(output_dir, f'comparison_result_{id}.pdf')


