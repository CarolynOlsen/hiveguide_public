# MIGRATION COMPLETE: This file is now a FastAPI app. Flask code has been removed.
from fastapi import FastAPI, Request, Response, Depends, HTTPException, status, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware
from pydantic import BaseModel, Field
from uuid import uuid4
from datetime import datetime, timedelta, date
import os
import secrets
from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, Date, ForeignKey, JSON, text, case, func
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm import Session
import yaml
from passlib.context import CryptContext
from sqlalchemy.orm import relationship
from typing import Optional, List
import openai
import json
import base64
import tempfile
import logging
import sys
from backend.utils.llm_analyzer import analyze_inspection_for_actions, get_hive_urgency

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.exception_handlers import RequestValidationError
from fastapi.exceptions import HTTPException

logging.basicConfig(level=logging.DEBUG, format='[%(levelname)s] %(message)s')

print = logging.info  # Redirect print to logging for consistency

app = FastAPI()

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to protect against common attacks and satisfy corporate firewalls"""
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        
        # Security headers required by most corporate firewalls
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY" 
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        
        # Content Security Policy - restrictive but allows the app to function
        csp_policy = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: blob:; "
            "font-src 'self'; "
            "connect-src 'self' https://hiveguide.up.railway.app; "
            "frame-ancestors 'none'"
        )
        response.headers["Content-Security-Policy"] = csp_policy
        
        # HTTPS enforcement in production (only add if request is HTTPS)
        if request.url.scheme == "https":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        
        return response

# Add security headers middleware
app.add_middleware(SecurityHeadersMiddleware)

def create_login_events_table_if_not_exists():
    """Create login_events table if it doesn't exist"""
    try:
        from sqlalchemy import text
        with engine.connect() as connection:
            # Check if table exists
            result = connection.execute(text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name = 'login_events'
                );
            """))
            
            if not result.scalar():
                # Create the table
                connection.execute(text("""
                    CREATE TABLE login_events (
                        id SERIAL PRIMARY KEY,
                        user_id INTEGER REFERENCES users(id),
                        email VARCHAR NOT NULL,
                        platform VARCHAR NOT NULL,
                        success BOOLEAN NOT NULL,
                        ip_address VARCHAR,
                        user_agent VARCHAR,
                        timestamp TIMESTAMP DEFAULT NOW(),
                        failure_reason VARCHAR
                    );
                    CREATE INDEX ix_login_events_id ON login_events (id);
                """))
                connection.commit()
                logging.info("Created login_events table successfully")
            else:
                logging.info("login_events table already exists")
    except Exception as e:
        logging.error(f"Error creating login_events table: {e}")

@app.on_event("startup")
async def startup_event():
    logging.info("FastAPI application startup.")
    create_login_events_table_if_not_exists()

@app.on_event("shutdown")
async def shutdown_event():
    logging.info("FastAPI application shutdown.")

@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    logging.error(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    logging.error(f"Validation error: {exc}")
    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors()},
    )

print("[DEBUG] Starting HiveGuide app...")

# Load configuration from config.yaml if present (env vars take precedence)
config = {}
try:
    if os.path.exists("config.yaml"):
        with open("config.yaml", "r") as f:
            config = yaml.safe_load(f) or {}
        logging.info("Loaded config.yaml successfully.")
    else:
        logging.info("config.yaml not found; relying on environment variables")
except Exception as e:
    logging.error(f"Failed to load config.yaml: {e}")
    config = {}

# Determine settings from environment or config
database_url = os.environ.get("DATABASE_URL") or config.get("database_url")
openai_key = os.environ.get("OPENAI_API_KEY") or config.get("openai_api_key")
openrouter_key = os.environ.get("OPENROUTER_API_KEY") or config.get("openrouter_api_key")
assembly_ai_key = os.environ.get("ASSEMBLY_AI_API_KEY") or config.get("assembly_ai_api_key")

if not database_url:
    logging.error("DATABASE_URL not set in environment or config.yaml")
if not openai_key:
    logging.error("OPENAI_API_KEY not set in environment or config.yaml")
if not openrouter_key:
    logging.error("OPENROUTER_API_KEY not set in environment or config.yaml")
if not assembly_ai_key:
    logging.error("ASSEMBLY_AI_API_KEY not set in environment or config.yaml")

# Assign settings
database_url = database_url
OPENAI_API_KEY = openai_key
OPENROUTER_API_KEY = openrouter_key
ASSEMBLY_AI_API_KEY = assembly_ai_key

logging.info(f"DATABASE_URL: {database_url}")

Base = declarative_base()

try:
    engine = create_engine(database_url)
    logging.info("Created SQLAlchemy engine successfully.")
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
except Exception as e:
    logging.error(f"Failed to create SQLAlchemy engine: {e}")
    sys.exit(1)

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    is_admin = Column(Boolean, default=False)
    is_approved = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    hives = relationship("Hive", back_populates="user", cascade="all, delete-orphan")

class Hive(Base):
    __tablename__ = "hives"
    id = Column(Integer, primary_key=True, index=True)
    nickname = Column(String, nullable=False)
    photo_url = Column(String, nullable=True)
    location = Column(String, nullable=True)
    description = Column(String, nullable=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    last_action_analysis = Column(DateTime, nullable=True)
    user = relationship("User", back_populates="hives")
    inspections = relationship("Inspection", back_populates="hive", cascade="all, delete-orphan")

User.hives = relationship("Hive", back_populates="user", cascade="all, delete-orphan")

class LoginEvent(Base):
    __tablename__ = "login_events"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)  # Nullable for failed attempts
    email = Column(String, nullable=False)  # Email used in login attempt
    platform = Column(String, nullable=False)  # 'web' or 'ios'
    success = Column(Boolean, nullable=False)  # True for successful login, False for failure
    ip_address = Column(String, nullable=True)  # Client IP address
    user_agent = Column(String, nullable=True)  # Browser/app user agent
    timestamp = Column(DateTime, default=datetime.utcnow)  # UTC timestamp
    failure_reason = Column(String, nullable=True)  # Reason for failed login
    user = relationship("User", backref="login_events")

class Inspection(Base):
    __tablename__ = "inspections"
    id = Column(Integer, primary_key=True, index=True)
    hive_id = Column(Integer, ForeignKey("hives.id"), nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)
    transcription = Column(String, default="")
    notes = Column(String, default="")
    weather = Column(String, default="sunny")
    temperature = Column(String, default="")
    queen_visible = Column(Boolean, default=False)
    eggs_visible = Column(Boolean, default=False)
    larvae_visible = Column(Boolean, default=False)
    capped_brood_visible = Column(Boolean, default=False)
    laying_pattern = Column(String, default="solid")
    activity_level = Column(String, default="average")
    photos = Column(JSON, default=list)
    action_items = Column(JSON, nullable=True)
    action_due_date = Column(Date, nullable=True)

# Add inspection_date column conditionally after database connection is established
def add_inspection_date_column():
    """Add inspection_date column to Inspection model if it exists in the database"""
    try:
        # Check if the column exists in the database
        with engine.connect() as conn:
            result = conn.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name = 'inspections' AND column_name = 'inspection_date'"))
            if result.fetchone():
                # Column exists, add it to the model
                Inspection.inspection_date = Column(Date, nullable=True)
                return True
    except Exception:
        pass
    return False

Inspection.hive = relationship("Hive", back_populates="inspections")

class Circle(Base):
    __tablename__ = "circles"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    description = Column(String, nullable=True)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    owner = relationship("User")
    memberships = relationship("CircleMembership", back_populates="circle", cascade="all, delete-orphan")

class CircleMembership(Base):
    __tablename__ = "circle_memberships"
    id = Column(Integer, primary_key=True, index=True)
    circle_id = Column(Integer, ForeignKey("circles.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    added_at = Column(DateTime, default=datetime.utcnow)
    circle = relationship("Circle", back_populates="memberships")
    user = relationship("User")

class Session(Base):
    __tablename__ = "sessions"
    id = Column(String, primary_key=True, index=True)  # Random session token
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)
    is_active = Column(Boolean, default=True)
    user = relationship("User")

# Check if inspection_date column exists and add it to the model if present
try:
    add_inspection_date_column()
    logging.info("Inspection date column compatibility check completed")
except Exception as e:
    logging.warning(f"Could not check inspection_date column: {e}")

# CORS configuration - secure settings for production and development
allowed_origins = [
    "http://localhost:5173",      # Vite dev server
    "http://127.0.0.1:5173",      # Vite dev server alternative
    "http://localhost:8000",      # Local FastAPI server
    "http://127.0.0.1:8000",      # Local FastAPI server alternative
]

# Add production origins from environment variables
custom_origin = os.environ.get("ALLOWED_ORIGIN")
if custom_origin:
    allowed_origins.append(custom_origin)

# Railway-specific environment variables
railway_app_url = os.environ.get("RAILWAY_STATIC_URL") or os.environ.get("RAILWAY_PUBLIC_DOMAIN")
if railway_app_url:
    # Ensure both HTTP and HTTPS versions are allowed
    if not railway_app_url.startswith(("http://", "https://")):
        railway_app_url = f"https://{railway_app_url}"
    allowed_origins.append(railway_app_url)
    # Also add the HTTP version for development
    if railway_app_url.startswith("https://"):
        allowed_origins.append(railway_app_url.replace("https://", "http://"))

# Common Railway URL patterns for CarolynOlsen/hiveguide
production_domains = [
    "https://hiveguide-production.up.railway.app",
    "https://hiveguide.up.railway.app", 
    "https://hiveguide-app.up.railway.app",
    "https://web-production-*.up.railway.app",  # Generic Railway pattern
]
allowed_origins.extend(production_domains)

# Development: allow localhost on any port for local testing
if os.environ.get("ENVIRONMENT", "development") == "development":
    allowed_origins.extend([
        "http://localhost:3000",   # Common React dev port
        "http://localhost:3001", 
        "http://127.0.0.1:3000",
    ])

# Remove duplicates and log for debugging
allowed_origins = list(set(allowed_origins))
logging.info(f"Allowed CORS origins: {allowed_origins}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],  # Specific methods instead of "*"
    allow_headers=["Content-Type", "Authorization", "Accept", "Origin", "X-Requested-With", "X-CSRF-Token"],  # Specific headers
)

inspections = []  # TODO: Replace with actual data loading logic

def load_inspections():
    # TODO: Implement actual loading logic
    return inspections

def get_db():
    try:
        db = SessionLocal()
        yield db
    except Exception as e:
        logging.error(f"Failed to create DB session: {e}")
        raise
    finally:
        db.close()

static_dir = os.path.join(os.path.dirname(__file__), 'static')
if not os.path.exists(static_dir):
    logging.error(f"Static directory {static_dir} does not exist!")
app.mount("/static", StaticFiles(directory=static_dir), name="static")

# Session Management Functions
def create_session(user_id: int, db: SessionLocal = None) -> str:
    """Create a new session for a user"""
    session_token = secrets.token_urlsafe(32)
    expires_at = datetime.utcnow() + timedelta(days=30)  # 30 days
    
    # Use a separate db session to avoid detaching objects in the calling session
    if db is None:
        db = SessionLocal()
        should_close = True
    else:
        should_close = False
    
    try:
        session = Session(
            id=session_token,
            user_id=user_id,
            expires_at=expires_at
        )
        db.add(session)
        db.commit()
        return session_token
    finally:
        if should_close:
            db.close()

def validate_session(session_token: str, db: SessionLocal) -> User | None:
    """Validate a session token and return the associated user"""
    if not session_token:
        return None
    
    session = db.query(Session).filter(
        Session.id == session_token,
        Session.is_active == True,
        Session.expires_at > datetime.utcnow()
    ).first()
    
    if not session:
        return None
    
    # Update last accessed time could be added here if needed
    return session.user

def invalidate_session(session_token: str, db: SessionLocal):
    """Invalidate a session token"""
    if not session_token:
        return
        
    session = db.query(Session).filter(Session.id == session_token).first()
    if session:
        session.is_active = False
        db.commit()

def get_current_user(request: Request) -> User | None:
    """Helper to get current user from request (supports both cookies and Authorization header)"""
    # Try to get session token from cookie first (for web app compatibility)
    session_token = request.cookies.get("session_id")
    
    # If no cookie, try Authorization header (for mobile app)
    if not session_token:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            session_token = auth_header.split(" ")[1]
    
    if not session_token:
        return None
    
    db = SessionLocal()
    try:
        return validate_session(session_token, db)
    finally:
        db.close()

def require_auth(request: Request) -> User:
    """Dependency to require authentication"""
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    return user

@app.get("/")
async def index(request: Request):
    # TODO: Session handling if needed
    return FileResponse(os.path.join(static_dir, 'index.html'))

@app.get("/api/health")
def api_health():
    """API health check for React frontend"""
    return {"status": "healthy"}

@app.get("/health")
def health_check():
    """Health check endpoint for Railway monitoring"""
    try:
        load_inspections()
        return {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "inspections_count": len(inspections),
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.now().isoformat(),
        }, 500

@app.get("/db_health")
def db_health():
    try:
        # TODO: Replace with actual db.session and text imports
        class DummyDB:
            def session(self):
                class Session:
                    def execute(self, query):
                        return 1
                return Session()
        db = DummyDB()
        def text(query):
            return query
        db.session().execute(text("SELECT 1"))
        return {"status": "healthy"}
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}

class LoginRequest(BaseModel):
    email: str
    password: str

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def detect_platform(request: Request) -> str:
    """Detect if request is from web browser or iOS app"""
    user_agent = request.headers.get("user-agent", "").lower()
    
    # Check for iOS app indicators
    if "hiveguideiOS" in user_agent or "ios" in user_agent or "iphone" in user_agent:
        return "ios"
    
    # Default to web for all other cases (browsers, etc.)
    return "web"

def get_client_ip(request: Request) -> str:
    """Extract client IP address from request"""
    # Check for forwarded headers (common in production with proxies)
    x_forwarded_for = request.headers.get("x-forwarded-for")
    if x_forwarded_for:
        # Take the first IP in the chain
        return x_forwarded_for.split(",")[0].strip()
    
    # Check for real IP header
    x_real_ip = request.headers.get("x-real-ip")
    if x_real_ip:
        return x_real_ip
    
    # Fallback to direct client IP
    client_host = getattr(request.client, "host", "unknown") if request.client else "unknown"
    return client_host

def log_login_event(user_id: int, email: str, platform: str, 
                   success: bool, ip_address: str, user_agent: str, 
                   failure_reason: str = None):
    """Log login event to database using separate session"""
    try:
        # Use a separate database session to avoid transaction conflicts
        with SessionLocal() as log_db:
            login_event = LoginEvent(
                user_id=user_id,  # Always log user_id when known (for both success/failure)
                email=email,
                platform=platform,
                success=success,
                ip_address=ip_address,
                user_agent=user_agent,
                failure_reason=failure_reason
            )
            log_db.add(login_event)
            log_db.commit()
    except Exception as e:
        # Don't let logging errors break the login flow
        # Use separate session so rollback won't affect main transaction
        print(f"Error logging login event: {e}")

@app.post("/login")
def login(data: LoginRequest, response: Response, request: Request, db: Session = Depends(get_db)):
    email = data.email.strip().lower()
    password = data.password
    
    # Extract request metadata for logging
    platform = detect_platform(request)
    ip_address = get_client_ip(request)
    user_agent = request.headers.get("user-agent", "")
    
    # Use separate variables to avoid detached instance issues
    user_id = None
    user_email = None
    is_admin = False
    is_approved = False
    
    # Query user data and capture all needed attributes immediately
    result = db.query(User.id, User.email, User.password_hash, User.is_approved, User.is_admin).filter(
        User.email == email
    ).first()
    
    if not result:
        # Log failed login attempt - user not found
        log_login_event(None, email, platform, False, ip_address, user_agent, "user_not_found")
        raise HTTPException(status_code=401, detail="Invalid email or password")
    
    user_id, user_email, password_hash, is_approved, is_admin = result
    
    if not pwd_context.verify(password, password_hash):
        # Log failed login attempt - invalid password
        log_login_event(user_id, email, platform, False, ip_address, user_agent, "invalid_password")
        raise HTTPException(status_code=401, detail="Invalid email or password")
    
    if not is_approved:
        # Log failed login attempt - not approved
        log_login_event(user_id, email, platform, False, ip_address, user_agent, "not_approved")
        raise HTTPException(status_code=403, detail="Account not approved by admin yet.")
    
    # Create secure session (using separate db session)
    session_token = create_session(user_id, db)
    
    # Log successful login attempt
    log_login_event(user_id, email, platform, True, ip_address, user_agent)
    
    # Set cookie for web app
    # Detect production environment
    is_production = os.environ.get('RAILWAY_ENVIRONMENT') is not None
    
    response.set_cookie(
        key="session_id", 
        value=session_token, 
        httponly=True,
        secure=is_production,  # True in production, False in dev
        samesite="lax",
        max_age=30 * 24 * 60 * 60  # 30 days
    )
    
    # Return response with session_token and user data for mobile app
    return {
        "status": "success", 
        "message": "Login successful", 
        "session_token": session_token,
        "user": {
            "id": user_id,
            "email": user_email,
            "is_admin": is_admin,
            "is_approved": is_approved
        }
    }

@app.post("/logout")
def logout(response: Response, request: Request):
    session_token = request.cookies.get("session_id")
    if session_token:
        db = SessionLocal()
        try:
            invalidate_session(session_token, db)
        finally:
            db.close()
    # Detect production environment for secure cookie deletion
    is_production = os.environ.get('RAILWAY_ENVIRONMENT') is not None
    
    response.delete_cookie(
        key="session_id",
        secure=is_production,  # Match the secure setting used when setting the cookie
        samesite="lax"
    )
    return {"status": "success", "message": "Logout successful"}

@app.get("/auth/status")
def auth_status(request: Request):
    user = get_current_user(request)
    return {"authenticated": user is not None}

@app.get("/auth/me")
def auth_me(request: Request):
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    # Return user object directly - HttpClient will wrap in ApiResponse
    return {
        "id": user.id, 
        "email": user.email, 
        "is_admin": user.is_admin, 
        "is_approved": user.is_approved,
        "created_at": user.created_at.isoformat() if hasattr(user, 'created_at') and user.created_at else ""
    }

# Update admin endpoints to use the database
class UserIdRequest(BaseModel):
    user_id: int

@app.get("/admin/pending_users")
def list_pending_users(request: Request):
    admin_user = require_auth(request)
    if not admin_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    db = SessionLocal()
    users = db.query(User).filter(User.is_approved == False).all()
    result = [{"id": u.id, "email": u.email, "created_at": u.created_at.isoformat()} for u in users]
    db.close()
    return result

@app.post("/admin/approve_user")
def approve_user(data: UserIdRequest, request: Request):
    admin_user = require_auth(request)
    if not admin_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    db = SessionLocal()
    user = db.query(User).filter(User.id == data.user_id).first()
    if not user:
        db.close()
        raise HTTPException(status_code=404, detail="User not found")
    user_email = user.email  # Store email before closing session
    user.is_approved = True
    db.commit()
    db.close()
    return {"status": "success", "message": f"User {user_email} approved."}

@app.post("/admin/reject_user")
def reject_user(data: UserIdRequest, request: Request):
    admin_user = require_auth(request)
    if not admin_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    db = SessionLocal()
    user = db.query(User).filter(User.id == data.user_id).first()
    if not user:
        db.close()
        raise HTTPException(status_code=404, detail="User not found")
    user_email = user.email  # Store email before deleting user
    db.delete(user)
    db.commit()
    db.close()
    return {"status": "success", "message": f"User {user_email} rejected and deleted."}

class RegisterRequest(BaseModel):
    email: str
    password: str

@app.post("/register")
def register(data: RegisterRequest):
    email = data.email.strip().lower()
    password = data.password
    if not email or not password:
        raise HTTPException(status_code=400, detail="Email and password are required.")
    db = SessionLocal()
    existing_user = db.query(User).filter(User.email == email).first()
    if existing_user:
        db.close()
        raise HTTPException(status_code=400, detail="Email already registered.")
    hashed_password = pwd_context.hash(password)
    new_user = User(email=email, password_hash=hashed_password, is_admin=False, is_approved=False)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    db.close()
    return {"status": "success", "message": "Registration successful. Awaiting admin approval."}

class HiveCreateRequest(BaseModel):
    nickname: str
    photo_url: Optional[str] = None
    location: Optional[str] = None
    description: Optional[str] = None

class HiveResponse(BaseModel):
    id: int
    nickname: str
    photo_url: Optional[str] = None
    location: Optional[str] = None
    description: Optional[str] = None
    user_id: int

    class Config:
        from_attributes = True

class CircleCreateRequest(BaseModel):
    name: str
    description: Optional[str] = None

class CircleResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    owner_id: int
    created_at: datetime

    class Config:
        from_attributes = True

class CircleMembershipResponse(BaseModel):
    id: int
    circle_id: int
    user_id: int
    added_at: datetime
    user_email: str

    class Config:
        from_attributes = True

class InviteMemberRequest(BaseModel):
    email: str

@app.post("/hives", response_model=HiveResponse)
def create_hive(
    request: Request,
    nickname: str = Form(...),
    location: str = Form(None),
    description: str = Form(None),
    photo: UploadFile = File(None)
):
    user = require_auth(request)
    db = SessionLocal()
    photo_url = None
    if photo:
        photos_dir = os.path.join("static", "hive_photos")
        os.makedirs(photos_dir, exist_ok=True)
        ext = os.path.splitext(photo.filename)[1]
        filename = f"hive_{user.id}_{nickname}_{photo.filename}"
        file_path = os.path.join(photos_dir, filename)
        with open(file_path, "wb") as f:
            f.write(photo.file.read())
        photo_url = f"/static/hive_photos/{filename}"
    hive = Hive(
        nickname=nickname,
        photo_url=photo_url,
        location=location,
        description=description,
        user_id=user.id
    )
    db.add(hive)
    db.commit()
    db.refresh(hive)
    db.close()
    return hive

@app.get("/hives", response_model=list[HiveResponse])
def list_hives(request: Request):
    user = require_auth(request)
    db = SessionLocal()
    try:
        user_id = user.id
        
        # Get user's own hives
        own_hives = db.query(Hive).filter(Hive.user_id == user_id).all()
        
        # Get hives from circles user is a member of (gracefully handle if Circle tables don't exist)
        circle_hives = []
        try:
            circle_hives = db.query(Hive).join(
                Circle, Hive.user_id == Circle.owner_id
            ).join(
                CircleMembership, Circle.id == CircleMembership.circle_id
            ).filter(
                CircleMembership.user_id == user_id,
                Hive.user_id != user_id  # Exclude own hives to avoid duplicates
            ).all()
        except Exception as e:
            logging.warning(f"Could not fetch circle hives: {e}")
            # Continue without circle hives if there's an issue with the Circle feature
        
        # Combine both lists
        all_hives = own_hives + circle_hives
        return all_hives
    finally:
        db.close()

class HiveUpdateRequest(BaseModel):
    nickname: Optional[str] = None
    location: Optional[str] = None
    description: Optional[str] = None

@app.put("/hives/{hive_id}", response_model=HiveResponse)
def update_hive(
    hive_id: int,
    request: Request,
    nickname: str = Form(None),
    location: str = Form(None),
    description: str = Form(None),
    photo: UploadFile = File(None)
):
    user = require_auth(request)
    db = SessionLocal()
    hive = db.query(Hive).filter(Hive.id == hive_id, Hive.user_id == user.id).first()
    if not hive:
        db.close()
        raise HTTPException(status_code=404, detail="Hive not found or not owned by user")
    
    if nickname is not None:
        hive.nickname = nickname
    if location is not None:
        hive.location = location
    if description is not None:
        hive.description = description
    
    if photo:
        photos_dir = os.path.join("static", "hive_photos")
        os.makedirs(photos_dir, exist_ok=True)
        ext = os.path.splitext(photo.filename)[1]
        filename = f"hive_{user.id}_{hive.nickname}_{photo.filename}"
        file_path = os.path.join(photos_dir, filename)
        with open(file_path, "wb") as f:
            f.write(photo.file.read())
        hive.photo_url = f"/static/hive_photos/{filename}"
    
    db.commit()
    db.refresh(hive)
    db.close()
    return hive

@app.delete("/hives/{hive_id}")
def delete_hive(hive_id: int, request: Request):
    user = require_auth(request)
    db = SessionLocal()
    hive = db.query(Hive).filter(Hive.id == hive_id, Hive.user_id == user.id).first()
    if not hive:
        db.close()
        raise HTTPException(status_code=404, detail="Hive not found or not owned by user")
    
    db.delete(hive)
    db.commit()
    db.close()
    return {"status": "success", "message": "Hive deleted successfully"}

# Circle Management Endpoints

@app.post("/circles", response_model=CircleResponse)
def create_circle(data: CircleCreateRequest, request: Request):
    user = require_auth(request)
    db = SessionLocal()
    
    circle = Circle(
        name=data.name,
        description=data.description,
        owner_id=user.id
    )
    db.add(circle)
    db.commit()
    db.refresh(circle)
    db.close()
    return circle

@app.get("/circles", response_model=list[CircleResponse])
def list_circles(request: Request):
    user = require_auth(request)
    db = SessionLocal()
    user_id = user.id
    
    # Get circles where user is owner or member
    circles = db.query(Circle).filter(
        (Circle.owner_id == user_id) | 
        (Circle.id.in_(
            db.query(CircleMembership.circle_id).filter(CircleMembership.user_id == user_id)
        ))
    ).all()
    
    db.close()
    return circles

@app.post("/circles/{circle_id}/invite")
def invite_to_circle(circle_id: int, data: InviteMemberRequest, request: Request):
    user = require_auth(request)
    db = SessionLocal()
    
    # Check if user owns the circle
    circle = db.query(Circle).filter(Circle.id == circle_id, Circle.owner_id == user.id).first()
    if not circle:
        db.close()
        raise HTTPException(status_code=404, detail="Circle not found or not owned by user")
    
    # Find user to invite
    invite_user = db.query(User).filter(User.email == data.email.strip().lower()).first()
    if not invite_user:
        db.close()
        raise HTTPException(status_code=404, detail="User not found")
    
    # Check if already a member
    existing_membership = db.query(CircleMembership).filter(
        CircleMembership.circle_id == circle_id,
        CircleMembership.user_id == invite_user.id
    ).first()
    if existing_membership:
        db.close()
        raise HTTPException(status_code=400, detail="User already in circle")
    
    # Create membership
    membership = CircleMembership(
        circle_id=circle_id,
        user_id=invite_user.id
    )
    db.add(membership)
    db.commit()
    db.close()
    return {"status": "success", "message": f"User {data.email} invited to circle"}

@app.get("/circles/{circle_id}/members", response_model=list[CircleMembershipResponse])
def list_circle_members(circle_id: int, request: Request):
    user = require_auth(request)

    db = SessionLocal()

    user_id = user.id
    
    # Check if user has access to this circle (owner or member)
    has_access = db.query(Circle).filter(
        Circle.id == circle_id,
        (Circle.owner_id == user_id) | 
        (Circle.id.in_(
            db.query(CircleMembership.circle_id).filter(CircleMembership.user_id == user_id)
        ))
    ).first()
    
    if not has_access:
        db.close()
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Get members with user emails
    memberships = db.query(CircleMembership, User.email).join(
        User, CircleMembership.user_id == User.id
    ).filter(CircleMembership.circle_id == circle_id).all()
    
    result = []
    for membership, email in memberships:
        result.append({
            "id": membership.id,
            "circle_id": membership.circle_id,
            "user_id": membership.user_id,
            "added_at": membership.added_at,
            "user_email": email
        })
    
    db.close()
    return result

@app.delete("/circles/{circle_id}/members/{user_id}")
def remove_circle_member(circle_id: int, user_id: int, request: Request):
    current_user = require_auth(request)
    db = SessionLocal()
    
    # Check if user owns the circle
    circle = db.query(Circle).filter(Circle.id == circle_id, Circle.owner_id == current_user.id).first()
    if not circle:
        db.close()
        raise HTTPException(status_code=404, detail="Circle not found or not owned by user")
    
    # Remove membership
    membership = db.query(CircleMembership).filter(
        CircleMembership.circle_id == circle_id,
        CircleMembership.user_id == user_id
    ).first()
    if not membership:
        db.close()
        raise HTTPException(status_code=404, detail="Membership not found")
    
    db.delete(membership)
    db.commit()
    db.close()
    return {"status": "success", "message": "Member removed from circle"}

@app.delete("/circles/{circle_id}")
def delete_circle(circle_id: int, request: Request):
    current_user = require_auth(request)
    db = SessionLocal()
    
    # Check if user owns the circle
    circle = db.query(Circle).filter(Circle.id == circle_id, Circle.owner_id == current_user.id).first()
    if not circle:
        db.close()
        raise HTTPException(status_code=404, detail="Circle not found or not owned by user")
    
    # Delete the circle (cascade will handle memberships)
    db.delete(circle)
    db.commit()
    db.close()
    return {"status": "success", "message": f"Circle '{circle.name}' deleted successfully"}

class InspectionCreateRequest(BaseModel):
    hive_id: int
    transcription: str = ""
    notes: str = ""
    weather: Optional[str] = Field(None, pattern="^(sunny|cloudy|partly_cloudy|rainy|snowy)$")
    temperature: str = ""
    queen_visible: Optional[bool] = None
    eggs_visible: Optional[bool] = None
    larvae_visible: Optional[bool] = None
    capped_brood_visible: Optional[bool] = None
    laying_pattern: Optional[str] = Field(None, pattern="^(poor|patchy|solid)$")
    activity_level: Optional[str] = Field(None, pattern="^(low|average|high)$")

class InspectionResponse(BaseModel):
    id: int
    hive_id: int
    timestamp: datetime
    inspection_date: Optional[date] = None
    transcription: str
    notes: str
    weather: str
    temperature: str
    queen_visible: bool
    eggs_visible: bool
    larvae_visible: bool
    capped_brood_visible: bool
    laying_pattern: str
    activity_level: str
    action_items: Optional[List[dict]] = None
    photos: List[str] = []

    @classmethod
    def model_validate(cls, obj):
        # Handle None photos field from database
        if hasattr(obj, 'photos') and obj.photos is None:
            obj.photos = []
        return super().model_validate(obj)

    class Config:
        from_attributes = True

@app.post("/inspections", response_model=InspectionResponse)
def create_inspection(request: Request,
    hive_id: int = Form(...),
    inspection_date: Optional[str] = Form(None),
    transcription: str = Form(""),
    notes: str = Form(""),
    weather: Optional[str] = Form(None),
    temperature: str = Form(""),
    queen_visible: Optional[bool] = Form(None),
    eggs_visible: Optional[bool] = Form(None),
    larvae_visible: Optional[bool] = Form(None),
    capped_brood_visible: Optional[bool] = Form(None),
    laying_pattern: Optional[str] = Form(None),
    activity_level: Optional[str] = Form(None),
    photos: list[UploadFile] = File([])
):
    user = require_auth(request)

    db = SessionLocal()

    user_id = user.id
    hive = db.query(Hive).filter(Hive.id == hive_id).first()
    if not hive:
        db.close()
        raise HTTPException(status_code=404, detail="Hive not found")
    
    # Check if user owns the hive or has access through a circle
    has_access = (hive.user_id == user_id)
    if not has_access:
        try:
            # Check circle access if Circle tables exist
            has_access = db.query(CircleMembership).join(
                Circle, CircleMembership.circle_id == Circle.id
            ).filter(
                CircleMembership.user_id == user_id,
                Circle.owner_id == hive.user_id
            ).first() is not None
        except Exception as e:
            logging.warning(f"Could not check circle access: {e}")
            # Continue without circle access if there's an issue with the Circle feature
    
    if not has_access:
        db.close()
        raise HTTPException(status_code=403, detail="Access denied to this hive")
    photo_urls = []
    for photo in photos:
        if photo:
            ext = os.path.splitext(photo.filename)[1]
            filename = f"inspection_{hive_id}_{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}{ext}"
            save_path = os.path.join(static_dir, "inspection_photos", filename)
            os.makedirs(os.path.dirname(save_path), exist_ok=True)
            with open(save_path, "wb") as f:
                f.write(photo.file.read())
            photo_urls.append(f"/static/inspection_photos/{filename}")
    # Create inspection with robust handling of inspection_date field
    inspection_data = {
        'hive_id': hive_id,
        'transcription': transcription,
        'notes': notes,
        'weather': weather,
        'temperature': temperature,
        'queen_visible': queen_visible,
        'eggs_visible': eggs_visible,
        'larvae_visible': larvae_visible,
        'capped_brood_visible': capped_brood_visible,
        'laying_pattern': laying_pattern,
        'activity_level': activity_level,
        'photos': photo_urls,
    }
    
    # Only add inspection_date if the column exists (for migration compatibility)
    if hasattr(Inspection, 'inspection_date'):
        # Parse inspection_date from string if provided, otherwise use today's date
        if inspection_date:
            try:
                inspection_data['inspection_date'] = datetime.strptime(inspection_date, '%Y-%m-%d').date()
            except ValueError:
                inspection_data['inspection_date'] = datetime.now().date()
        else:
            inspection_data['inspection_date'] = datetime.now().date()
    
    inspection = Inspection(**inspection_data)
    db.add(inspection)
    db.commit()
    db.refresh(inspection)
    
    # Analyze inspection for action items using LLM
    try:
        # Pass inspection_date to filter seasonal suggestions
        inspection_date_for_analysis = getattr(inspection, 'inspection_date', None)
        analysis = analyze_inspection_for_actions(notes, transcription, inspection_date=inspection_date_for_analysis)
        if analysis.get("actions"):
            # Add individual due dates to each action based on their timeframe_days
            actions_with_due_dates = []
            # Use inspection_date if available, otherwise fallback to timestamp
            base_date = getattr(inspection, 'inspection_date', None) or inspection.timestamp.date()
            for action in analysis["actions"]:
                action_with_due_date = action.copy()
                timeframe_days = action.get("timeframe_days", 14)
                action_with_due_date["due_date"] = (base_date + timedelta(days=timeframe_days)).isoformat()
                actions_with_due_dates.append(action_with_due_date)
            
            inspection.action_items = actions_with_due_dates
            
            # Update hive analysis timestamp
            hive.last_action_analysis = datetime.now()
            
            db.commit()
            db.refresh(inspection)
            
        logging.info(f"Action item analysis completed for inspection {inspection.id}: {len(analysis.get('actions', []))} actions found")
    except Exception as e:
        logging.error(f"Failed to analyze action items for inspection {inspection.id}: {e}")
        # Don't fail the inspection creation if analysis fails
    
    db.close()
    return inspection

@app.get("/inspections", response_model=list[InspectionResponse])
def list_inspections(request: Request, hive_id: int = None, hive_name: str = None, location: str = None):
    user = require_auth(request)

    db = SessionLocal()

    try:
        user_id = user.id
        
        # Get hives user has access to (own hives + circle hives)
        # Start with own hive IDs
        own_hive_ids = [hive.id for hive in db.query(Hive).filter(Hive.user_id == user_id).all()]
        
        # Try to get circle hive IDs, gracefully handle if Circle tables don't exist
        accessible_hive_ids = own_hive_ids[:]
        try:
            circle_hives = db.query(Hive).join(
                Circle, Hive.user_id == Circle.owner_id
            ).join(
                CircleMembership, Circle.id == CircleMembership.circle_id
            ).filter(
                CircleMembership.user_id == user_id
            ).all()
            accessible_hive_ids.extend([hive.id for hive in circle_hives])
        except Exception as e:
            logging.warning(f"Could not fetch circle hive access: {e}")
            # Continue with just own hives if there's an issue with the Circle feature
        
        # Query inspections for accessible hives
        query = db.query(Inspection).filter(Inspection.hive_id.in_(accessible_hive_ids))
        if hive_id:
            query = query.filter(Inspection.hive_id == hive_id)
        
        # Apply additional filters if provided
        if hive_name or location:
            query = query.join(Hive, Inspection.hive_id == Hive.id)
            if hive_name:
                query = query.filter(Hive.nickname.ilike(f"%{hive_name}%"))
            if location:
                query = query.filter(Hive.location.ilike(f"%{location}%"))
        
        # Sort by inspection_date descending (most recent first), with fallback to timestamp for null dates
        inspections = query.order_by(
            func.coalesce(
                Inspection.inspection_date,
                func.date(Inspection.timestamp)
            ).desc(),
            Inspection.timestamp.desc()
        ).all()
        
        # Fix None photos fields before returning
        for inspection in inspections:
            if inspection.photos is None:
                inspection.photos = []
        
        return inspections
    finally:
        db.close()

class InspectionUpdateRequest(BaseModel):
    inspection_date: Optional[date] = None
    notes: Optional[str] = None
    weather: Optional[str] = Field(None, pattern="^(sunny|cloudy|partly_cloudy|rainy|snowy|)$")
    temperature: Optional[str] = None
    queen_visible: Optional[bool] = None
    eggs_visible: Optional[bool] = None
    larvae_visible: Optional[bool] = None
    capped_brood_visible: Optional[bool] = None
    laying_pattern: Optional[str] = Field(None, pattern="^(poor|patchy|solid|)$")
    activity_level: Optional[str] = Field(None, pattern="^(low|average|high|)$")
    action_items: Optional[List[dict]] = None

@app.put("/inspections/{inspection_id}", response_model=InspectionResponse)
def update_inspection(inspection_id: int, update_data: InspectionUpdateRequest, request: Request):
    user = require_auth(request)
    
    db = SessionLocal()
    try:
        # Get the inspection
        inspection = db.query(Inspection).filter(Inspection.id == inspection_id).first()
        if not inspection:
            raise HTTPException(status_code=404, detail="Inspection not found")
        
        # Check if user owns the hive or has access through a circle
        hive = db.query(Hive).filter(Hive.id == inspection.hive_id).first()
        if not hive:
            raise HTTPException(status_code=404, detail="Associated hive not found")
            
        has_access = (hive.user_id == user.id)
        if not has_access:
            try:
                # Check circle access if Circle tables exist
                has_access = db.query(CircleMembership).join(
                    Circle, CircleMembership.circle_id == Circle.id
                ).filter(
                    CircleMembership.user_id == user.id,
                    Circle.owner_id == hive.user_id
                ).first() is not None
            except Exception as e:
                logging.warning(f"Could not check circle access: {e}")
        
        if not has_access:
            raise HTTPException(status_code=403, detail="Access denied to this inspection")
        
        # Update fields that are provided (not None)
        allowed_fields = {
            "inspection_date", "notes", "weather", "temperature", "queen_visible",
            "eggs_visible", "larvae_visible", "capped_brood_visible", "laying_pattern", 
            "activity_level", "action_items"
        }
        update_data_dict = update_data.model_dump(exclude_unset=True)
        for field, value in update_data_dict.items():
            if field in allowed_fields and hasattr(inspection, field) and value is not None:
                # Convert empty strings to None for optional fields
                if field in ["weather", "laying_pattern", "activity_level"] and value == "":
                    value = None
                setattr(inspection, field, value)
        
        db.commit()
        db.refresh(inspection)
        
        # Fix None photos field before returning
        if inspection.photos is None:
            inspection.photos = []
            
        return inspection
    finally:
        db.close()

@app.get("/data")
def view_raw_data(request: Request):
    user = require_auth(request)
    return inspections

class SaveInspectionRequest(BaseModel):
    transcription: str = ""
    notes: str = ""
    hive_number: str = ""
    weather: Optional[str] = None
    temperature: str = ""
    queen_visible: Optional[bool] = None
    eggs_visible: Optional[bool] = None
    larvae_visible: Optional[bool] = None
    capped_brood_visible: Optional[bool] = None
    laying_pattern: Optional[str] = None
    activity_level: Optional[str] = None

@app.post("/save_inspection")
def save_inspection(data: SaveInspectionRequest, request: Request):
    user = require_auth(request)
    try:
        inspection = {
            "id": str(uuid4()),
            "session_id": user.id,
            "timestamp": datetime.now().isoformat(),
            "transcription": data.transcription,
            "notes": data.notes,
            "hive_number": data.hive_number,
            "user_agent": request.headers.get("User-Agent", ""),
            "ip_address": request.client.host if request.client else None,
            "weather": data.weather,
            "temperature": data.temperature,
            "queen_visible": data.queen_visible,
            "eggs_visible": data.eggs_visible,
            "larvae_visible": data.larvae_visible,
            "capped_brood_visible": data.capped_brood_visible,
            "laying_pattern": data.laying_pattern,
            "activity_level": data.activity_level,
        }
        inspections.append(inspection)
        # TODO: Save to file if needed
        return {"status": "success", "message": "Inspection saved successfully", "inspection_id": inspection["id"]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save inspection: {str(e)}")

def load_openai_config():
    try:
        api_key = os.environ.get("OPENAI_API_KEY")
        if api_key:
            return {"openai_api_key": api_key}
        if os.path.exists("config.yaml"):
            with open("config.yaml", "r") as f:
                return yaml.safe_load(f)
        return {"openai_api_key": None}
    except Exception as e:
        logging.error(f"Error loading OpenAI config: {e}")
        return {"openai_api_key": None}

openai_config = load_openai_config()
openai.api_key = openai_config.get("openai_api_key")

system_prompt = """You are a beekeeping expert assistant. Analyze the hive inspection transcription and extract specific information.\n\nExtract ONLY the following information and respond in JSON format:\n- weather: \"sunny\", \"cloudy\", \"partly_cloudy\", \"rainy\", or \"snowy\" based on weather mentioned\n- temperature: \"under_60\", \"60s\", \"70s\", \"80s\", or \"90_plus\" based on temperature mentioned\n- queen_visible: true if queen is mentioned as seen, false if not mentioned or mentioned as not seen\n- eggs_visible: true if eggs are mentioned as seen, false if not mentioned or mentioned as not seen\n- larvae_visible: true if larvae are mentioned as seen, false if not mentioned or mentioned as not seen\n- capped_brood_visible: true if capped brood is mentioned as seen, false if not mentioned or mentioned as not seen\n- laying_pattern: \"poor\", \"patchy\", or \"solid\" based on the QUALITY/PATTERN of where the queen has laid eggs. \"solid\" means evenly distributed and consistent laying. \"patchy\" means some gaps but generally good pattern. \"poor\" means irregular or poor distribution. DO NOT confuse this with space availability - \"not enough room to lay\" refers to space constraints, not laying pattern quality.\n- activity_level: \"low\", \"average\", or \"high\" based on overall hive activity described\n\nIMPORTANT: \n- \"laying_pattern\" refers to the QUALITY of the egg-laying pattern (solid/even vs patchy vs poor/irregular)\n- Phrases like \"no room to lay\", \"not enough space\", \"crowded\" refer to space constraints, NOT laying pattern quality\n- Only set laying_pattern if the actual pattern/distribution quality of eggs is described\n\nIf a field is not mentioned in the transcription, or if you would return 'unknown', set that field to null or omit it from the JSON.\n\nRespond ONLY with valid JSON like this:\n{\n  \"weather\": \"sunny\",\n  \"temperature\": null,\n  \"queen_visible\": true,\n  \"eggs_visible\": false,\n  \"larvae_visible\": null,\n  \"capped_brood_visible\": true,\n  \"laying_pattern\": \"solid\",\n  \"activity_level\": \"high\"\n}"""

