import os
from dotenv import load_dotenv
load_dotenv()
from fastapi import APIRouter, Request, Depends, Form, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from app.templates import templates
from app.db import get_session
from app.security.auth import authenticate_user, get_current_user
from app.audit.service import append_event
from sqlalchemy import select
import hashlib
import json

from app.models import Document, DocumentContent, Run, RunStep, AuditEvent
from app.policy.service import run_policy_checks
from app.pipeline.tokens import choose_strategy
from app.pipeline.summarize import run_map_reduce
from app.pipeline.citations import verify_quote
from app.pipeline.prompts import SUMMARIZE_SYSTEM_PROMPT
from app.llm.openai_compat import make_groq_provider
from app.llm.mock import MockProvider
from app.models import Citation
from app.audit.verify import verify_chain
from app.security.rbac import require_role
from fastapi import UploadFile
from app.pipeline.run_service import execute_run
from app.rate_limit import limiter
from app.rate_limit import limiter, RUN_RATE_LIMIT
from app.models import User, Control


router = APIRouter(prefix="/ui", tags=["ui"])


@router.get("/login")
def login_page(request: Request, reason: str | None = None):
    message = None
    if reason == "session_expired":
        message = "Your session expired or you're not logged in. Please log in again."

    return templates.TemplateResponse(request, "login.html", {"message": message})

@router.post("/login")
def login_submit(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    session: Session = Depends(get_session),
):
    try:
        user = authenticate_user(session, email, password)
    except HTTPException:
        append_event(
            session, actor_id=None, actor_role=None,
            action="auth.login.failure", entity_type="user", entity_id=None,
            payload={"email": email},
        )
        return templates.TemplateResponse(request, "login.html", {"error": "Invalid email or password"})

    request.session["user_id"] = user.id
    request.session["role"] = user.role

    append_event(
        session, actor_id=user.id, actor_role=user.role,
        action="auth.login.success", entity_type="user", entity_id=user.id,
        payload={"email": user.email},
    )

    return RedirectResponse(url="/ui/", status_code=303)


@router.get("/")
def home_page(request: Request, current_user: dict = Depends(get_current_user)):
    return templates.TemplateResponse(request, "home.html", {"current_user": current_user})

@router.get("/upload")
def upload_page(request: Request, current_user: dict = Depends(get_current_user)):
    return templates.TemplateResponse(request, "upload.html")


@router.post("/upload")
async def upload_submit(
    request: Request,
    file: UploadFile,
    current_user: dict = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    raw_bytes = await file.read()
    try:
        text = raw_bytes.decode("utf-8")
    except UnicodeDecodeError:
        return templates.TemplateResponse(request, "upload.html", {"error": "Could not decode file as UTF-8"})

    sha256 = hashlib.sha256(text.encode("utf-8")).hexdigest()

    document = Document(
        owner_id=current_user["id"], filename=file.filename, sha256=sha256,
        size_bytes=len(raw_bytes), encoding="utf-8", status="uploaded",
    )
    session.add(document)
    session.flush()
    session.add(DocumentContent(document_id=document.id, text=text))

    append_event(
        session, actor_id=current_user["id"], actor_role=current_user["role"],
        action="document.uploaded", entity_type="document", entity_id=document.id,
        payload={"filename": file.filename, "sha256": sha256, "size_bytes": len(raw_bytes)},
    )
    session.commit()

    decisions = run_policy_checks(
        session, text=text, filename=file.filename, document_id=document.id,
        actor_id=current_user["id"], actor_role=current_user["role"],
    )

    denied = [d for d in decisions if d.outcome == "deny"]
    if denied:
        document.status = "denied"
        session.commit()

    return templates.TemplateResponse(request, "upload.html", {
        "document": document,
        "policy_decisions": [{"check": d.check_name, "outcome": d.outcome, "reason": d.reason} for d in decisions],
    })


@router.post("/documents/{document_id}/runs")
@limiter.limit(RUN_RATE_LIMIT)
async def run_submit(
    request: Request,
    document_id: int,
    current_user: dict = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    document = session.get(Document, document_id)

    run = await execute_run(session, document=document, actor_id=current_user["id"], actor_role=current_user["role"])

    steps = session.scalars(select(RunStep).where(RunStep.run_id == run.id)).all()

    return templates.TemplateResponse(request, "run_detail.html", {
        "run": run, "result": run.parsed_result,
        "key_points_with_verification": run.key_points_with_verification,
        "verified_count": run.verified_count, "total_count": run.total_count,
        "steps": steps,
    })


@router.get("/audit")
def audit_page(
    request: Request,
    current_user: dict = Depends(require_role("admin", "auditor")),
    session: Session = Depends(get_session),
):
    events = session.scalars(select(AuditEvent).order_by(AuditEvent.seq.desc()).limit(20)).all()
    return templates.TemplateResponse(request, "audit.html", {"events": events})


@router.post("/audit/verify")
def audit_verify_submit(
    request: Request,
    current_user: dict = Depends(require_role("admin", "auditor")),
    session: Session = Depends(get_session),
):
    result = verify_chain(session)
    events = session.scalars(select(AuditEvent).order_by(AuditEvent.seq.desc()).limit(20)).all()
    return templates.TemplateResponse(request, "audit.html", {"verify_result": result, "events": events})

@router.post("/logout")
def logout_submit(request: Request):
    request.session.clear()
    return RedirectResponse(url="/ui/login", status_code=303)



@router.get("/admin")
def admin_page(
    request: Request,
    current_user: dict = Depends(require_role("admin")),
    session: Session = Depends(get_session),
):
    users = session.scalars(select(User)).all()
    documents = session.scalars(select(Document).order_by(Document.id.desc()).limit(20)).all()
    runs = session.scalars(select(Run).order_by(Run.id.desc()).limit(20)).all()
    controls = session.scalars(select(Control)).all()

    return templates.TemplateResponse(request, "admin.html", {
        "users": users,
        "documents": documents,
        "runs": runs,
        "controls": controls,
    })