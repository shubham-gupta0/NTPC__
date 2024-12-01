import os
from config import *
from .transcript_generation.image_processing import preprocess_image
from .transcript_generation.pdf_processing import convert_pdf_to_image, HtmlToPdf
from .transcript_generation.ocr_processing import initialize_ocr, perform_ocr_for_standard

def generate_standard(id, pdf_path):
    # Construct the PDF path based on the provided request_id
    
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"The Standard file {id} does not exist at {pdf_path}.")

    # # Convert PDF to image
    # combined_image_path = convert_pdf_to_image(id, pdf_path, OUTPUT_FOLDER, POPPLER_PATH)
    
    # # Preprocess image
    # processed_image_path = preprocess_image(id, combined_image_path, OUTPUT_FOLDER)
    # print('Processed Image')

    # Initialize OCR model
    ocr_model = initialize_ocr(OCR_DET_ARCH, OCR_RECO_ARCH, PRETRAINED)
    print('OCR Performed')

    # Perform OCR
    standard_text_path = perform_ocr_for_standard(id, 'processed_image_path', 'assets', ocr_model, pdf_path=pdf_path)
    
    Config.STANDARD_DOC_PATH = standard_text_path  # Update the path dynamically
    print(f'Standard Document Path set to {Config.STANDARD_DOC_PATH}')

    return f"Standard Text for {id} Generated!"