logger = logging.getLogger("hiveguide")
# logging.basicConfig(level=logging.INFO) # This line is now redundant as logging is configured globally

def analyze_transcription_with_gpt(transcription):
    try:
        response = openai.chat.completions.create(
            model="gpt-4.1-nano-2025-04-14",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Analyze this hive inspection: {transcription}"},
            ],
            temperature=0.1,
            max_tokens=200,
        )
        result_text = response.choices[0].message.content.strip()
        logging.info(f"GPT raw output: {result_text}")
        try:
            result = json.loads(result_text)
            structured_data = {}
            for field in [
                "weather", "temperature", "queen_visible", "eggs_visible", "larvae_visible", "capped_brood_visible", "laying_pattern", "activity_level"
            ]:
                value = result.get(field, None)
                if value is not None and value != "unknown":
                    structured_data[field] = value
            logging.info(f"Parsed structured_data: {structured_data}")
            return structured_data
        except json.JSONDecodeError as e:
            logging.error(f"Failed to parse GPT output as JSON: {result_text}")
            return {}
    except Exception as e:
        import traceback
        logging.error(f"GPT analysis error: {e}")
        logging.error(traceback.format_exc())
        return {}

class AnalyzeTextRequest(BaseModel):
    text: str

@app.post("/analyze_text")
def analyze_text(data: AnalyzeTextRequest, request: Request):
    user = require_auth(request)
    text = data.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="No text provided")
    try:
        structured_data = analyze_transcription_with_gpt(text)
        logging.info(f"/analyze_text returning: {structured_data}")
        return {"status": "success", "transcription": text, "structured_data": structured_data}
    except Exception as e:
        import traceback
        logging.error(f"Analyze endpoint error: {e}")
        logging.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail="Analyze failed")

