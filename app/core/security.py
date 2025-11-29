from jose import JWTError, jwt
from datetime import datetime, timedelta
from typing import Optional
from app.core.config import settings
import hashlib
import secrets

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Simple password verification using SHA256 (for development only)"""
    # In production, you should use bcrypt or argon2
    return get_password_hash(plain_password) == hashed_password

def get_password_hash(password: str) -> str:
    """Simple password hashing using SHA256 (for development only)"""
    # Add a pepper to make it slightly more secure (in production, use proper salt)
    pepper = "evoting-pepper-2024"
    salted_password = password + pepper
    return hashlib.sha256(salted_password.encode()).hexdigest()

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

def verify_token(token: str) -> Optional[dict]:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except JWTError:
        return None