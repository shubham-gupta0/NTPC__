import os

# Poppler binary path
POPPLER_PATH = r"libs/poppler-24.08.0/Library/bin"
wkhtmltopdf_PATH = r"libs/wkhtmltopdf/bin/wkhtmltopdf.exe"

# Output folder configuration
OUTPUT_FOLDER = "output"
os.makedirs(OUTPUT_FOLDER, exist_ok=True)
HYPERLINK_OUTPUTS = 'hyperlink_outputs'
os.makedirs(HYPERLINK_OUTPUTS, exist_ok=True)

# Paths for assets
class Config:
    # STANDARD_DOC_PATH = os.path.join('assets', 'standard_text_Standard_3.txt')
    STANDARD_DOC_PATH = ''



# OCR model configurations
OCR_DET_ARCH = 'db_resnet50'
OCR_RECO_ARCH = 'crnn_vgg16_bn'
PRETRAINED = True
