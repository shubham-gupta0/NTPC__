import asyncio
import csv
from datetime import datetime
import os
import shutil
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
from fastapi import FastAPI, Form, File, UploadFile, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from werkzeug.utils import secure_filename
from config import *
from csv_parser import parse_csv_file
from utils.generate_transcript import generate_transcript
from utils.generateStandardText import generate_standard
import threading
from pathlib import Path
from custom_parser import parse_metadata_file
from passlib.context import CryptContext
from fastapi.staticfiles import StaticFiles


# CHANGE THE DATABASE URL
DATABASE_URL = "sqlite+aiosqlite:///database/app.db"
engine = create_async_engine(DATABASE_URL, echo=True)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
Base = declarative_base()


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

    id = Column(Integer, primary_key=True, autoincrement=True, nullable=False)
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
app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/output", StaticFiles(directory=str(OUTPUT_FOLDER)), name="output")
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


# Middle ware dependencies for session
async def is_logged_in(request: Request):
    # raise exception if user is not logged in
    if not request.session.get("logged_in"):
        raise HTTPException(status_code=401, detail="Unauthorized")
    return request.session.get("logged_in")


async def is_admin(request: Request):
    # raise exception if user is not admin
    if not request.session.get("admin"):
        raise HTTPException(status_code=401, detail="Unauthorized access Admin only")
    return request.session.get("admin")


# Routes
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    if request.session.get("logged_in"):
        return RedirectResponse(url="/dashboard", status_code=302)
    return RedirectResponse(url="/login", status_code=302)


"""    LOGIC FOR LOGIN PAGE        """


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    # Check if the user is already logged in
    print(request.session)
    print("HERE")
    if request.session.get("logged_in"):
        return RedirectResponse(url="/dashboard", status_code=302)
    return templates.TemplateResponse("login.html", {"request": request})


@app.post("/login")
async def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    # Check if the user exists
    check_user = await db.execute(
        text("SELECT * FROM users WHERE username = :username"), {"username": username}
    )
    user = check_user.fetchone()
    if not user:
        if username == "admin" and password == "admin":
            request.session["admin"] = True
            request.session["logged_in"] = True
            request.session["userid"] = 0
            return RedirectResponse(url="/dashboard", status_code=302)

        raise HTTPException(status_code=400, detail="No user found with that username")

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


@app.get("/logout")
async def logout(request: Request):
    request.session.clear()  # Clear all session data
    return RedirectResponse(url="/login", status_code=303)  # Redirect to login page


""" ADMIN   LOGIC FOR ADDING NEW USER  only admin can add new user      """


