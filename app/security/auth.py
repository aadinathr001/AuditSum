from fastapi import Request, HTTPException, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from app.models import User
from app.db import get_session

hasher = PasswordHasher()


def authenticate_user(session: Session, email: str, password: str) -> User:
    user = session.scalar(select(User).where(User.email == email))

    if user is None:
        raise HTTPException(status_code=401, detail="Invalid email or password")

    try:
        hasher.verify(user.password_hash, password)
    except VerifyMismatchError:
        raise HTTPException(status_code=401, detail="Invalid email or password")

    return user


def get_current_user(request: Request) -> dict:
    user_id = request.session.get("user_id")
    if user_id is None:
        raise HTTPException(status_code=401, detail="Not logged in")
    return {"id": user_id, "role": request.session.get("role")}