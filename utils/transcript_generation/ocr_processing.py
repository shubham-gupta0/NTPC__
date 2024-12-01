import os
import json
from doctr.io import DocumentFile
from doctr.models import ocr_predictor

def initialize_ocr(det_arch, reco_arch, pretrained=True):
    """Initialize the OCR model."""
    return ocr_predictor(det_arch=det_arch, reco_arch=reco_arch, pretrained=pretrained)

def perform_ocr(id, image_path, output_folder, ocr_model):
    """Perform OCR on an image and save results."""
    single_img_doc = DocumentFile.from_images(image_path)
    result = ocr_model(single_img_doc)

    # Save text results
    text_output_path = os.path.join(output_folder, f"extracted_text_{id}.txt")
    with open(text_output_path, 'w', encoding='utf-8') as text_file:
        for page in result.pages:
            for block in page.blocks:
                for line in block.lines:
                    text_file.write(" ".join(word.value for word in line.words) + '\n')
            text_file.write('\n')

    # Save JSON results
    json_output_path = os.path.join(output_folder, f"results_{id}.json")
    with open(json_output_path, 'w') as json_file:
        json.dump(result.export(), json_file, indent=4)

    return text_output_path

# def perform_ocr_for_standard(id, image_path, output_folder, ocr_model):
#     """Perform OCR on an image and save results."""
#     single_img_doc = DocumentFile.from_images(image_path)
#     result = ocr_model(single_img_doc)

#     output_folder = 'assets'

#     # Save text results
#     text_output_path = os.path.join(output_folder, f"standard_text_{id}.txt")
#     with open(text_output_path, 'w', encoding='utf-8') as text_file:
#         for page in result.pages:
#             for block in page.blocks:
#                 for line in block.lines:
#                     text_file.write(" ".join(word.value for word in line.words) + '\n')
#             text_file.write('\n')

#     # Save JSON results
#     json_output_path = os.path.join(output_folder, f"results_{id}.json")
#     with open(json_output_path, 'w') as json_file:
#         json.dump(result.export(), json_file, indent=4)

#     return text_output_path

def perform_ocr_for_standard(id, image_path, output_folder, ocr_model, pdf_path):
    try:
        output_folder = 'assets'
        # Ensure output folder exists
        os.makedirs(output_folder, exist_ok=True)
    
        # Load the image
        single_img_doc = DocumentFile.from_pdf(pdf_path)
        
        # Perform OCR
        result = ocr_model(single_img_doc)
        
        # Prepare output paths
        text_output_path = os.path.join(output_folder, f"standard_text_{id}.txt")
        json_output_path = os.path.join(output_folder, f"results_{id}.json")
        
        # Save text results with preserved line structure
        with open(text_output_path, 'w', encoding='utf-8') as text_file:
            for page in result.pages:
                # Group lines by their vertical position to maintain original layout
                lines_by_position = {}
                for block in page.blocks:
                    for line in block.lines:
                        # Use the top y-coordinate of the line's geometry
                        position = line.geometry[0][1]
                        # Combine words in the line
                        line_text = " ".join(word.value for word in line.words)
                        lines_by_position[position] = line_text
                
                # Sort lines by their vertical position
                sorted_lines = sorted(lines_by_position.items(), key=lambda x: x[0])
                
                # Write lines to file
                for _, line_text in sorted_lines:
                    text_file.write(line_text + '\n')
        
        # Save JSON results
        with open(json_output_path, 'w') as json_file:
            json.dump(result.export(), json_file, indent=4)
        
        return text_output_path
    except Exception as e:
        print(f'Error : {e}')


