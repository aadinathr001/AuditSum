from app.db import engine
from sqlalchemy.orm import Session

from app.audit.service import append_event

with Session(engine) as session:
    e1 = append_event(
        session,
        actor_id=None,
        actor_role=None,
        action="auth.login.success",
        entity_type="user",
        entity_id=1,
        payload={"email": "test@example.com"},
    )
    print(f"seq={e1.seq} prev_hash={e1.prev_hash[:12]}... hash={e1.hash[:12]}...")

    e2 = append_event(
        session,
        actor_id=1,
        actor_role="admin",
        action="document.uploaded",
        entity_type="document",
        entity_id=1,
        payload={"filename": "test.txt", "size_bytes": 1234},
    )
    print(f"seq={e2.seq} prev_hash={e2.prev_hash[:12]}... hash={e2.hash[:12]}...")

    e3 = append_event(
        session,
        actor_id=1,
        actor_role="admin",
        action="run.completed",
        entity_type="run",
        entity_id=1,
        payload={"model": "gpt-oss-120b", "tokens": 500},
    )
    print(f"seq={e3.seq} prev_hash={e3.prev_hash[:12]}... hash={e3.hash[:12]}...")