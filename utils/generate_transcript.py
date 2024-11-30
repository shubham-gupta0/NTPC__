import os
from config import *
from .transcript_generation.image_processing import preprocess_image
from .transcript_generation.pdf_processing import convert_pdf_to_image, HtmlToPdf
from .transcript_generation.ocr_processing import initialize_ocr, perform_ocr
from .transcript_generation.comparison import compare_documents
from .transcript_generation.qwen import getMetadata

def generate_transcript(id, pdf_path):
    # Construct the PDF path based on the provided request_id
    
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"The PDF file for ID {id} does not exist at {pdf_path}.")

    # Convert PDF to image
    combined_image_path = convert_pdf_to_image(id, pdf_path, OUTPUT_FOLDER, POPPLER_PATH)
    
    # Preprocess image
    processed_image_path = preprocess_image(id, combined_image_path, OUTPUT_FOLDER)
    print('Processed Image')

    # Initialize OCR model
    ocr_model = initialize_ocr(OCR_DET_ARCH, OCR_RECO_ARCH, PRETRAINED)
    print('OCR Performed')

    # Perform OCR
    extracted_text_path = perform_ocr(id, processed_image_path, OUTPUT_FOLDER, ocr_model)
    
    # Compare documents
    comparisons = compare_documents(id, STANDARD_DOC_PATH, extracted_text_path, output_dir=OUTPUT_FOLDER)
    print('Transcript HTML Generated')

    #save pdf for transcript
    HtmlToPdf(id, comparisons['html_file'], output_dir=OUTPUT_FOLDER)
    print('Transcript Pdf Generated')

    #Generate Metadata
    # getMetadata(id, extracted_text_path, OUTPUT_FOLDER)

    return f"Transcript for ID: {id} Generated!"
