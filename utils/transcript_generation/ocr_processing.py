import os
import json
from doctr.io import DocumentFile
from doctr.models import ocr_predictor

def initialize_ocr(det_arch, reco_arch, pretrained=True):
    """Initialize the OCR model."""
    return ocr_predictor(det_arch=det_arch, reco_arch=reco_arch, pretrained=pretrained)

def perform_ocr(image_path, output_folder, ocr_model):
    """Perform OCR on an image and save results."""
    single_img_doc = DocumentFile.from_images(image_path)
    result = ocr_model(single_img_doc)

    # Save text results
    text_output_path = os.path.join(output_folder, "extracted_text.txt")
    with open(text_output_path, 'w', encoding='utf-8') as text_file:
        for page in result.pages:
            for block in page.blocks:
                for line in block.lines:
                    text_file.write(" ".join(word.value for word in line.words) + '\n')
            text_file.write('\n')

    # Save JSON results
    json_output_path = os.path.join(output_folder, "results.json")
    with open(json_output_path, 'w') as json_file:
        json.dump(result.export(), json_file, indent=4)

    return text_output_path