# Add user
@app.post("/add_user", dependencies=[Depends(is_admin), Depends(is_logged_in)])
async def add_user(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    email: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    existing_user = await db.execute(
        text("SELECT * FROM users WHERE username = :username OR email = :email"),
        {"username": username, "email": email},
    )
    if existing_user.fetchone():
        raise HTTPException(status_code=400, detail="User already exists")
    # Hash the password
    hashed_password = pwd_context.hash(password)
    # Add the new user
    await db.execute(
        text(
            "INSERT INTO users (username, password_hash, email) VALUES (:username, :password_hash, :email)"
        ),
        {"username": username, "password_hash": hashed_password, "email": email},
    )
    await db.commit()

    # Retrieve the newly created user's ID
    user_result = await db.execute(
        text("SELECT id FROM Users WHERE username = :username AND email = :email"),
        {"username": username, "email": email},
    )
    new_user_id = user_result.scalar_one()

    # Create a directory for the user
    user_folder = UPLOAD_FOLDER / str(new_user_id)
    user_folder.mkdir(parents=True, exist_ok=True)

    return JSONResponse(content={"message": "User added successfully"})


# View all users
@app.get(
    "/all_users",
    response_class=HTMLResponse,
    dependencies=[Depends(is_admin), Depends(is_logged_in)],
)
async def all_users(request: Request, db: AsyncSession = Depends(get_db)):
    is_admin = request.session.get("admin") == 1  # 1 = admin, 0 = user

    # Protect admin routes
    if not is_admin:
        raise HTTPException(status_code=403, detail="Only admins can access this route")

    # Only retrieve users with role='0', ordered by descending ID
    result = await db.execute(text("SELECT * FROM users ORDER BY id ASC"))
    users = result.fetchall()
    print(users)
    return templates.TemplateResponse(
        "all_users.html", {"request": request, "users": users}
    )


@app.post(
    "/update_user",
    response_class=JSONResponse,
    dependencies=[Depends(is_admin), Depends(is_logged_in)],
)
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
    # Map role string to integer
    role_value = 1 if role == "admin" else 0
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
    update_fields = {"username": username, "email": email, "role": role_value}

    if password:
        hashed_password = pwd_context.hash(password)
        update_fields["password_hash"] = hashed_password

    # Dynamically build the SET part of the SQL statement
    set_clause = ", ".join([f"{key} = :{key}" for key in update_fields.keys()])
    print(set_clause)
    # Update the user
    await db.execute(
        text(f"UPDATE users SET {set_clause} WHERE id = :user_id"),
        {**update_fields, "user_id": user_id},
    )
    await db.commit()

    return JSONResponse(content={"message": "User updated successfully."})


"""    DASHBOARD PAGE        """


@app.get(
    "/dashboard", response_class=HTMLResponse, dependencies=[Depends(is_logged_in)]
)
async def dashboard(request: Request):
    # if user is admin then show admin dashboard
    if request.session.get("admin"):
        return templates.TemplateResponse("admin_dashboard.html", {"request": request})

    else:
        return templates.TemplateResponse("dashboard.html", {"request": request})


@app.get("/EMD_BG", response_class=HTMLResponse, dependencies=[Depends(is_logged_in)])
async def doc1(request: Request):

    return templates.TemplateResponse("EMD_dashboard.html", {"request": request})


""" Tender LOGIC TO ADD, VIEW AND DELETE TENDER """


@app.get("/tender", response_class=HTMLResponse,dependencies=[Depends(is_logged_in)])
async def create_task_page(request: Request):
    if not request.session.get("logged_in"):
        return RedirectResponse(url="/login", status_code=302)
    return templates.TemplateResponse("create_tender.html", {"request": request})


@app.post("/tender",dependencies=[Depends(is_logged_in)])
async def create_task_tender(
    request: Request,
    tender_ref: str = Form(...),
    tender_title: str = Form(...),
    validity_date: str = Form(...),
    db: AsyncSession = Depends(get_db),
):

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
    if available_space < 2:
        raise HTTPException(
            status_code=400,
            detail="Not enough storage space available kindly delete some files",
        )
    # 4. Parse validity_date to datetime object
    try:
        validity_date = datetime.strptime(validity_date, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(
            status_code=400, detail="Invalid date format. Use YYYY-MM-DD."
        )

    # Add the bid to the database
    new_tender = Tender(name=tender_title, valid_until=validity_date, user_id=user.id)
    print(new_tender)
    print(new_tender.id)
    print(new_tender.name)
    print(new_tender.valid_until)
    db.add(new_tender)
    await db.commit()
    return RedirectResponse(url=f"/add_bids/{new_tender.id}", status_code=302)


@app.get("/add_bids/{tender_id}", response_class=HTMLResponse,dependencies=[Depends(is_logged_in)])
async def add_bids_page(
    request: Request,
    tender_id: int,
    db: AsyncSession = Depends(get_db),
):
    """
    Render the Add Bids page. If a tender_id is provided via path parameters,
    include it in the template context.
    """
    print("CALLING ADD BIDS PAGE")
    print(tender_id)
    if not request.session.get("logged_in"):
        return RedirectResponse(url="/login", status_code=302)

    user_id = request.session.get("userid")
    # TODO: search for tender id for that particular user and if not found ask to create one
    # Fetch all bids (PDF files) for the tender and the current user
    bids_result = await db.execute(
        text(
            "SELECT * FROM pdffiles WHERE tender_id = :tender_id AND user_id = :user_id"
        ),
        {"tender_id": tender_id, "user_id": user_id},
    )
    bids = bids_result.fetchall()
    print(bids)
    return templates.TemplateResponse(
        "add_bids.html", {"request": request, "bids": bids, "tender_id": tender_id}
    )


@app.post("/add_bids/{tender_id}",dependencies=[Depends(is_logged_in)])
async def add_bids(
    request: Request,
    tender_id: int,
    bid_name: str = Form(...),
    bid_pdf: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    bid_pdf_path = UPLOAD_FOLDER / secure_filename(bid_pdf.filename)
    input_filename = os.path.splitext(bid_pdf.filename)[0]

    # Reset file pointer after reading for size
    bid_pdf.file.seek(0)

    # Read file content once
    content = await bid_pdf.read()

    # Check file size (in MB)
    pdf_file_size = len(content) / (1024 * 1024)

    user = await db.execute(
        text("SELECT * FROM users WHERE id = :user_id"),
        {"user_id": request.session.get("userid")},
    )
    user = user.fetchone()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Calculate available space (1GB = 1024MB)
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
    await db.commit()
    await db.refresh(new_pdf)

    # Update the user's used storage
    new_used_storage = user.total_storage_used + pdf_file_size
    await db.execute(
        text(
            "UPDATE users SET total_storage_used = :new_used_storage WHERE id = :user_id"
        ),
        {"new_used_storage": new_used_storage, "user_id": user.id},
    )
    await db.commit()

    async def process_transcript():
        try:
            print("calling generate transcript")
            trans_path, metadata_path, ins_csv, del_csv = generate_transcript(
                input_filename, bid_pdf_path, user.id
            )
            print("Transcript Generated",trans_path)
            # Store a dictionary (not JSONB) in the errors field
            new_transcript = Transcript(
                pdf_id=new_pdf.id,
                file_path=str(trans_path),
                decision="0",  # or any string you prefer
                errors={},  # store an empty dict or any valid dict
            )
            db.add(new_transcript)
            await db.commit()
            new_meta = MetaFile(
                pdf_id=new_pdf.id,
                file_path=str(metadata_path),
            )
            db.add(new_meta)
            await db.commit()
            # --- Process Insertions CSV ---
            if isinstance(ins_csv, str):
                ins_path = Path(ins_csv)
                if ins_path.exists():
                    insertions_list = parse_csv_file(ins_csv)
                else:
                    insertions_list = [ins_csv]
            elif isinstance(ins_csv, list):
                insertions_list = ins_csv
            else:
                insertions_list = [str(ins_csv)]

            for row in insertions_list:
                row_data = row  # each row is a string from our parser
                decision_val = 0
                await db.execute(
                    text(
                        "INSERT INTO CsvErrors (tender_id, user_id, row_data, error_type, decision) "
                        "VALUES (:tender_id, :user_id, :row_data, :error_type, :decision)"
                    ),
                    {
                        "tender_id": tender_id,
                        "user_id": user.id,
                        "row_data": row_data,
                        "error_type": "insertion",
                        "decision": decision_val,
                    },
                )

            # --- Process Deletions CSV ---
            if isinstance(del_csv, str):
                del_path = Path(del_csv)
                if del_path.exists():
                    deletion_list = parse_csv_file(del_csv)
                else:
                    deletion_list = [del_csv]
            elif isinstance(del_csv, list):
                deletion_list = del_csv
            else:
                deletion_list = [str(del_csv)]

            for row in deletion_list:
                row_data = row
                decision_val = 0
                await db.execute(
                    text(
                        "INSERT INTO CsvErrors (tender_id, user_id, row_data, error_type, decision) "
                        "VALUES (:tender_id, :user_id, :row_data, :error_type, :decision)"
                    ),
                    {
                        "tender_id": tender_id,
                        "user_id": user.id,
                        "row_data": row_data,
                        "error_type": "deletion",
                        "decision": decision_val,
                    },
                )
            await db.commit()
        except Exception as e:
            print(f"Error generating transcript for ID {tender_id}: {e}")

    # Save the uploaded file
    async with aiofiles.open(bid_pdf_path, "wb") as f:
        await f.write(content)
    # Start the transcript generation in a separate thread
    threading.Thread(target=lambda: asyncio.run(process_transcript())).start()

    return RedirectResponse(url=f"/add_bids/{tender_id}", status_code=302)


@app.get("/view_bids/{pdf_id}", name="view_bids",dependencies=[Depends(is_logged_in)])
async def view_bids(pdf_id: int, request: Request, db: AsyncSession = Depends(get_db)):
    user_id = request.session.get("userid")
    if not user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    result = await db.execute(
        text("SELECT * FROM pdfFiles WHERE id = :pdf_id AND user_id = :user_id"),
        {"pdf_id": pdf_id, "user_id": user_id},
    )
    pdf = result.fetchone()
    print(pdf)
    if not pdf:
        raise HTTPException(status_code=404, detail="File not found")
    file_path = Path(pdf.file_path)
    if file_path.exists():
        return FileResponse(str(file_path))
    raise HTTPException(status_code=404, detail="File not found")


@app.post("/delete_bid/{pdf_id}", name="delete_bid",dependencies=[Depends(is_logged_in)])
async def delete_bids(
    pdf_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    if not request.session.get("logged_in"):
        return RedirectResponse(url="/login", status_code=302)

    user_id = request.session.get("userid")
    if not user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")

    # Fetch the PDF file record
    result = await db.execute(
        text("SELECT * FROM pdffiles WHERE id = :pdf_id AND user_id = :user_id"),
        {"pdf_id": pdf_id, "user_id": user_id},
    )
    pdf = result.fetchone()
    if not pdf:
        raise HTTPException(status_code=404, detail="File not found")

    # Delete the PDF file from the filesystem if it exists
    pdf_file_path = Path(pdf.file_path)
    if pdf_file_path.exists():
        pdf_file_path.unlink()

    # Option 1: If your DB schema supports ON DELETE CASCADE and SQLite foreign keys are enabled,
    # simply deleting the PDF record may delete dependent rows.
    # However, if that's not working you can delete manually.

    # Delete associated transcript records (and meta files)
    await db.execute(
        text("DELETE FROM transcripts WHERE pdf_id = :pdf_id"), {"pdf_id": pdf_id}
    )
    await db.execute(
        text("DELETE FROM metafiles WHERE pdf_id = :pdf_id"), {"pdf_id": pdf_id}
    )

    # Delete associated CSV rows – here we assume the CSV rows belong to this bid
    # (Note: In your schema, CSV tables store tender_id and user_id only.)
    await db.execute(
        text(
            "DELETE FROM CsvErrors WHERE tender_id = :tender_id AND user_id = :user_id AND error_type = 'insertion'"
        ),
        {"tender_id": pdf.tender_id, "user_id": user_id},
    )
    await db.execute(
        text(
            "DELETE FROM CsvErrors WHERE tender_id = :tender_id AND user_id = :user_id AND error_type = 'deletion'"
        ),
        {"tender_id": pdf.tender_id, "user_id": user_id},
    )
    await db.commit()

    # Finally, delete the PDF file record itself
    await db.execute(
        text("DELETE FROM pdffiles WHERE id = :pdf_id"), {"pdf_id": pdf_id}
    )
    await db.commit()

    return RedirectResponse(url=f"/add_bids/{pdf.tender_id}", status_code=302)


@app.get("/bidder_details/{tender_id}", response_class=HTMLResponse,dependencies=[Depends(is_logged_in)])
async def bidder_details_page(
    request: Request, tender_id: int, db: AsyncSession = Depends(get_db)
):
    # Fetch all bids (PDF files) for the given tender
    result = await db.execute(
        text("SELECT * FROM pdffiles WHERE tender_id = :tender_id"),
        {"tender_id": tender_id},
    )
    bids = result.fetchall()

    # Create a list of bid details with transcript and metadata information.
    bids_list = []
    for bid in bids:
        # Check if transcript exists in the database
        transcript_result = await db.execute(
            text("SELECT id FROM Transcripts WHERE pdf_id = :pdf_id"),
            {"pdf_id": bid.id},
        )
        transcript_exists = transcript_result.scalar() is not None
        
        # Check if metadata exists in the database
        meta_result = await db.execute(
            text("SELECT id FROM MetaFiles WHERE pdf_id = :pdf_id"),
            {"pdf_id": bid.id},
        )
        metadata_exists = meta_result.scalar() is not None
        
        bids_list.append(
            {
                "id": bid.id,
                "name": bid.file_name,  # Using file_name as bidder name
                "file": os.path.basename(bid.file_path),  # Just the filename without path
                "transcript": transcript_exists,
                "metadata": metadata_exists,
                "tender_id": bid.tender_id,
            }
        )

    return templates.TemplateResponse(
        "bidder_details.html",
        {
            "request": request,
            "bids": bids_list,
            "tender_id": tender_id,
            "route_name": "bidder_details",
        },
    )


@app.get("/uploaded/{filename}", name="uploaded_file",dependencies=[Depends(is_logged_in)])
async def uploaded_file(filename: str):
    file_path = UPLOAD_FOLDER / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(str(file_path))


# @app.get("/document/{doc_type}/{filename}", name="document")
# async def document_file(doc_type: str, filename: str):
#     # Determine the directory based on doc_type. Here we assume transcripts and metadata are in OUTPUT_FOLDER.
#     if doc_type not in ["transcript", "metadata"]:
#         raise HTTPException(status_code=400, detail="Invalid document type")
#     file_path = OUTPUT_FOLDER / filename
#     if not file_path.exists():
#         raise HTTPException(status_code=404, detail="File not found")
#     return FileResponse(str(file_path))


@app.get("/metadata/{pdf_id}", name="metadata", response_class=HTMLResponse,dependencies=[Depends(is_logged_in)])
async def metadata(request: Request, pdf_id: int, db: AsyncSession = Depends(get_db)):
    # Fetch the metadata content (assumed stored in MetaFiles.file_path column as text)
    meta_result = await db.execute(
        text("SELECT file_path FROM MetaFiles WHERE pdf_id = :pdf_id"),
        {"pdf_id": pdf_id},
    )
    meta_files = meta_result.fetchone()
    if not meta_files:
        raise HTTPException(status_code=404, detail="Metadata not found")
    meta_file_path = Path(meta_files.file_path)
    if not meta_file_path.exists():
        raise HTTPException(status_code=404, detail="Metadata file not found")
    # Parse the metadata file content
    meta_row = parse_metadata_file(meta_file_path)
    if not meta_row:
        raise HTTPException(status_code=404, detail="Metadata not found")

    # Also fetch the original PDF record to get a bidder name (file_name)
    pdf_result = await db.execute(
        text("SELECT file_name FROM PdfFiles WHERE id = :pdf_id"),
        {"pdf_id": pdf_id},
    )
    pdf = pdf_result.fetchone()
    bid_name = pdf.file_name if pdf else "Unknown Bid"
    print(meta_row)
    return templates.TemplateResponse(
        "metadata.html",
        {"request": request, "metadata": meta_row, "bid_name": bid_name},
    )


@app.get("/transcript/{pdf_id}", response_class=HTMLResponse, dependencies=[Depends(is_logged_in)])
async def view_transcript(request: Request, pdf_id: int, db: AsyncSession = Depends(get_db)):
    # Fetch the transcript record (file_path and status)
    transcript_result = await db.execute(
        text("SELECT file_path, status FROM Transcripts WHERE pdf_id = :pdf_id"),
        {"pdf_id": pdf_id},
    )
    transcript_data = transcript_result.fetchone()
    if not transcript_data:
        raise HTTPException(status_code=404, detail="Transcript not found")
    transcript_file = transcript_data.file_path
    transcript_status = transcript_data.status

    # Fetch the PDF record for tender and user details
    pdf_result = await db.execute(
        text("SELECT tender_id, user_id, file_name, file_path FROM PdfFiles WHERE id = :pdf_id"),
        {"pdf_id": pdf_id},
    )
    pdf = pdf_result.fetchone()
    if not pdf:
        raise HTTPException(status_code=404, detail="Bid not found")
    tender_id = pdf.tender_id
    user_id = pdf.user_id
    bid_name = pdf.file_name

    # Fetch the stored CSV contents
    ins_result = await db.execute(
        text(
            "SELECT id, row_data, decision FROM CsvErrors WHERE tender_id = :tender_id "
            "AND user_id = :user_id AND error_type = 'insertion'"
        ),
        {"tender_id": tender_id, "user_id": user_id},
    )
    insertions = ins_result.fetchall()

    del_result = await db.execute(
        text(
            "SELECT id, row_data, decision FROM CsvErrors WHERE tender_id = :tender_id "
            "AND user_id = :user_id AND error_type = 'deletion'"
        ),
        {"tender_id": tender_id, "user_id": user_id},
    )
    deletions = del_result.fetchall()

    # Determine the URLs for PDF files
    original_pdf_url = f"/uploaded/{os.path.basename(pdf.file_path)}"
    
    # Get relative path from OUTPUT_FOLDER to preserve folder structure
    output_folder_path = Path(OUTPUT_FOLDER)
    transcript_path = Path(transcript_file)
    try:
        # If the transcript path is absolute, make it relative to OUTPUT_FOLDER
        if transcript_path.is_absolute():
            relative_path = transcript_path.relative_to(output_folder_path)
        else:
            # If it's already a relative path, use it directly
            relative_path = transcript_path
        generated_pdf_url = f"/output/{relative_path}"
    except ValueError:
        # Fallback if path is not relative to OUTPUT_FOLDER
        generated_pdf_url = f"/output/{os.path.basename(transcript_file)}"

    # Render the locked template if decisions are locked (status == 1)
    if transcript_status == 1:
        return templates.TemplateResponse(
            "locked_transcript.html",
            {
                "request": request,
                "bid_name": bid_name,
                "insertions": insertions,
                "deletions": deletions,
                "original_pdf_url": original_pdf_url,
                "generated_pdf_url": generated_pdf_url,
            },
        )
    # Else, render the editable transcript template
    return templates.TemplateResponse(
        "transcript.html",
        {
            "request": request,
            "bid_name": bid_name,
            "insertions": insertions,
            "deletions": deletions,
            "original_pdf_url": original_pdf_url,
            "generated_pdf_url": generated_pdf_url,
        },
    )

@app.post("/update_decision", dependencies=[Depends(is_logged_in)])
async def update_decision(payload: dict, db: AsyncSession = Depends(get_db)):
    pdf_id = payload.get("pdf_id")
    row_id = payload.get("row_id")
    decision = int(payload.get("decision"))

    # Check if the transcript is locked
    if pdf_id:
        transcript_status = await db.execute(
            text("SELECT status FROM Transcripts WHERE pdf_id = :pdf_id"),
            {"pdf_id": pdf_id},
        )
        transcript_status = transcript_status.scalar()
        if transcript_status == 1:
            return JSONResponse(
                status_code=400,
                content={"message": "Decisions have been locked for this transcript."},
            )

    await db.execute(
        text("UPDATE CsvErrors SET decision = :decision WHERE id = :row_id"),
        {"decision": decision, "row_id": row_id},
    )
    await db.commit()
    return JSONResponse(content={"message": "Decision updated successfully"})

@app.post("/submit_decisions/{pdf_id}", dependencies=[Depends(is_logged_in)])
async def submit_decisions(pdf_id: int, payload: dict, db: AsyncSession = Depends(get_db)):
    # Update the transcript status to 1 for the given pdf_id (locking decisions)
    await db.execute(
        text("UPDATE Transcripts SET status = 1 WHERE pdf_id = :pdf_id"),
        {"pdf_id": pdf_id},
    )
    await db.commit()

    # Retrieve the tender_id for the given pdf_id from PdfFiles
    pdf_result = await db.execute(
        text("SELECT tender_id FROM pdffiles WHERE id = :pdf_id"),
        {"pdf_id": pdf_id},
    )
    pdf = pdf_result.fetchone()
    if pdf:
        tender_id = pdf.tender_id

        # Check if any transcript associated with this tender is not locked (status != 1)
        count_result = await db.execute(
            text("""
                 SELECT COUNT(*) FROM Transcripts 
                 WHERE pdf_id IN (
                     SELECT id FROM pdffiles WHERE tender_id = :tender_id
                 ) AND status <> 1
                 """),
            {"tender_id": tender_id},
        )
        not_locked_count = count_result.scalar()
        if not_locked_count == 0:
            # If all transcripts are locked, update the tender status to 1 (closed)
            await db.execute(
                text("UPDATE tenders SET status = 1 WHERE id = :tender_id"),
                {"tender_id": tender_id},
            )
            await db.commit()
            
    return JSONResponse(content={"message": "Transcript locked and decisions submitted successfully."})

@app.get("/my_tenders", response_class=HTMLResponse, dependencies=[Depends(is_logged_in)])
async def my_tenders(request: Request, db: AsyncSession = Depends(get_db)):
    user_id = request.session.get("userid")
    result = await db.execute(
        text("SELECT * FROM tenders WHERE user_id = :user_id ORDER BY id ASC"),
        {"user_id": user_id},
    )
    tenders = result.fetchall()
    return templates.TemplateResponse(
        "view_tender.html",
        {"request": request, "tenders": tenders}
    )
    
@app.post("/delete_user/{user_id}", dependencies=[Depends(is_admin), Depends(is_logged_in)])
async def delete_user(user_id: int, request: Request, db: AsyncSession = Depends(get_db)):
    # Check if the user exists
    user_result = await db.execute(
        text("SELECT * FROM users WHERE id = :user_id"),
        {"user_id": user_id},
    )
    user = user_result.fetchone()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Remove the user's upload folder (deletes all user files)
    user_folder = UPLOAD_FOLDER / str(user_id)
    if user_folder.exists() and user_folder.is_dir():
        shutil.rmtree(user_folder)

    # Delete physical files associated with PDF bids for the user
    pdf_result = await db.execute(
        text("SELECT * FROM pdffiles WHERE user_id = :user_id"),
        {"user_id": user_id},
    )
    pdf_files = pdf_result.fetchall()
    for pdf in pdf_files:
        pdf_file_path = Path(pdf.file_path)
        if pdf_file_path.exists():
            pdf_file_path.unlink()

    # Delete associated records in the following order:
    # 1. MetaFiles (associated with PDF bids)
    await db.execute(
        text("DELETE FROM metafiles WHERE pdf_id IN (SELECT id FROM pdffiles WHERE user_id = :user_id)"),
        {"user_id": user_id},
    )
    # 2. Transcripts (associated with PDF bids)
    await db.execute(
        text("DELETE FROM transcripts WHERE pdf_id IN (SELECT id FROM pdffiles WHERE user_id = :user_id)"),
        {"user_id": user_id},
    )
    # 3. CSV Errors (associated with the user)
    await db.execute(
        text("DELETE FROM CsvErrors WHERE user_id = :user_id"),
        {"user_id": user_id},
    )
    # 4. PDF files (bids) for the user
    await db.execute(
        text("DELETE FROM pdffiles WHERE user_id = :user_id"),
        {"user_id": user_id},
    )
    # 5. Tenders created by the user
    await db.execute(
        text("DELETE FROM tenders WHERE user_id = :user_id"),
        {"user_id": user_id},
    )
    # Finally, delete the user record itself
    await db.execute(
        text("DELETE FROM users WHERE id = :user_id"),
        {"user_id": user_id},
    )
    await db.commit()
    
    return JSONResponse(content={"message": "User and all associated records have been deleted successfully."})

@app.post("/set_bank_guarantee", dependencies=[Depends(is_admin), Depends(is_logged_in)])
async def set_bank_guarantee(file: UploadFile = File(...)):
    assets_folder = BASE_DIR / "assets"
    assets_folder.mkdir(parents=True, exist_ok=True)
    # Get the file extension from the uploaded file
    file_ext = os.path.splitext(file.filename)[1]
    target_filename = f"standard{file_ext}"
    target_path = assets_folder / target_filename

    content = await file.read()
    async with aiofiles.open(target_path, "wb") as f:
        await f.write(content)

    return JSONResponse(content={"message": "Bank guarantee format file updated successfully.", "file": target_filename})