@app.post("/transcribe")
def transcribe_audio(request: Request, audio: UploadFile = File(...)):
    user = require_auth(request)
    try:
        # Save uploaded audio to a temp file
        suffix = ".webm"  # Default, could be improved by sniffing mimetype
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
            temp_file.write(audio.file.read())
            temp_file_path = temp_file.name
        try:
            # Transcribe with Whisper (OpenAI 1.x API)
            with open(temp_file_path, "rb") as audio_file:
                transcript = openai.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                    response_format="text"
                )
            transcription_text = transcript.strip()
            # Analyze with GPT
            structured_data = analyze_transcription_with_gpt(transcription_text)
            return {
                "status": "success",
                "transcription": transcription_text,
                "structured_data": structured_data,
            }
        except Exception as e:
            import traceback
            logging.error(f"Whisper transcription error: {e}")
            logging.error(traceback.format_exc())
            raise HTTPException(status_code=500, detail=f"Whisper transcription failed: {str(e)}")
        finally:
            try:
                os.unlink(temp_file_path)
            except Exception:
                pass
    except Exception as e:
        import traceback
        logging.error(f"Transcribe endpoint error: {e}")
        logging.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail="Transcription failed")

# Assembly AI token generation endpoint for streaming transcription
import httpx

@app.post("/api/assembly-ai-token")
async def generate_assembly_ai_token(request: Request):
    """Generate a temporary token for Assembly AI v3 streaming"""
    # For local development, allow unauthenticated access from localhost
    client_host = str(request.client.host) if request.client else ""
    if client_host in ["127.0.0.1", "localhost", "::1"]:
        # Skip authentication for localhost during development
        user = None
    else:
        # Require authentication for production/remote access
        user = require_auth(request)
    
    if not ASSEMBLY_AI_API_KEY:
        raise HTTPException(status_code=500, detail="Transcription service not configured")
    
    try:
        # Call Assembly AI v3 to generate a temporary token
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://streaming.assemblyai.com/v3/token",
                params={"expires_in_seconds": 600},  # Token expires in 10 minutes (max allowed)
                headers={"Authorization": ASSEMBLY_AI_API_KEY}
            )
            response.raise_for_status()
            token_data = response.json()
            
            logging.info("Generated Assembly AI v3 temporary token")
            return {"token": token_data["token"]}
            
    except httpx.HTTPStatusError as e:
        logging.error(f"Assembly AI v3 token generation failed: {e.response.text}")
        raise HTTPException(status_code=500, detail="Failed to generate transcription token")
    except Exception as e:
        logging.error(f"Assembly AI v3 token generation error: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate transcription token")


