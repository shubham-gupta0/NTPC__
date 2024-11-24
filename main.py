import os
from fastapi import FastAPI, File, UploadFile
from config import *
from utils.generate_transcript import generate_transcript
from fastapi.responses import FileResponse

app = FastAPI()

@app.get("/")
def read_root():
    return {"message": "Welcome to the PDF Transcript Generator API!"}

@app.post("/generate-transcript/")
async def create_transcript(pdf: UploadFile = File(...)):
    # Save the uploaded file temporarily
    pdf_path = os.path.join(os.getcwd(), "temp/temp_uploaded.pdf")
    with open(pdf_path, "wb") as f:
        f.write(await pdf.read())
    
    # Generate transcript from the uploaded PDF
    generate_transcript(pdf_path)
    
    # After transcript generation, you can choose to return a generated file or just a success message.
    # If you want to send back the generated transcript file (assuming it's saved as 'transcript.txt')
    transcript_path = os.path.join(os.getcwd(), "output/extracted_text.txt")
    
    return FileResponse(transcript_path, media_type="text/plain", filename="transcript.txt")

# Run the FastAPI app with Uvicorn when executed directly
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
