from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.models import AuditEvent
from app.audit.canonical import canonical_json
from app.audit.hashing import sha256_hex, utc_now_canonical

GENESIS_HASH = "0" * 64

from sqlalchemy import text

AUDIT_LOCK_KEY = 727001  # arbitrary but fixed number, shared by anything locking this resource


def append_event(
    session: Session,
    *,
    actor_id: int | None,
    actor_role: str | None,
    action: str,
    entity_type: str | None = None,
    entity_id: int | None = None,
    request_id: str | None = None,
    trace_id: str | None = None,
    payload: dict,
) -> AuditEvent:
    session.execute(text("SELECT pg_advisory_xact_lock(:k)"), {"k": AUDIT_LOCK_KEY})

    # 1. Find the last row in the chain (if any)
    last = session.scalar(
        select(AuditEvent).order_by(AuditEvent.seq.desc()).limit(1)
    )
    prev_hash = last.hash if last else GENESIS_HASH
    seq = (last.seq + 1) if last else 1

    # 2. Canonicalize and hash the payload
    payload_json = canonical_json(payload)
    payload_sha256 = sha256_hex(payload_json)
    ts = utc_now_canonical()

    # 3. Build the exact string that represents "this row", and hash it
    record = canonical_json({
        "seq": seq,
        "ts": ts,
        "actor_id": actor_id,
        "actor_role": actor_role,
        "action": action,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "request_id": request_id,
        "trace_id": trace_id,
        "payload_sha256": payload_sha256,
        "prev_hash": prev_hash,
    })
    this_hash = sha256_hex(record)

    # 4. Create and save the row
    event = AuditEvent(
        seq=seq,
        ts=ts,
        actor_id=actor_id,
        actor_role=actor_role,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        request_id=request_id,
        trace_id=trace_id,
        payload_json=payload_json,
        payload_sha256=payload_sha256,
        prev_hash=prev_hash,
        hash=this_hash,
    )
    session.add(event)
    session.commit()
    return event