# Streaming transcription with WebSocket (using Whisper in small batches)
from fastapi import WebSocket, WebSocketDisconnect
import asyncio
import base64
import wave

@app.websocket("/ws/transcribe")
async def websocket_transcribe(websocket: WebSocket):
    """WebSocket endpoint for near real-time audio streaming and transcription using Whisper"""
    await websocket.accept()
    
    accumulated_transcript = []
    audio_buffer = bytearray()
    
    # Configuration for batch processing - updated for iOS hardware native format
    SAMPLE_RATE = 48000  # Match iOS hardware native sample rate
    BYTES_PER_SAMPLE = 2  # 16-bit audio (iOS sends Int16)
    CHUNK_DURATION_SEC = 2  # Process every 2 seconds of audio
    CHUNK_SIZE_BYTES = SAMPLE_RATE * BYTES_PER_SAMPLE * CHUNK_DURATION_SEC
    
    try:
        # Send ready signal
        await websocket.send_json({"type": "ready", "message": "Streaming transcription ready"})
        
        # Listen for audio data from client
        while True:
            try:
                message = await websocket.receive_json()
                
                if message["type"] == "audio":
                    # Decode base64 audio and add to buffer
                    audio_data = base64.b64decode(message["data"])
                    audio_buffer.extend(audio_data)
                    
                    # Process when we have enough audio (e.g., 2 seconds)
                    if len(audio_buffer) >= CHUNK_SIZE_BYTES:
                        # Extract chunk to process
                        chunk_to_process = bytes(audio_buffer[:CHUNK_SIZE_BYTES])
                        audio_buffer = audio_buffer[CHUNK_SIZE_BYTES:]
                        
                        # Transcribe this chunk with Whisper
                        try:
                            # Save chunk to temporary WAV file
                            with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as temp_file:
                                # Write WAV header and data
                                with wave.open(temp_file.name, 'wb') as wav_file:
                                    wav_file.setnchannels(1)  # Mono
                                    wav_file.setsampwidth(BYTES_PER_SAMPLE)
                                    wav_file.setframerate(SAMPLE_RATE)
                                    wav_file.writeframes(chunk_to_process)
                                
                                temp_file_path = temp_file.name
                            
                            # Transcribe with Whisper
                            with open(temp_file_path, "rb") as audio_file:
                                transcript = await asyncio.get_event_loop().run_in_executor(
                                    None,
                                    lambda: openai.audio.transcriptions.create(
                                        model="whisper-1",
                                        file=audio_file,
                                        response_format="text"
                                    )
                                )
                            
                            transcription_text = transcript.strip()
                            
                            # Clean up temp file
                            try:
                                os.unlink(temp_file_path)
                            except Exception:
                                pass
                            
                            # Only send non-empty transcriptions
                            if transcription_text:
                                accumulated_transcript.append(transcription_text)
                                
                                # Send transcription to client
                                await websocket.send_json({
                                    "type": "transcription",
                                    "text": transcription_text,
                                    "isFinal": True,
                                    "confidence": 0.95,  # Whisper doesn't provide confidence, use default
                                    "accumulatedText": " ".join(accumulated_transcript)
                                })
                        
                        except Exception as e:
                            logging.error(f"Whisper transcription error: {e}")
                            # Continue processing, don't break the stream
                    
                elif message["type"] == "stop":
                    # Process any remaining audio in buffer
                    if len(audio_buffer) > SAMPLE_RATE * BYTES_PER_SAMPLE:  # At least 1 second
                        try:
                            with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as temp_file:
                                with wave.open(temp_file.name, 'wb') as wav_file:
                                    wav_file.setnchannels(1)
                                    wav_file.setsampwidth(BYTES_PER_SAMPLE)
                                    wav_file.setframerate(SAMPLE_RATE)
                                    wav_file.writeframes(bytes(audio_buffer))
                                
                                temp_file_path = temp_file.name
                            
                            with open(temp_file_path, "rb") as audio_file:
                                transcript = await asyncio.get_event_loop().run_in_executor(
                                    None,
                                    lambda: openai.audio.transcriptions.create(
                                        model="whisper-1",
                                        file=audio_file,
                                        response_format="text"
                                    )
                                )
                            
                            transcription_text = transcript.strip()
                            
                            try:
                                os.unlink(temp_file_path)
                            except Exception:
                                pass
                            
                            if transcription_text:
                                accumulated_transcript.append(transcription_text)
                        
                        except Exception as e:
                            logging.error(f"Final chunk transcription error: {e}")
                    
                    # Send final accumulated transcript
                    final_text = " ".join(accumulated_transcript)
                    await websocket.send_json({
                        "type": "final",
                        "text": final_text,
                        "isFinal": True
                    })
                    break
                    
            except WebSocketDisconnect:
                logging.info("Client disconnected from transcription stream")
                break
            except Exception as e:
                logging.error(f"Error processing audio chunk: {e}")
                await websocket.send_json({
                    "type": "error",
                    "error": str(e)
                })
                
    except Exception as e:
        logging.error(f"Streaming transcription error: {e}")
        import traceback
        logging.error(traceback.format_exc())
        await websocket.send_json({
            "type": "error",
            "error": "Streaming transcription failed. Please use regular recording.",
            "fallback": True
        })
    finally:
        try:
            await websocket.close()
        except:
            pass

