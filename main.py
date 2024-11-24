import os
from config import *
from utils.generate_transcript import generate_transcript

if __name__ == "__main__":
    # import sys
    # if len(sys.argv) < 2:
    #     print("Usage: python main.py <pdf_path>")
    #     sys.exit(1)

    # pdf_path = sys.argv[1]
    
    pdf_path = r"assets/test1.pdf"
    generate_transcript(pdf_path)
