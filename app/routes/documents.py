import hashlib
from fastapi import APIRouter, UploadFile, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_session
from app.security.auth import get_current_user
from app.models import Document, DocumentContent
from app.audit.service import append_event
from app.policy.service import run_policy_checks

router = APIRouter(prefix="/documents", tags=["documents"])

ALLOWED_EXTENSIONS = (".txt", ".md")


@router.post("")
def upload_document(
    file: UploadFile,
    current_user: dict = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    raw_bytes = file.file.read()

    try:
        text = raw_bytes.decode("utf-8")
        encoding = "utf-8"
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="Could not decode file as UTF-8")

    sha256 = hashlib.sha256(text.encode("utf-8")).hexdigest()

    document = Document(
        owner_id=current_user["id"],
        filename=file.filename,
        sha256=sha256,
        size_bytes=len(raw_bytes),
        encoding=encoding,
        status="uploaded",
    )
    session.add(document)
    session.flush()  # assigns document.id without fully committing yet

    session.add(DocumentContent(document_id=document.id, text=text))

    append_event(
        session,
        actor_id=current_user["id"],
        actor_role=current_user["role"],
        action="document.uploaded",
        entity_type="document",
        entity_id=document.id,
        payload={"filename": file.filename, "sha256": sha256, "size_bytes": len(raw_bytes)},
    )

    session.commit()

    decisions = run_policy_checks(
        session,
        text=text,
        filename=file.filename,
        document_id=document.id,
        actor_id=current_user["id"],
        actor_role=current_user["role"],
    )

    denied = [d for d in decisions if d.outcome == "deny"]
    if denied:
        document.status = "denied"
        session.commit()
        raise HTTPException(status_code=400, detail=f"Document denied: {denied[0].reason}")

    return {
        "document_id": document.id,
        "status": document.status,
        "policy_decisions": [{"check": d.check_name, "outcome": d.outcome, "reason": d.reason} for d in decisions],
    }

from sqlalchemy import select
from app.models import PolicyDecision as PolicyDecisionRow


@router.get("")
def list_documents(
    current_user: dict = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    if current_user["role"] in ("admin", "auditor"):
        documents = session.scalars(select(Document)).all()
    else:
        documents = session.scalars(select(Document).where(Document.owner_id == current_user["id"])).all()

    return [
        {"id": d.id, "filename": d.filename, "status": d.status, "size_bytes": d.size_bytes}
        for d in documents
    ]


@router.get("/{document_id}")
def get_document(
    document_id: int,
    current_user: dict = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    document = session.get(Document, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")

    if current_user["role"] not in ("admin", "auditor") and document.owner_id != current_user["id"]:
        raise HTTPException(status_code=403, detail="Not your document")

    decisions = session.scalars(
        select(PolicyDecisionRow).where(PolicyDecisionRow.document_id == document_id)
    ).all()

    return {
        "id": document.id,
        "filename": document.filename,
        "status": document.status,
        "sha256": document.sha256,
        "size_bytes": document.size_bytes,
        "created_at": document.created_at,
        "policy_decisions": [
            {"check": d.check_name, "outcome": d.outcome, "reason": d.reason} for d in decisions
        ],
    }