from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from app.db.session import SessionLocal
from app.db.models import User
from app.security.passwords import verify_password
from app.security.jwt import create_access_token
from app.security.deps import get_current_user

router = APIRouter()

class LoginRequest(BaseModel):
    email: str
    password: str

class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"

@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest):
    db = SessionLocal()
    user = db.query(User).filter(User.email == payload.email).first()
    db.close()

    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_access_token({
        "user_id": user.id,
        "email": user.email,
        "role": user.role,
        "organization_id": user.organization_id,
    })

    return LoginResponse(access_token=token)

@router.get("/me")
def me(user: User = Depends(get_current_user)):
    return {
        "user_id": user.id,
        "email": user.email,
        "role": user.role,
        "organization_id": user.organization_id,
    }