def require_admin_session(request: Request):
    admin_user = require_auth(request)
    if not admin_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    return {"authenticated": True, "is_admin": True}

# RAG System Endpoints
class RAGQueryRequest(BaseModel):
    question: str
    max_chunks: Optional[int] = 5
    session_id: Optional[str] = None

class RAGResponse(BaseModel):
    answer: str
    sources: list[dict]
    chunk_count: int
    session_id: str

@app.post("/rag/query", response_model=RAGResponse)
async def rag_query(request: Request, query_request: RAGQueryRequest):
    """Query the RAG system for beekeeping information using LangChain"""
    # Get authenticated user for personalized data access
    user = require_auth(request)
    try:
        # Import LangChain RAG service
        from backend.rag.langchain_service import get_langchain_service
        
        service = get_langchain_service()
        
        # Query with conversation memory and user context for personalized data
        result = service.query_with_user_tools(
            question=query_request.question,
            user_id=user.id,
            session_id=query_request.session_id
        )
        
        if not result or not result.get("answer"):
            return RAGResponse(
                answer="I couldn't find relevant information about your question. Please try rephrasing or asking about beekeeping topics covered in our knowledge base.",
                sources=[],
                chunk_count=0,
                session_id=query_request.session_id or "default"
            )
        
        # Get sources (already filtered by LangChain service)
        sources = result.get("sources", [])
        
        # Format sources for frontend compatibility
        formatted_sources = []
        for source in sources:
            formatted_sources.append({
                'document_title': source.get('document_title', 'Unknown'),
                'similarity': source.get('similarity', 0.0),
                'chunk_preview': source.get('chunk_text', ''),
                'page_number': source.get('page_number'),
                'organization': source.get('organization'),
                'publication_year': source.get('publication_year'),
                'source_url': source.get('source_url')
            })
        
        return RAGResponse(
            answer=result["answer"],
            sources=formatted_sources,
            chunk_count=len(sources),
            session_id=query_request.session_id or "default"
        )
        
    except Exception as e:
        logging.error(f"LangChain RAG query failed: {e}")
        raise HTTPException(status_code=500, detail=f"RAG system error: {str(e)}")

