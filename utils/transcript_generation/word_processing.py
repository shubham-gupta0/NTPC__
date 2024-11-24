from docx import Document
from docx.shared import Pt
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
import os 

def set_line_spacing(paragraph, spacing_value):
    """Set custom line spacing for a paragraph."""
    p = paragraph._element
    pPr = p.find(qn('w:pPr'))
    if pPr is None:
        pPr = OxmlElement('w:pPr')
        p.append(pPr)
    spacing = pPr.find(qn('w:spacing'))
    if spacing is None:
        spacing = OxmlElement('w:spacing')
        pPr.append(spacing)
    spacing.set(qn('w:line'), str(int(spacing_value * 240)))

def save_text_to_word(text_file_path, output_folder):
    """Save extracted text to a Word document."""
    with open(text_file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    doc = Document()
    style = doc.styles['Normal']
    font = style.font
    font.name = 'Arial'
    font.size = Pt(11.5)

    for line in content.split('\n'):
        paragraph = doc.add_paragraph(line)
        set_line_spacing(paragraph, 0.7)

    output_file = os.path.join(output_folder, "formatted_document.docx")
    doc.save(output_file)
    return output_file
