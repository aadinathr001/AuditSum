from fastapi import APIRouter, Request, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.db import get_session
from app.security.auth import authenticate_user, get_current_user
from app.audit.service import append_event

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    email: str
    password: str


@router.post("/login")
def login(data: LoginRequest, request: Request, session: Session = Depends(get_session)):
    try:
        user = authenticate_user(session, data.email, data.password)
    except HTTPException:
        append_event(
            session,
            actor_id=None,
            actor_role=None,
            action="auth.login.failure",
            entity_type="user",
            entity_id=None,
            payload={"email": data.email},
        )
        raise

    request.session["user_id"] = user.id
    request.session["role"] = user.role

    append_event(
        session,
        actor_id=user.id,
        actor_role=user.role,
        action="auth.login.success",
        entity_type="user",
        entity_id=user.id,
        payload={"email": user.email},
    )

    return {"message": "Logged in", "email": user.email, "role": user.role}


@router.post("/logout")
def logout(request: Request, session: Session = Depends(get_session)):
    user_id = request.session.get("user_id")
    role = request.session.get("role")

    request.session.clear()

    if user_id is not None:
        append_event(
            session,
            actor_id=user_id,
            actor_role=role,
            action="auth.logout",
            entity_type="user",
            entity_id=user_id,
            payload={},
        )

    return {"message": "Logged out"}