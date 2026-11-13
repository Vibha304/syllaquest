"""JWT auth with PBKDF2 password hashing (standard library only)."""
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from .config import SECRET_KEY, TOKEN_HOURS
from .database import get_db
from .models import User

_ITER = 200_000
_bearer = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), _ITER).hex()
    return f"pbkdf2${_ITER}${salt}${digest}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _, iters, salt, digest = stored.split("$")
        check = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), int(iters)).hex()
        return hmac.compare_digest(check, digest)
    except Exception:
        return False


def create_token(user: User) -> str:
    payload = {
        "sub": str(user.id),
        "role": user.role,
        "exp": datetime.now(timezone.utc) + timedelta(hours=TOKEN_HOURS),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")


def current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer), db: Session = Depends(get_db)
) -> User:
    if creds is None:
        raise HTTPException(401, "Not authenticated")
    try:
        payload = jwt.decode(creds.credentials, SECRET_KEY, algorithms=["HS256"])
        user = db.get(User, int(payload["sub"]))
    except Exception:
        user = None
    if user is None:
        raise HTTPException(401, "Session expired, please sign in again")
    return user


def teacher_only(user: User = Depends(current_user)) -> User:
    if user.role != "teacher":
        raise HTTPException(403, "This area is for teachers")
    return user
