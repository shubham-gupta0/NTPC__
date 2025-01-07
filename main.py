import csv
from datetime import datetime
import os
import aiofiles
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    DateTime,
    BigInteger,
    ForeignKey,
    JSON,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func
from sqlalchemy import text

# from docx import Document
from fastapi import FastAPI, Form, File, UploadFile, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from werkzeug.utils import secure_filename
from config import *
from utils.generate_transcript import generate_transcript
from utils.generateStandardText import generate_standard
import threading
from pathlib import Path
from custom_parser import parse_metadata_file
from passlib.context import CryptContext

# CHANGE THE DATABASE URL
DATABASE_URL = "sqlite+aiosqlite:///database/app.db"
engine = create_async_engine(DATABASE_URL, echo=True)
Base = declarative_base()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    username = Column(String(50), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    email = Column(String(100), unique=True, nullable=False)
    role = Column(Integer, nullable=False, default=0)  # 0 = user, 1 = admin
    total_storage_used = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Tender(Base):
    __tablename__ = "tenders"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    name = Column(Text, nullable=False)
    valid_until = Column(DateTime(timezone=True), nullable=False)
    status = Column(Integer, nullable=False, default=0)  # 0 = open, 1 = closed
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now())


class PdfFile(Base):
    __tablename__ = "pdffiles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tender_id = Column(
        Integer, ForeignKey("tenders.id", ondelete="CASCADE"), nullable=False
    )
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    file_name = Column(String(255), nullable=False)
    file_size = Column(BigInteger, nullable=False)
    file_path = Column(String(255), nullable=False)
    uploaded_at = Column(DateTime(timezone=True), server_default=func.now())


class Transcript(Base):
    __tablename__ = "transcripts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    pdf_id = Column(
        Integer, ForeignKey("pdffiles.id", ondelete="CASCADE"), nullable=False
    )
    file_path = Column(String(255), nullable=False)
    errors = Column(JSON, nullable=True)  # use JSON for storing error data
    status = Column(
        Integer, nullable=False, default=0
    )  # 0 = Pending, 1 = Fixed, 2 = Rejected
    decision = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now())


class MetaFile(Base):
    __tablename__ = "metafiles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    pdf_id = Column(
        Integer, ForeignKey("pdffiles.id", ondelete="CASCADE"), nullable=False
    )
    file_path = Column(String(255), nullable=False)
    status = Column(
        Integer, nullable=False, default=0
    )  # 0 = Pending, 1 = Fixed, 2 = Rejected
    created_at = Column(DateTime(timezone=True), server_default=func.now())


async_session = sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
# fastApi sertup
app = FastAPI()
# Middleware for sessions
app.add_middleware(SessionMiddleware, secret_key="your-secret-key")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


BASE_DIR = Path(__file__).resolve().parent
UPLOAD_FOLDER = BASE_DIR / "uploads"
OUTPUT_FOLDER = BASE_DIR / "output"

UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)
OUTPUT_FOLDER.mkdir(parents=True, exist_ok=True)
# Templates and static files
templates = Jinja2Templates(directory=BASE_DIR / "templates")
hyperlink_templates = Jinja2Templates(directory=BASE_DIR / "hyperlink_outputs")
static = StaticFiles(directory=BASE_DIR / "static")
app.mount("/static", static)


# Database utilities
async def get_db():
    async with async_session() as session:
        yield session


@app.on_event("startup")
async def on_startup():
    async with engine.begin() as conn:
        # Create tables if they don't exist
        await conn.run_sync(Base.metadata.create_all)


@app.on_event("shutdown")
async def on_shutdown():
    await engine.dispose()


# Routes
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return RedirectResponse(url="/login", status_code=302)


"""    LOGIC FOR LOGIN PAGE        """


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


@app.post("/login")
async def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    # Check if the user exists
    print(username, password)
    check_user = await db.execute(
        text("SELECT * FROM users WHERE username = :username"), {"username": username}
    )
    user = check_user.fetchone()
    if not user:
        raise HTTPException(status_code=400, detail="No user found with that username")
    print(user)
    print(user.password_hash)
    # Check if the password is correct with the hashed password
    if not pwd_context.verify(password, user.password_hash):
        raise HTTPException(status_code=400, detail="Invalid credentials")

    # check if user is admin
    if user.role == 1:
        request.session["admin"] = True
    # store user in session
    request.session["userid"] = user.id
    request.session["logged_in"] = True

    return RedirectResponse(url="/dashboard", status_code=302)


