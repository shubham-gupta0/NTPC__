import pdfkit

# Specify the path to wkhtmltopdf executable
config = pdfkit.configuration(wkhtmltopdf=r'D:\ntpc_backend\ntpc_backend\libs\wkhtmltopdf\bin\wkhtmltopdf.exe')

# Define the input HTML file and the output PDF file
input_html = 'output/comparision_result_Test_BG_1_removed.html'  # path to your input HTML file
output_pdf = 'transcript.pdf'  # desired path for the output PDF

# Convert HTML to PDF
pdfkit.from_file(input_html, output_pdf, configuration=config)

print(f"PDF saved to {output_pdf}")
