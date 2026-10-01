from fastapi import HTTPException, Depends, Request
from sqlalchemy.orm import Session

from app.security.auth import get_current_user
from app.db import get_session
from app.audit.service import append_event


def require_role(*allowed_roles: str):
    def dependency(
        current_user: dict = Depends(get_current_user),
        session: Session = Depends(get_session),
    ):
        if current_user["role"] not in allowed_roles:
            append_event(
                session,
                actor_id=current_user["id"],
                actor_role=current_user["role"],
                action="rbac.denied",
                entity_type=None,
                entity_id=None,
                payload={"required_roles": list(allowed_roles)},
            )
            raise HTTPException(status_code=403, detail="Forbidden: insufficient role")
        return current_user
    return dependency