@app.get("/rag/status")
async def rag_status():
    """Check RAG system status"""
    try:
        # Import RAG models only when needed
        from backend.rag.models import DocumentChunk
        
        # Use local DocumentChunk model and database session
        session = SessionLocal()
        
        try:
            total_chunks = session.query(DocumentChunk).count()
            embedded_chunks = session.query(DocumentChunk).filter(
                (DocumentChunk.embedding.isnot(None)) & 
                (DocumentChunk.embedding_vector.isnot(None))
            ).count()
            
            return {
                "status": "operational" if embedded_chunks > 0 else "no_embeddings",
                "total_chunks": total_chunks,
                "embedded_chunks": embedded_chunks,
                "embedding_percentage": round((embedded_chunks/total_chunks)*100, 1) if total_chunks > 0 else 0
            }
        finally:
            session.close()
            
    except Exception as e:
        logging.error(f"RAG status check failed: {e}")
        return {"status": "error", "message": str(e)}

@app.post("/rag/clear-memory")
async def clear_rag_memory():
    """Clear conversation memory for RAG system"""
    try:
        from backend.rag.langchain_service import get_langchain_service
        
        service = get_langchain_service()
        service.clear_memory()
        
        return {"status": "success", "message": "Conversation memory cleared"}
        
    except Exception as e:
        logging.error(f"Failed to clear RAG memory: {e}")
        raise HTTPException(status_code=500, detail=f"Memory clear error: {str(e)}")

