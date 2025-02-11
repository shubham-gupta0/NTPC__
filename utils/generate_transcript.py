from datetime import datetime
import os
from config import *
from .transcript_generation.image_processing import preprocess_image
from .transcript_generation.pdf_processing import convert_pdf_to_image, HtmlToPdf
from .transcript_generation.ocr_processing import initialize_ocr, perform_ocr
from .transcript_generation.comparison import compare_documents
from .transcript_generation.qwen import getMetadata
import pdfkit
    
    
def generate_transcript(input_name, pdf_path):
    # Construct the PDF path based on the provided request_id
    # print(db)
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"The PDF file for ID {input_name} does not exist at {pdf_path}.")

    # Convert PDF to image
    combined_image_path = convert_pdf_to_image(input_name, pdf_path, OUTPUT_FOLDER, POPPLER_PATH)
    
    # Preprocess image
    processed_image_path = preprocess_image(input_name, combined_image_path, OUTPUT_FOLDER)
    print('Processed Image')

    # Initialize OCR model
    ocr_model = initialize_ocr(OCR_DET_ARCH, OCR_RECO_ARCH, PRETRAINED)
    print('OCR Performed')

    # Perform OCR
    extracted_text_path = perform_ocr(input_name, processed_image_path, OUTPUT_FOLDER, ocr_model)
    
    # Compare documents
    comparisons = compare_documents(input_name, Config.STANDARD_DOC_PATH, extracted_text_path, output_dir=OUTPUT_FOLDER)
    print('Transcript HTML Generated')
    
    # store_transcript_details(pdf_id, extracted_text_path, db)
    # print('Transcript Stored in Database')
    #save pdf for transcript
    trans_path=HtmlToPdf(input_name, os.path.join(OUTPUT_FOLDER, f'comparison_result_{input_name}.html'), output_dir=OUTPUT_FOLDER)
    print('Transcript Pdf Generated at comparison_result_{input_name}.html')

    #Generate Metadata
    print('Generating Metadata')
    metadata_path=getMetadata(input_name, extracted_text_path, OUTPUT_FOLDER)
    print('Metadata Generated')
    
    return (trans_path,metadata_path,comparisons["insertions_csv"],comparisons["deletions_csv"])
