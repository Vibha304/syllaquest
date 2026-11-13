from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User
from ..security import create_token, current_user, hash_password, verify_password
from ..services import gamification as game

router = APIRouter(prefix="/api/auth", tags=["auth"])


class RegisterIn(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    email: EmailStr
    password: str = Field(min_length=6, max_length=100)
    role: str = Field(default="student", pattern="^(student|teacher)$")


class LoginIn(BaseModel):
    email: EmailStr
    password: str


def user_out(user: User) -> dict:
    return {
        "id": user.id, "name": user.name, "email": user.email, "role": user.role,
        "streak": game.current_streak(user), "longest_streak": user.longest_streak,
        **game.level_info(user.xp),
    }


@router.post("/register")
def register(body: RegisterIn, db: Session = Depends(get_db)):
    email = body.email.lower()
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(409, "An account with this email already exists")
    user = User(name=body.name.strip(), email=email, password_hash=hash_password(body.password), role=body.role)
    db.add(user)
    db.commit()
    return {"token": create_token(user), "user": user_out(user)}


@router.post("/login")
def login(body: LoginIn, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == body.email.lower()))
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(401, "Incorrect email or password")
    return {"token": create_token(user), "user": user_out(user)}


@router.get("/me")
def me(user: User = Depends(current_user)):
    return user_out(user)