""" ADMIN   LOGIC FOR ADDING NEW USER  only admin can add new user      """


# middleware for sessions if session admin is true then user is admin


async def admin_only_middleware(request: Request, call_next):
    # Check if the user is an admin
    print(request.session.get("admin"))
    is_admin = request.session.get("admin") == 1  # 1 = admin, 0 = user

    # Protect admin routes
    if not is_admin:
        raise HTTPException(status_code=403, detail="Only admins can access this route")

    return await call_next(request)


# Add user
@app.post("/add_user")
async def add_user(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    email: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    is_admin = request.session.get("admin") == 1  # 1 = admin, 0 = user

    # Protect admin routes
    if not is_admin:
        raise HTTPException(status_code=403, detail="Only admins can access this route")

    # Check for duplicate users
    print(username, password, email)

    existing_user = await db.execute(
        text("SELECT * FROM users WHERE username = :username OR email = :email"),
        {"username": username, "email": email},
    )
    print(existing_user)
    if existing_user.fetchone():
        raise HTTPException(status_code=400, detail="User already exists")
    # Hash the password
    hashed_password = pwd_context.hash(password)
    print(hashed_password)
    # Add the new user
    await db.execute(
        text(
            "INSERT INTO users (username, password_hash, email) VALUES (:username, :password_hash, :email)"
        ),
        {"username": username, "password_hash": hashed_password, "email": email},
    )
    await db.commit()

    return JSONResponse(content={"message": "User added successfully"})


# View all users
@app.get(
    "/all_users",
    response_class=HTMLResponse,
)
async def all_users(request: Request, db: AsyncSession = Depends(get_db)):
    is_admin = request.session.get("admin") == 1  # 1 = admin, 0 = user

    # Protect admin routes
    if not is_admin:
        raise HTTPException(status_code=403, detail="Only admins can access this route")

    # Only retrieve users with role='0', ordered by descending ID
    result = await db.execute(
        text("SELECT * FROM users WHERE role = '0' ORDER BY id DESC")
    )
    users = result.fetchall()
    print(users)
    return templates.TemplateResponse(
        "all_users.html", {"request": request, "users": users}
    )


@app.post("/update_user", response_class=JSONResponse)
async def update_user(
    request: Request,
    user_id: int = Form(...),
    username: str = Form(...),
    email: str = Form(...),
    role: str = Form(...),  # 'admin' or 'user'
    password: str = Form(None),  # Optional
    db: AsyncSession = Depends(get_db),
):
    is_admin = request.session.get("admin") == 1
    if not is_admin:
        raise HTTPException(status_code=403, detail="Only admins can access this route")
    # Validate role
    if role not in ["admin", "user"]:
        raise HTTPException(status_code=400, detail="Invalid role selected.")

    # Check if user exists
    user = await db.execute(
        text("SELECT * FROM users WHERE id = :user_id"),
        {"user_id": user_id},
    )
    user = user.fetchone()
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")

    # Check for duplicate username or email
    existing_user = await db.execute(
        text(
            "SELECT * FROM users WHERE (username = :username OR email = :email) AND id != :user_id"
        ),
        {"username": username, "email": email, "user_id": user_id},
    )
    if existing_user.fetchone():
        raise HTTPException(status_code=400, detail="Username or email already exists.")

    # Prepare the update statement
    update_fields = {"username": username, "email": email, "role": role}

    if password:
        hashed_password = pwd_context.hash(password)
        update_fields["password_hash"] = hashed_password

    # Dynamically build the SET part of the SQL statement
    set_clause = ", ".join([f"{key} = :{key}" for key in update_fields.keys()])

    await db.execute(
        text(f"UPDATE users SET {set_clause} WHERE id = :user_id"),
        {**update_fields, "user_id": user_id},
    )
    await db.commit()

    return JSONResponse(content={"message": "User updated successfully."})


# CLear storage for a user
@app.post("/clear_storage/{user_id}", dependencies=[Depends(admin_only_middleware)])
async def clear_storage(user_id: int, db: AsyncSession = Depends(get_db)):
    # TODO: CASCADE DELETE ALL FILES UPLOADED BY THE USER delete all files uploaded by the user Metafiles and transcripts
    # Check if user exists
    user = await db.execute(
        "SELECT * FROM users WHERE id = :user_id", {"user_id": user_id}
    )
    user = user.fetchone()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    # from pdffiles table delete all files uploaded by the user
    pdfs = await db.execute(
        "SELECT file_path FROM pdffiles WHERE user_id = :user_id",
        {"user_id": user_id},
    )
    pdfs = pdfs.fetchall()
    for pdf in pdfs:
        pdf_path = Path(pdf[0])
        if pdf_path.exists():
            pdf_path.unlink()

    result = await db.execute(
        "DELETE FROM pdffiles WHERE user_id = :user_id",
        {"user_id": user_id},
    )
    # update total_storage_used to 0
    result = await db.execute(
        "UPDATE users SET total_storage_used = 0 WHERE id = :user_id",
        {"user_id": user_id},
    )


"""    DASHBOARD PAGE        """


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    if not request.session.get("logged_in"):
        return RedirectResponse(url="/login", status_code=302)
    # if user is admin then show admin dashboard
    print(request.session.get("admin"))
    if request.session.get("admin"):
        return templates.TemplateResponse("admin_dashboard.html", {"request": request})

    else:
        return templates.TemplateResponse("dashboard.html", {"request": request})


@app.get("/compare1", response_class=HTMLResponse)
async def doc1(request: Request):
    return templates.TemplateResponse("doc1_dashboard.html", {"request": request})


@app.get("/task1", response_class=HTMLResponse)
async def create_task_page(request: Request):
    return templates.TemplateResponse("create_task.html", {"request": request})


@app.post("/task1")
async def create_task_tender(
    request: Request,
    tender_ref: str = Form(...),
    tender_title: str = Form(...),
    validity_date: str = Form(...),
    pdf_file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    # BANK LIST
    # Check file size (in MB)
    pdf_file_size = len(await pdf_file.read()) / (1024 * 1024)

    # Fetch the user's storage information
    user = await db.execute(
        text("SELECT * FROM users WHERE id = :user_id"),
        {"user_id": request.session["userid"]},
    )
    user = user.fetchone()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # fix it available_space = 1GB - user.total_storage_used
    available_space = 1024 - user.total_storage_used
    # Check if the user has enough space
    if pdf_file_size > available_space:
        raise HTTPException(
            status_code=400, detail="Not enough storage space available"
        )
    # 4. Parse validity_date to datetime object
    try:
        validity_date = datetime.strptime(validity_date, '%Y-%m-%d')
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD.")

    # Save the file
    pdf_file_path = UPLOAD_FOLDER / secure_filename(pdf_file.filename)
    async with aiofiles.open(pdf_file_path, "wb") as f:
        await f.write(await pdf_file.read())
    #set validity
    # Add the bid to the database
    new_bid = Tender(name=tender_title, valid_until=validity_date, user_id=user.id)
    print(new_bid)
    db.add(new_bid)

    # Update the user's used storage
    new_used_storage = user.total_storage_used + pdf_file_size
    await db.execute(
        text(
            "UPDATE users SET total_storage_used = :new_used_storage WHERE id = :user_id"
        ),
        {"new_used_storage": new_used_storage, "user_id": user.id},
    )

    await db.commit()

    return RedirectResponse(url="/add_bids", status_code=302)


# View tender
@app.get("/view_tender, response_class=HTMLResponse")
async def view_tender(request: Request, db: AsyncSession = Depends(get_db)):
    # for userid get all tenders
    result = await db.execute(
        text("SELECT * FROM tenders WHERE user_id = :user_id ORDER BY id DESC"),
        {"user_id": request.session["userid"]},
    )
    tenders = result.fetchall()
    return templates.TemplateResponse(
        "view_tender.html", {"request": request, "tenders": tenders}
    )


# @app.post("/task1")
# async def create_task(
#     request: Request,
#     tender_ref: str = Form(...),
#     tender_title: str = Form(...),
#     validity_date: str = Form(...),
#     pdf_file: UploadFile = File(...),
# ):

#     pdf_file_path = UPLOAD_FOLDER / secure_filename(pdf_file.filename)
#     request.session["tender_ref"] = tender_ref
#     request.session["tender_title"] = tender_title
#     request.session["validity_date"] = validity_date
#     # Save the uploaded file
#     async with aiofiles.open(pdf_file_path, "wb") as f:
#         await f.write(await pdf_file.read())
#     request.session["pdf_file"] = pdf_file.filename
#     return RedirectResponse(url="/add_bids", status_code=302)


# @app.get("/upload_master_document", response_class=HTMLResponse)
# async def upload_master_document_page(request: Request):
#     return templates.TemplateResponse("upload_master_document.html", {"request": request})


# @app.post("/upload_master_document")
# async def upload_master_document(
#     request: Request ,
#     master_pdf: UploadFile = File(...)
# ):
#     master_pdf_path = UPLOAD_FOLDER / secure_filename(master_pdf.filename)
#     # Save the uploaded file
#     async with aiofiles.open(master_pdf_path, "wb") as f:
#         await f.write(await master_pdf.read())
#     request.session["master_pdf"] = master_pdf.filename

#     master_input_filename = os.path.splitext(master_pdf.filename)[0]

#     def process_standard():
#         try:
#             print("Building Standard Text")
#             # generate_standard(master_input_filename, master_pdf_path)
#             print("Standard Text GENERATED")
#         except Exception as e:
#             # Log the error (could be replaced with proper logging)
#             print(f"Error generating Standard Form Text")

#     print("Extracting Standard Text")
#     threading.Thread(target=process_standard).start()

#     return RedirectResponse(url="/add_bids", status_code=302)


@app.get("/add_bids", response_class=HTMLResponse)
async def add_bids_page(request: Request):
    bids = request.session.get("bids", [])
    return templates.TemplateResponse(
        "add_bids.html", {"request": request, "bids": bids}
    )


@app.post("/add_bids")
async def add_bids(
    request: Request,
    bid_name: str = Form(...),
    bid_pdf: UploadFile = File(...),
    tender_id: int = Form(...),
    db: AsyncSession = Depends(get_db),
):
    print("CALLING ADD BIDS")
    bid_pdf_path = UPLOAD_FOLDER / secure_filename(bid_pdf.filename)
    input_filename = os.path.splitext(bid_pdf.filename)[0]
    # Check file size (in MB)
    pdf_file_size = len(await bid_pdf_path.read()) / (1024 * 1024)
    user = await db.execute(
        text("SELECT * FROM users WHERE id = :user_id"),
        {"user_id": request.session["userid"]},
    )
    user = user.fetchone()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # fix it available_space = 1GB - user.total_storage_used
    available_space = 1024 - user.total_storage_used
    # Check if the user has enough space
    if pdf_file_size > available_space:
        raise HTTPException(
            status_code=400, detail="Not enough storage space available"
        )

    new_pdf = PdfFile(
        tender_id=tender_id,
        user_id=user.id,
        file_name=input_filename,
        file_size=pdf_file_size,
        file_path=str(bid_pdf_path),
    )
    db.add(new_pdf)
    # Update the user's used storage
    new_used_storage = user.total_storage_used + pdf_file_size
    await db.execute(
        text(
            "UPDATE users SET total_storage_used = :new_used_storage WHERE id = :user_id"
        ),
        {"new_used_storage": new_used_storage, "user_id": user.id},
    )

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
        transcript_path = (
            OUTPUT_FOLDER / f"comparison_result_{input_filename}.pdf"
        )  # Changed from .docx to .pdf
        bid["transcript"] = transcript_path.exists()
        metadata_path = OUTPUT_FOLDER / f"metadata_{input_filename}.txt"
        bid["metadata"] = metadata_path.exists()

    return templates.TemplateResponse(
        "bidder_details.html",
        {"request": request, "bids": bids, "route_name": "bidder_details"},
    )


@app.get("/output/{filename}")
async def get_output_file(filename: str):
    # Secure the filename and remove the extension
    print(filename)
    # input_filename = os.path.splitext(secure_filename(filename))[0]
    file_path = OUTPUT_FOLDER / f"{filename}"  # Changed from .docx to .pdf
    if file_path.exists():
        return FileResponse(
            file_path, media_type="application/pdf"
        )  # Set the correct MIME type for PDF
    else:
        raise HTTPException(status_code=404, detail="File not found")


@app.get("/uploads/{filename}")
async def uploaded_file(filename: str):
    # Secure the filename
    filename = secure_filename(filename)
    file_path = UPLOAD_FOLDER / filename

    # Debug statements
    # print(f"UPLOAD_FOLDER is: {UPLOAD_FOLDER}")
    # print(f"Attempting to serve file: {filename}")
    # print(f"Full file path: {file_path}")
    print(f"File exists: {file_path.exists()}")

    if file_path.exists():
        print(f"Serving file from: {file_path}")
        return FileResponse(file_path)
    else:
        print(f"File not found at: {file_path}")
        raise HTTPException(status_code=404, detail="File not found")


# @app.get("/show_transcript/{bid_name}")
# async def show_transcript(bid_name: str):
#     # Secure the bid name and remove the extension
#     input_filename = os.path.splitext(secure_filename(bid_name))[0]
#     print(input_filename)
#     transcript_path = OUTPUT_FOLDER / f"comparison_result_{input_filename}.docx"
#     if transcript_path.exists():
#         document = Document(transcript_path)
#         html_content = "".join(
#             f"<h{''.join(filter(str.isdigit, para.style.name)) or '1'}>{para.text}</h>" if para.style.name.startswith("Heading") else f"<p>{para.text}</p>"
#             for para in document.paragraphs
#         )
#         return JSONResponse({"success": True, "content": html_content})
#     else:
#         raise HTTPException(status_code=404, detail="Transcript not found")


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
    return JSONResponse(
        content={
            "message": f"Transcript generation process has been started for ID {id}."
        }
    )


# View to display the metadata for a specific bid
@app.get("/metadata/{filename}", name="metadata", response_class=HTMLResponse)
async def metadata(request: Request, filename: str):
    bid_name = filename  # Or fetch the actual bid name based on filename
    # read the txt file from output folder named as metadata_{filename}.txt
    # print(filename)
    filename = os.path.splitext(secure_filename(filename))[0]
    metadata_path = OUTPUT_FOLDER / f"metadata_{filename}.txt"
    print(metadata_path)
    metadata = parse_metadata_file(metadata_path)
    # print (metadata)

    return templates.TemplateResponse(
        "metadata.html",
        {"request": request, "metadata": metadata, "bid_name": bid_name},
    )


@app.get("/transcript/{bid_name}", response_class=HTMLResponse)
async def view_transcript(request: Request, bid_name: str):
    input_filename = os.path.splitext(secure_filename(bid_name))[0]

    # Paths to CSV files
    insertions_csv_path = OUTPUT_FOLDER / f"insertions_{input_filename}.csv"
    deletions_csv_path = OUTPUT_FOLDER / f"deletions_{input_filename}.csv"

    # Read Insertions CSV
    insertions = []
    if insertions_csv_path.exists():
        with open(insertions_csv_path, "r", encoding="utf-8") as f:
            for line in f:
                insertions.append(line)

    # Read Deletions CSV
    deletions = []
    if deletions_csv_path.exists():
        with open(deletions_csv_path, "r", encoding="utf-8") as f:
            for line in f:
                deletions.append(line)

    # Paths to PDFs
    original_pdf_path = UPLOAD_FOLDER / f"{input_filename}.pdf"
    generated_pdf_path = OUTPUT_FOLDER / f"comparison_result_{input_filename}.pdf"

    # Check if PDFs exist
    original_pdf_exists = original_pdf_path.exists()
    generated_pdf_exists = generated_pdf_path.exists()
    # print(original_pdf_exists, generated_pdf_exists)

    return templates.TemplateResponse(
        "transcript.html",
        {
            "request": request,
            "bid_name": bid_name,
            "insertions": insertions,
            "deletions": deletions,
            "original_pdf_url": (
                f"/uploads/{original_pdf_path.name}" if original_pdf_exists else None
            ),
            "generated_pdf_url": (
                f"/output/{generated_pdf_path.name}" if generated_pdf_exists else None
            ),
        },
    )

    # return hyperlink_templates.TemplateResponse(
    #     f"hyperlink_{str(bid_name)[:-4]}.html",
    #     {"request": request}
    # )


# Run the FastAPI app with Uvicorn when executed directly
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
