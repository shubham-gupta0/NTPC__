import csv
import os
import aiofiles
from docx import Document
from fastapi import FastAPI, Form, File, UploadFile, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from werkzeug.utils import secure_filename
from config import *
from utils.generate_transcript import generate_transcript
import threading
from pathlib import Path
app = FastAPI()

# Middleware for sessions
app.add_middleware(SessionMiddleware, secret_key="your-secret-key")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

BASE_DIR = Path(__file__).resolve().parent
UPLOAD_FOLDER = BASE_DIR / 'uploads'
OUTPUT_FOLDER = BASE_DIR /  'output'

UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)
OUTPUT_FOLDER.mkdir(parents=True, exist_ok=True)
# Templates and static files
templates = Jinja2Templates(directory=BASE_DIR / 'templates')

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):    
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/login")
async def login(request: Request, username: str = Form(...), password: str = Form(...)):
    if username == "admin" and password == "admin":
        response = RedirectResponse(url="/dashboard", status_code=302)
        request.session["logged_in"] = True
        return response
    else:
        raise HTTPException(status_code=400, detail="Invalid credentials")
@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    if not request.session.get("logged_in"):
        return RedirectResponse(url="/login", status_code=302)
    return templates.TemplateResponse("dashboard.html", {"request": request})


@app.get("/task1", response_class=HTMLResponse)
async def create_task_page(request: Request):
    return templates.TemplateResponse("create_task.html", {"request": request})

@app.post("/task1")
async def create_task(
    request: Request,
    tender_ref: str = Form(...),
    tender_title: str = Form(...),
    validity_date: str = Form(...),
    pdf_file: UploadFile = File(...),
   
):  
    print(tender_ref, tender_title, validity_date)
    pdf_file_path = UPLOAD_FOLDER / secure_filename(pdf_file.filename)
    request.session['tender_ref'] = tender_ref
    request.session['tender_title'] = tender_title
    request.session['validity_date'] = validity_date
    # Save the uploaded file
    async with aiofiles.open(pdf_file_path, "wb") as f:
        await f.write(await pdf_file.read())
    request.session['pdf_file'] = pdf_file.filename
    return RedirectResponse(url="/upload_master_document", status_code=302)

@app.get("/upload_master_document", response_class=HTMLResponse)
async def upload_master_document_page(request: Request):
    return templates.TemplateResponse("upload_master_document.html", {"request": request})


@app.post("/upload_master_document")
async def upload_master_document(
    request: Request ,
    master_pdf: UploadFile = File(...)
):
    master_pdf_path = UPLOAD_FOLDER / secure_filename(master_pdf.filename)
    # Save the uploaded file
    async with aiofiles.open(master_pdf_path, "wb") as f:
        await f.write(await master_pdf.read())
    request.session["master_pdf"] = master_pdf.filename
    return RedirectResponse(url="/add_bids", status_code=302)


@app.get("/add_bids", response_class=HTMLResponse)
async def add_bids_page(request: Request):
    bids = request.session.get("bids", [])
    return templates.TemplateResponse("add_bids.html", {"request": request, "bids": bids})

@app.post("/add_bids")
async def add_bids(
    request: Request,
    bid_name: str = Form(...), 
    bid_pdf: UploadFile = File(...)
):  
    print("CALLING ADD BIDS")
    bid_pdf_path = UPLOAD_FOLDER / secure_filename(bid_pdf.filename)
    input_filename = os.path.splitext(bid_pdf.filename)[0]
    # Generate transcript asynchronously
    def process_transcript():
        try:
            print("GENERATING TRANSCRIPT")
            generate_transcript(input_filename, bid_pdf_path)
            print("TRANSCRIPT GENERATED")
        except Exception as e:
            # Log the error (could be replaced with proper logging)
            print(f"Error generating transcript for ID {id}: {e}")
    
    # Save the uploaded file
    async with aiofiles.open(bid_pdf_path, "wb") as f:
        await f.write(await bid_pdf.read())
        # Start the transcript generation process in a separate thread
        print("Starting transcript generation process")
        threading.Thread(target=process_transcript).start()
    if "bids" not in request.session:
        request.session["bids"] = []
    request.session["bids"].append({"name": bid_name, "file": bid_pdf.filename})
    return RedirectResponse(url="/add_bids", status_code=302)


