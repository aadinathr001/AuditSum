from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_session
from app.security.rbac import require_role
from app.audit.verify import verify_chain

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("/verify")
def verify(
    current_user: dict = Depends(require_role("admin", "auditor")),
    session: Session = Depends(get_session),
):
    result = verify_chain(session)
    return {
        "ok": result.ok,
        "checked": result.checked,
        "head_seq": result.head_seq,
        "head_hash": result.head_hash,
        "first_broken_seq": result.first_broken_seq,
        "reason": result.reason,
    }