from dataclasses import dataclass
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AuditEvent
from app.audit.canonical import canonical_json
from app.audit.hashing import sha256_hex

GENESIS_HASH = "0" * 64


@dataclass
class VerifyResult:
    ok: bool
    checked: int
    head_seq: int | None = None
    head_hash: str | None = None
    first_broken_seq: int | None = None
    reason: str | None = None


def verify_chain(session: Session) -> VerifyResult:
    prev_hash = GENESIS_HASH
    expected_seq = 1
    checked = 0

    rows = session.scalars(select(AuditEvent).order_by(AuditEvent.seq))

    for row in rows:
        # Check 1: seq must increase by exactly 1 each time, no gaps
        if row.seq != expected_seq:
            return VerifyResult(ok=False, checked=checked, first_broken_seq=row.seq, reason="sequence gap")

        # Check 2: this row's prev_hash must match the previous row's actual hash
        if row.prev_hash != prev_hash:
            return VerifyResult(ok=False, checked=checked, first_broken_seq=row.seq, reason="prev_hash mismatch")

        # Check 3: the payload hasn't been silently edited
        if sha256_hex(row.payload_json) != row.payload_sha256:
            return VerifyResult(ok=False, checked=checked, first_broken_seq=row.seq, reason="payload altered")

        # Check 4: recompute this row's own hash and confirm it matches what's stored
        record = canonical_json({
            "seq": row.seq,
            "ts": row.ts,
            "actor_id": row.actor_id,
            "actor_role": row.actor_role,
            "action": row.action,
            "entity_type": row.entity_type,
            "entity_id": row.entity_id,
            "request_id": row.request_id,
            "trace_id": row.trace_id,
            "payload_sha256": row.payload_sha256,
            "prev_hash": row.prev_hash,
        })
        recomputed_hash = sha256_hex(record)

        if recomputed_hash != row.hash:
            return VerifyResult(ok=False, checked=checked, first_broken_seq=row.seq, reason="hash mismatch")

        prev_hash = row.hash
        expected_seq += 1
        checked += 1

    return VerifyResult(ok=True, checked=checked, head_seq=checked, head_hash=prev_hash)