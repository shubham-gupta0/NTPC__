import os
from fastapi import FastAPI, File, UploadFile, Form
from fastapi.responses import JSONResponse
from config import *
from utils.generate_transcript import generate_transcript
import threading

app = FastAPI()

@app.get("/")
def read_root():
    return {"message": "Welcome to the PDF Transcript Generator API!"}

@app.post("/generate-transcript/")
async def create_transcript(id: str = Form(...), pdf: UploadFile = File(...)):
    """
    API Endpoint to initiate transcript generation for the uploaded PDF.
    Args:
        id (str): Unique identifier for the request.
        pdf (UploadFile): Uploaded PDF file.
    """
    # Create the temp directory if it doesn't exist
    os.makedirs("temp", exist_ok=True)
    
    # Save the uploaded file with the ID in its name
    pdf_path = os.path.join("temp", f"temp_uploaded_{id}.pdf")
    with open(pdf_path, "wb") as f:
        f.write(await pdf.read())
    
    # Run the transcript generation process in a separate thread
    def process_transcript():
        try:
            generate_transcript(id, pdf_path)
        except Exception as e:
            # Log the error (could be replaced with proper logging)
            print(f"Error generating transcript for ID {id}: {e}")
    
    threading.Thread(target=process_transcript).start()
    
    # Return an immediate response
    return JSONResponse(content={"message": f"Transcript generation process has been started for ID {id}."})

# Run the FastAPI app with Uvicorn when executed directly
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
