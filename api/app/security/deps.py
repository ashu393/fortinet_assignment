from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.db.session import SessionLocal
from app.db.models import User
from app.security.jwt import decode_access_token

bearer = HTTPBearer(auto_error=False)

def get_current_user(creds: HTTPAuthorizationCredentials = Depends(bearer)) -> User:
    if not creds:
        raise HTTPException(status_code=401, detail="Missing Authorization header")

    token = creds.credentials
    try:
        payload = decode_access_token(token)
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid token")

    user_id = payload.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token payload")

    db = SessionLocal()
    user = db.get(User, user_id)
    db.close()

    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user