@app.get("/rag/chat-history")
async def get_rag_chat_history():
    """Get current RAG conversation history"""
    try:
        from backend.rag.langchain_service import get_langchain_service
        
        service = get_langchain_service()
        history = service.get_chat_history()
        
        return {"chat_history": history}
        
    except Exception as e:
        logging.error(f"Failed to get RAG chat history: {e}")
        raise HTTPException(status_code=500, detail=f"Chat history error: {str(e)}")

@app.post("/rag/process-pdfs")
async def process_pdfs():
    """Process PDFs and generate embeddings using LangChain"""
    try:
        from backend.rag.langchain_service import get_langchain_service
        from pathlib import Path
        
        service = get_langchain_service()
        
        # Process PDFs from the sources directory
        base_dir = Path(__file__).resolve().parent / "rag"
        source_dir = base_dir / "sources"
        
        if not source_dir.exists():
            return {"status": "error", "message": "Sources directory not found"}
        
        service.process_pdfs(source_dir)
        
        return {"status": "success", "message": "PDFs processed successfully"}
        
    except Exception as e:
        logging.error(f"PDF processing failed: {e}")
        raise HTTPException(status_code=500, detail=f"PDF processing error: {str(e)}")

@app.post("/rag/generate-embeddings")
async def generate_embeddings():
    """Generate embeddings for existing chunks that don't have them"""
    try:
        from backend.rag.langchain_service import get_langchain_service
        
        service = get_langchain_service()
        service.generate_embeddings_for_existing_chunks()
        
        return {"status": "success", "message": "Embeddings generated for existing chunks"}
        
    except Exception as e:
        logging.error(f"Embedding generation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Embedding generation error: {str(e)}")