@app.post("/delete_bid/{bid_index}")
async def delete_bid(bid_index: int, request: Request):
    bids = request.session.get("bids", [])
    if 0 <= bid_index < len(bids):
        deleted_bid = bids.pop(bid_index)
        bid_pdf_path = UPLOAD_FOLDER / deleted_bid["file"]
        if bid_pdf_path.exists():
            bid_pdf_path.unlink()
        request.session["bids"] = bids
        return RedirectResponse(url="/add_bids", status_code=302)
    else:
        raise HTTPException(status_code=404, detail="Bid not found")


@app.get("/bidder_details", response_class=HTMLResponse)
async def bidder_details_page(request: Request):
    bids = request.session.get("bids", [])
    for bid in bids:
        input_filename = os.path.splitext(bid["file"])[0]
        print(input_filename)
        transcript_path = OUTPUT_FOLDER / f"comparison_result_{input_filename}.pdf"  # Changed from .docx to .pdf
        bid["transcript"] = transcript_path.exists()
    return templates.TemplateResponse("bidder_details.html", {"request": request, "bids": bids, "route_name": "bidder_details"})


@app.get("/output/{filename}")
async def get_output_file(filename: str):
    # Secure the filename and remove the extension
    print(filename)
    # input_filename = os.path.splitext(secure_filename(filename))[0]
    file_path = OUTPUT_FOLDER / f"{filename}"  # Changed from .docx to .pdf
    if file_path.exists():
        return FileResponse(file_path, media_type='application/pdf')  # Set the correct MIME type for PDF
    else:
        raise HTTPException(status_code=404, detail="File not found")
    
@app.get("/uploads/{filename}")
async def uploaded_file(filename: str):
    # Secure the filename
    filename = secure_filename(filename)
    file_path = UPLOAD_FOLDER / filename

    # Debug statements
    print(f"UPLOAD_FOLDER is: {UPLOAD_FOLDER}")
    print(f"Attempting to serve file: {filename}")
    print(f"Full file path: {file_path}")
    print(f"File exists: {file_path.exists()}")

    if file_path.exists():
        print(f"Serving file from: {file_path}")
        return FileResponse(file_path)
    else:
        print(f"File not found at: {file_path}")
        raise HTTPException(status_code=404, detail="File not found")
@app.get("/show_transcript/{bid_name}")
async def show_transcript(bid_name: str):
    # Secure the bid name and remove the extension
    input_filename = os.path.splitext(secure_filename(bid_name))[0]
    print(input_filename)
    transcript_path = OUTPUT_FOLDER / f"comparison_result_{input_filename}.docx"
    if transcript_path.exists():
        document = Document(transcript_path)
        html_content = "".join(
            f"<h{''.join(filter(str.isdigit, para.style.name)) or '1'}>{para.text}</h>" if para.style.name.startswith("Heading") else f"<p>{para.text}</p>"
            for para in document.paragraphs
        )
        return JSONResponse({"success": True, "content": html_content})
    else:
        raise HTTPException(status_code=404, detail="Transcript not found")
    
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

@app.get("/transcript/{bid_name}", response_class=HTMLResponse)
async def view_transcript(request: Request, bid_name: str):
    input_filename = os.path.splitext(secure_filename(bid_name))[0]
    
    # Paths to CSV files
    insertions_csv_path = OUTPUT_FOLDER / f"insertions_{input_filename}.csv"
    deletions_csv_path = OUTPUT_FOLDER / f"deletions_{input_filename}.csv"
    
    # Read Insertions CSV
    insertions = []
    if insertions_csv_path.exists():
        with open(insertions_csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            insertions = list(reader)
    
    # Read Deletions CSV
    deletions = []
    if deletions_csv_path.exists():
        with open(deletions_csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            deletions = list(reader)
    
    # Paths to PDFs
    original_pdf_path = UPLOAD_FOLDER / f"{input_filename}.pdf"
    generated_pdf_path = OUTPUT_FOLDER / f"comparison_result_{input_filename}.pdf"
    
    # Check if PDFs exist
    original_pdf_exists = original_pdf_path.exists()
    generated_pdf_exists = generated_pdf_path.exists()
    print(original_pdf_exists, generated_pdf_exists)
    return templates.TemplateResponse(
        "transcript.html",
        {
            "request": request,
            "bid_name": bid_name,
            "insertions": insertions,
            "deletions": deletions,
            "original_pdf_url": f"/uploads/{original_pdf_path.name}" if original_pdf_exists else None,
            "generated_pdf_url": f"/output/{generated_pdf_path.name}" if generated_pdf_exists else None
        }
    )
    
    
# Run the FastAPI app with Uvicorn when executed directly
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
