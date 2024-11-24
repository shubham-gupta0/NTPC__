import os
from config import *
from .transcript_generation.image_processing  import preprocess_image
from .transcript_generation.pdf_processing  import convert_pdf_to_image
from .transcript_generation.ocr_processing  import initialize_ocr, perform_ocr
from .transcript_generation.word_processing  import save_text_to_word
from .transcript_generation.comparison  import compare_documents

def generate_transcript(pdf_path):
    # Convert PDF to image
    combined_image_path = convert_pdf_to_image(pdf_path, OUTPUT_FOLDER, POPPLER_PATH)

    # Preprocess image
    processed_image_path = preprocess_image(combined_image_path, OUTPUT_FOLDER)

    # Initialize OCR model
    ocr_model = initialize_ocr(OCR_DET_ARCH, OCR_RECO_ARCH, PRETRAINED)

    # Perform OCR
    extracted_text_path = perform_ocr(processed_image_path, OUTPUT_FOLDER, ocr_model)

    # Save text to Word
    formatted_docx_path = save_text_to_word(extracted_text_path, OUTPUT_FOLDER)

    # Compare documents
    compare_documents(STANDARD_DOC_PATH, formatted_docx_path, OUTPUT_FOLDER)