# Dashboard endpoints for Hive Overview with Smart Action Items

class DashboardHive(BaseModel):
    """Response model for dashboard hive data"""
    id: int
    nickname: str
    location: Optional[str]
    description: Optional[str]
    photo_url: Optional[str]
    urgency_color: str  # "red", "yellow", "green"
    urgency_score: int
    last_inspection_date: Optional[str]
    days_since_inspection: Optional[int]
    action_items: List[dict]
    overdue: bool
    next_action_due_date: Optional[str]

class DashboardResponse(BaseModel):
    """Response model for dashboard overview"""
    apiaries: dict  # grouped by location
    summary: dict
    total_hives: int
    urgent_count: int
    attention_count: int
    good_count: int

@app.get("/api/dashboard", response_model=DashboardResponse)
def get_dashboard(request: Request):
    """Get comprehensive dashboard overview with action items and urgency status"""
    user = require_auth(request)
    db = SessionLocal()
    
    try:
        # Get all user's hives with their latest inspection
        hives = db.query(Hive).filter(Hive.user_id == user.id).all()
        
        dashboard_hives = []
        urgent_count = 0
        attention_count = 0
        good_count = 0
        
        for hive in hives:
            # Get latest inspection - order by inspection_date first, fallback to timestamp
            # Use COALESCE to handle null inspection_date values (inspection_date or DATE(timestamp))
            latest_inspection = db.query(Inspection).filter(
                Inspection.hive_id == hive.id
            ).order_by(
                func.coalesce(
                    Inspection.inspection_date,
                    func.date(Inspection.timestamp)
                ).desc(),
                Inspection.timestamp.desc()
            ).first()
            
            # Calculate days since inspection - use inspection_date if available, otherwise timestamp
            days_since = None
            last_inspection_date = None
            if latest_inspection:
                # Prefer inspection_date, fallback to timestamp
                last_inspection_date = getattr(latest_inspection, 'inspection_date', None) or latest_inspection.timestamp.date()
                days_since = (datetime.now().date() - last_inspection_date).days
            
            # Select action items to display: prefer latest inspection only; otherwise fallback to most recent pending
            action_items = []
            next_due_date = None
            if latest_inspection:
                # Prefer showing only the latest inspection's action items
                if latest_inspection.action_items:
                    action_items = latest_inspection.action_items
                    next_due_date = latest_inspection.action_due_date
                else:
                    # Fallback: find most recent previous inspection with pending actions due today or later
                    today = datetime.now().date()
                    previous_with_pending = db.query(Inspection).filter(
                        Inspection.hive_id == hive.id,
                        Inspection.id != latest_inspection.id,
                        Inspection.action_items.isnot(None),
                        Inspection.action_due_date.isnot(None),
                        Inspection.action_due_date >= today
                    ).order_by(
                        func.coalesce(
                            Inspection.inspection_date,
                            func.date(Inspection.timestamp)
                        ).desc(),
                        Inspection.timestamp.desc()
                    ).first()
                    if previous_with_pending:
                        action_items = previous_with_pending.action_items
                        next_due_date = previous_with_pending.action_due_date
            
            # Prepare hive data for urgency calculation
            hive_data = {
                "last_inspection_date": last_inspection_date,
                "action_items": action_items
            }
            
            # Calculate urgency
            urgency_color, urgency_score = get_hive_urgency(hive_data)
            
            # Count urgency categories
            if urgency_color == "red":
                urgent_count += 1
            elif urgency_color == "yellow":
                attention_count += 1
            else:
                good_count += 1
            
            # Create dashboard hive object
            dashboard_hive = DashboardHive(
                id=hive.id,
                nickname=hive.nickname,
                location=hive.location or "Unknown Location",
                description=hive.description,
                photo_url=hive.photo_url,
                urgency_color=urgency_color,
                urgency_score=urgency_score,
                last_inspection_date=last_inspection_date.isoformat() if last_inspection_date else None,
                days_since_inspection=days_since,
                action_items=action_items,
                overdue=(True if (days_since is not None and days_since > 14) else False),
                next_action_due_date=next_due_date.isoformat() if next_due_date else None
            )
            dashboard_hives.append(dashboard_hive)
        
        # Group hives by location (apiary)
        apiaries = {}
        for hive in dashboard_hives:
            location = hive.location or "Unknown Location"
            if location not in apiaries:
                apiaries[location] = []
            apiaries[location].append(hive)
        
        # Sort hives within each apiary by urgency (most urgent first)
        for location in apiaries:
            apiaries[location].sort(key=lambda h: h.urgency_score, reverse=True)
        
        return DashboardResponse(
            apiaries=apiaries,
            summary={
                "urgent": urgent_count,
                "attention": attention_count,
                "good": good_count
            },
            total_hives=len(hives),
            urgent_count=urgent_count,
            attention_count=attention_count,
            good_count=good_count
        )
        
    finally:
        db.close()

@app.post("/inspections/{inspection_id}/analyze")
def analyze_inspection_action_items(inspection_id: int, request: Request):
    """Re-analyze inspection for action items using LLM"""
    user = require_auth(request)
    db = SessionLocal()
    
    try:
        # Get inspection and verify ownership
        inspection = db.query(Inspection).filter(Inspection.id == inspection_id).first()
        if not inspection:
            raise HTTPException(status_code=404, detail="Inspection not found")
        
        # Verify user owns the hive
        hive = db.query(Hive).filter(Hive.id == inspection.hive_id).first()
        if not hive or hive.user_id != user.id:
            raise HTTPException(status_code=403, detail="Access denied")
        
        # Analyze inspection notes
        # Pass inspection_date to filter seasonal suggestions
        inspection_date_for_analysis = getattr(inspection, 'inspection_date', None)
        analysis = analyze_inspection_for_actions(
            inspection.notes or "",
            inspection.transcription or "",
            inspection_date=inspection_date_for_analysis
        )
        
        # Update inspection with action items, adding individual due dates
        if analysis.get("actions"):
            actions_with_due_dates = []
            # Use inspection_date if available, otherwise fallback to timestamp
            base_date = getattr(inspection, 'inspection_date', None) or inspection.timestamp.date()
            for action in analysis["actions"]:
                action_with_due_date = action.copy()
                timeframe_days = action.get("timeframe_days", 14)
                action_with_due_date["due_date"] = (base_date + timedelta(days=timeframe_days)).isoformat()
                actions_with_due_dates.append(action_with_due_date)
            
            inspection.action_items = actions_with_due_dates
        else:
            inspection.action_items = []
        
        # Update hive analysis timestamp
        hive.last_action_analysis = datetime.now()
        
        db.commit()
        
        return {
            "status": "success",
            "analysis": analysis,
            "action_items": inspection.action_items
        }
        
    finally:
        db.close()

@app.put("/hives/{hive_id}/actions")
def update_hive_actions(hive_id: int, request: Request, actions: dict):
    """Manually update or dismiss action items for a hive"""
    user = require_auth(request)
    db = SessionLocal()
    
    try:
        # Verify hive ownership
        hive = db.query(Hive).filter(Hive.id == hive_id, Hive.user_id == user.id).first()
        if not hive:
            raise HTTPException(status_code=404, detail="Hive not found")
        
        # Get latest inspection
        latest_inspection = db.query(Inspection).filter(
            Inspection.hive_id == hive_id
        ).order_by(Inspection.timestamp.desc()).first()
        
        if not latest_inspection:
            raise HTTPException(status_code=404, detail="No inspections found for this hive")
        
        # Update action items
        latest_inspection.action_items = actions.get("action_items", [])
        
        # Update action due date if provided
        if actions.get("action_due_date"):
            latest_inspection.action_due_date = datetime.fromisoformat(actions["action_due_date"]).date()
        
        db.commit()
        
        return {
            "status": "success",
            "message": "Action items updated successfully"
        }
        
    finally:
        db.close()

# Move this to the end to avoid shadowing API routes
@app.get("/{full_path:path}")
async def serve_react_app(full_path: str):
    # Don't intercept WebSocket endpoints
    if full_path.startswith("ws/"):
        raise HTTPException(status_code=404, detail="Not found")
    
    file_path = os.path.join(static_dir, full_path)
    if os.path.exists(file_path):
        return FileResponse(file_path)
    else:
        # For client-side routing, serve index.html
        return FileResponse(os.path.join(static_dir, 'index.html'))