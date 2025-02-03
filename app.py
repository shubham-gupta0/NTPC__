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

    id = Column(Integer, primary_key=True, autoincrement=True,nullable=False)
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


# Routes
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
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

    await db.execute(
        text(f"UPDATE users SET {set_clause} WHERE id = :user_id"),
        {**update_fields, "user_id": user_id},
    )
    await db.commit()

    return JSONResponse(content={"message": "User updated successfully."})


"""    DASHBOARD PAGE        """


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    print(request.session)
    if not request.session.get("logged_in"):
        return RedirectResponse(url="/login", status_code=302)
    # if user is admin then show admin dashboard
    if request.session.get("admin"):
        return templates.TemplateResponse("admin_dashboard.html", {"request": request})

    else:
        return templates.TemplateResponse("dashboard.html", {"request": request})


@app.get("/EMD_BG", response_class=HTMLResponse)
async def doc1(request: Request):
    # Check if the user is already logged in
    if not request.session.get("logged_in"):
        return RedirectResponse(url="/login", status_code=302)

    return templates.TemplateResponse("EMD_dashboard.html", {"request": request})


""" Tender LOGIC TO ADD, VIEW AND DELETE TENDER """


@app.get("/tender", response_class=HTMLResponse)
async def create_task_page(request: Request):
    if not request.session.get("logged_in"):
        return RedirectResponse(url="/login", status_code=302)
    return templates.TemplateResponse("create_tender.html", {"request": request})


@app.post("/tender")
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


@app.get("/add_bids/{tender_id}", response_class=HTMLResponse)
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
        text("SELECT * FROM pdffiles WHERE tender_id = :tender_id AND user_id = :user_id"),
        {"tender_id": tender_id, "user_id": user_id},
    )
    bids = bids_result.fetchall()
    print(bids)
    return templates.TemplateResponse(
        "add_bids.html", {"request": request, "bids": bids, "tender_id": tender_id}
    )
@app.post("/add_bids/{tender_id}")
async def add_bids(
    request: Request,
    tender_id: int,
    bid_name: str = Form(...),
    bid_pdf: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    print("CALLING ADD BIDS")
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
    print(new_pdf)
    db.add(new_pdf)
    await db.commit()
    
    # Update the user's used storage
    new_used_storage = user.total_storage_used + pdf_file_size
    await db.execute(
        text(
            "UPDATE users SET total_storage_used = :new_used_storage WHERE id = :user_id"
        ),
        {"new_used_storage": new_used_storage, "user_id": user.id},
    )
    await db.commit()

    # Generate transcript asynchronously
    def process_transcript():
        try:
            print("GENERATING TRANSCRIPT")
            a=generate_transcript(input_filename, bid_pdf_path,user.id, tender_id,new_pdf.id,db)
            print(f"\n\nTRANSCRIPT GENERATED {a}\n\n")
        except Exception as e:
            # Log the error (use proper logging in production)
            print(f"Error generating transcript for ID {tender_id}: {e}")

    # Save the uploaded file
    async with aiofiles.open(bid_pdf_path, "wb") as f:
        await f.write(content)
        # Start the transcript generation process in a separate thread
        print("Starting transcript generation process")
        threading.Thread(target=process_transcript).start()
    
    # Update session with the new bid
    if "bids" not in request.session:
        request.session["bids"] = []
    request.session["bids"].append({"name": bid_name, "file": bid_pdf.filename})
    
    return RedirectResponse(url=f"/add_bids/{tender_id}", status_code=302)

@app.get("/view_bids/{pdf_id}", name="view_bids")
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

@app.post("/delete_bid/{pdf_id}", name="delete_bid")
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

    # Fetch the PDF file
    result = await db.execute(
        text("SELECT * FROM pdffiles WHERE id = :pdf_id AND user_id = :user_id"),
        {"pdf_id": pdf_id, "user_id": user_id},
    )
    pdf = result.fetchone()
    if not pdf:
        raise HTTPException(status_code=404, detail="File not found")
    
    # Delete the PDF file
    pdf_file_path = Path(pdf.file_path)
    if pdf_file_path.exists():
        pdf_file_path.unlink()
        
    # Update the user's storage
    result = await db.execute(
        text("SELECT * FROM users WHERE id = :user_id"),
        {"user_id": user_id},
    )
    user = result.fetchone()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    new_used_storage = user.total_storage_used - pdf.file_size
    await db.execute(
        text("UPDATE users SET total_storage_used = :new_used_storage WHERE id = :user_id"),
        {"new_used_storage": new_used_storage, "user_id": user_id},
    )
    await db.commit()
    

    # Delete the PDF file record
    await db.execute(
        text("DELETE FROM pdffiles WHERE id = :pdf_id"),
        {"pdf_id": pdf_id},
    )
    await db.commit()
    return RedirectResponse(url=f"/add_bids/{pdf.tender_id}", status_code=302)