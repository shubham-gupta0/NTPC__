import os
from config import *
from .transcript_generation.image_processing import preprocess_image
from .transcript_generation.pdf_processing import convert_pdf_to_image, HtmlToPdf
from .transcript_generation.ocr_processing import initialize_ocr, perform_ocr_for_standard
import PyPDF2

def extract_text_from_pdf(id, pdf_path):
    # Open the PDF file
    with open(pdf_path, "rb") as file:
        reader = PyPDF2.PdfReader(file)
        
        # Initialize a variable to hold the extracted text
        full_text = ""
        
        # Iterate through each page
        for page_num in range(len(reader.pages)):
            page = reader.pages[page_num]
            full_text += page.extract_text()
        
        # If no text was found, print a message
        if not full_text.strip():
            print("Text not available.")
            return False
        else:
            print(full_text)
            # Save extracted text to a .txt file
            text_output_path = os.path.join('assets', f"standard_text_{id}.txt")

            with open(text_output_path, "w") as txt_file:
                txt_file.write(full_text)

            Config.STANDARD_DOC_PATH = text_output_path
            print(f'Standard Document Path set to {Config.STANDARD_DOC_PATH}')
            return True

def generate_standard(id, pdf_path):
    # Construct the PDF path based on the provided request_id
    
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"The Standard file {id} does not exist at {pdf_path}.")
    
    # if(extract_text_from_pdf(id, pdf_path)):
    #     return f"Standard Text for {id} Generated!"
    
    # Convert PDF to image
    combined_image_path = convert_pdf_to_image(id, pdf_path, OUTPUT_FOLDER, POPPLER_PATH)
    
    # Preprocess image
    processed_image_path = preprocess_image(id, combined_image_path, OUTPUT_FOLDER)
    print('Processed Image')

    # Initialize OCR model
    ocr_model = initialize_ocr(OCR_DET_ARCH, OCR_RECO_ARCH, PRETRAINED)
    print('OCR Performed')

    # Perform OCR
    standard_text_path = perform_ocr_for_standard(id, processed_image_path, 'assets', ocr_model, pdf_path=pdf_path)
    
    Config.STANDARD_DOC_PATH = standard_text_path  # Update the path dynamically
    print(f'Standard Document Path set to {Config.STANDARD_DOC_PATH}')

    return f"Standard Text for {id} Generated!"
