import os

# Poppler binary path
POPPLER_PATH = r"libs/poppler-24.08.0/Library/bin"

# Output folder configuration
OUTPUT_FOLDER = "output"
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# Paths for assets
STANDARD_DOC_PATH = os.path.join("assets", "standard.docx")

# OCR model configurations
OCR_DET_ARCH = 'db_resnet50'
OCR_RECO_ARCH = 'crnn_vgg16_bn'
PRETRAINED = True
