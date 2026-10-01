from sqlalchemy.orm import Session

from app.models import PolicyDecision as PolicyDecisionRow
from app.policy.engine import evaluate, PolicyDecision
from app.audit.service import append_event


def run_policy_checks(
    session: Session,
    *,
    text: str,
    filename: str,
    document_id: int | None,
    actor_id: int | None,
    actor_role: str | None,
) -> list[PolicyDecision]:
    decisions = evaluate(session, text, filename, model="gpt-oss-120b")

    for d in decisions:
        session.add(PolicyDecisionRow(
            document_id=document_id,
            run_id=None,
            check_name=d.check_name,
            outcome=d.outcome,
            reason=d.reason,
            details_json=d.details,
        ))

        append_event(
            session,
            actor_id=actor_id,
            actor_role=actor_role,
            action="policy.decision",
            entity_type="document",
            entity_id=document_id,
            payload={"check_name": d.check_name, "outcome": d.outcome, "reason": d.reason},
        )

    session.commit()
    return decisions