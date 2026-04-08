from datetime import UTC, datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session
from fastapi import Depends, HTTPException, Header

try:
    from .settings import settings
except ImportError:
    from settings import settings

# JWT settings
SECRET_KEY = settings.jwt_secret_key
ALGORITHM = "HS256"
TOKEN_EXPIRY_MINUTES = settings.token_expiry_minutes

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain password against a hashed password."""
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(user_id: str, expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT access token."""
    if expires_delta is None:
        expires_delta = timedelta(minutes=TOKEN_EXPIRY_MINUTES)

    expire = datetime.now(UTC) + expires_delta
    to_encode = {"sub": user_id, "exp": expire}

    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def verify_token(token: str) -> Optional[str]:
    """Verify a JWT token and return the user_id (sub claim)."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            return None
        return user_id
    except JWTError:
        return None


def authenticate_user(db: Session, username: str, password: str):
    """Authenticate user by username and password."""
    try:
        from .models import User
    except ImportError:
        from models import User
    user = db.query(User).filter(User.username == username).first()
    if not user or not verify_password(password, user.hashed_password):
        return None
    return user


def get_current_user(
    authorization: Optional[str] = Header(None),
) -> str:
    """Dependency to get current user_id from JWT token in Authorization header."""
    if authorization is None:
        raise HTTPException(status_code=401, detail="Chybí autorizační token")

    # Parse "Bearer <token>"
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(status_code=401, detail="Neplatný formát tokenu")

    token = parts[1]
    user_id = verify_token(token)
    if user_id is None:
        raise HTTPException(status_code=401, detail="Neplatný nebo vypršelý token")

    return user_id
