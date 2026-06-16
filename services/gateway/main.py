import uuid
import logging
from typing import Dict, Any, Optional
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr
from datetime import timedelta
import os

from shared.db import get_db, Base, engine
from shared.models import User, Organization, UserRole, AuditLog
from shared.auth import hash_password, verify_password, create_access_token, get_current_user

logger = logging.getLogger("orqix.gateway")

app = FastAPI(title="Orqix API Gateway & Authentication Service", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def startup_event():
    # Make sure tables exist on launch
    Base.metadata.create_all(bind=engine)

class RegisterRequest(BaseModel):
    organization_name: str
    email: EmailStr
    password: str
    role: Optional[UserRole] = UserRole.RESEARCHER

@app.post("/auth/register")
def register_organization_and_user(req: RegisterRequest, db: Session = Depends(get_db)):
    # Check if email exists
    existing_user = db.query(User).filter(User.email == req.email).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="A user with this email already exists")

    org_id = f"org_{uuid.uuid4().hex[:8]}"
    user_id = f"usr_{uuid.uuid4().hex[:8]}"

    # Create Org
    org = Organization(id=org_id, name=req.organization_name)
    db.add(org)
    
    # Create User
    user = User(
        id=user_id,
        org_id=org_id,
        email=req.email,
        password_hash=hash_password(req.password),
        role=req.role.value if req.role else UserRole.RESEARCHER.value
    )
    db.add(user)
    
    # Create audit trail
    audit = AuditLog(
        org_id=org_id,
        user_id=user_id,
        action="REGISTER",
        resource="auth",
        details={"email": req.email, "role": user.role}
    )
    db.add(audit)
    
    db.commit()
    db.refresh(user)

    return {
        "user_id": user.id,
        "email": user.email,
        "organization_id": org.id,
        "organization_name": org.name,
        "role": user.role
    }

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

@app.post("/auth/login")
def login_user(req: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == req.email).first()
    if not user or not verify_password(req.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Load organization
    org = db.query(Organization).filter(Organization.id == user.org_id).first()
    
    access_token = create_access_token(
        data={"sub": user.email, "id": user.id, "org_id": user.org_id, "role": user.role}
    )
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user_id": user.id,
        "email": user.email,
        "organization_id": user.org_id,
        "organization_name": org.name if org else "Orqix Labs",
        "role": user.role
    }

@app.get("/auth/me")
def get_user_profile(current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    org = db.query(Organization).filter(Organization.id == current_user["org_id"]).first()
    return {
        "id": current_user["id"],
        "email": current_user["sub"],
        "organization_id": current_user["org_id"],
        "organization_name": org.name if org else "Orqix Labs",
        "role": current_user["role"]
    }

from sqlalchemy import text
from shared.kafka import event_broker

@app.get("/health")
def health_check(db: Session = Depends(get_db)):
    postgres_ok = False
    try:
        db.execute(text("SELECT 1"))
        postgres_ok = True
    except Exception as e:
        logger.error(f"Health check Postgres failure: {e}")

    redis_ok = False
    try:
        event_broker.redis_client.ping()
        redis_ok = True
    except Exception as e:
        logger.error(f"Health check Redis failure: {e}")

    return {
        "postgres": "online" if postgres_ok else "offline",
        "redis": "online" if redis_ok else "offline",
        "kafka": "online" if event_broker.use_kafka else "offline"
    }

# Serve static dashboard
static_dir = "d:/projects/Orqix/services/gateway/static"
if os.path.exists(static_dir):
    app.mount("/dashboard/static", StaticFiles(directory=static_dir), name="static")

@app.get("/", response_class=HTMLResponse)
@app.get("/dashboard", response_class=HTMLResponse)
def get_dashboard():
    return FileResponse("d:/projects/Orqix/services/gateway/static/index.html")
