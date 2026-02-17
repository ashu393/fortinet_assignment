from datetime import datetime, timedelta
from jose import jwt, JWTError
from app.config import settings

def create_access_token(claims: dict, expires_minutes: int | None = None) -> str:
    expire = datetime.utcnow() + timedelta(minutes=expires_minutes or settings.access_token_expires_min)
    to_encode = {**claims, "exp": expire}
    return jwt.encode(to_encode, settings.jwt_secret, algorithm=settings.jwt_alg)

def decode_access_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_alg])
        return payload
    except JWTError as e:
        raise ValueError("Invalid token") from e