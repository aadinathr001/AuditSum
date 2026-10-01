from app.db import engine
from sqlalchemy.orm import Session

from app.policy.service import run_policy_checks

with Session(engine) as session:
    decisions = run_policy_checks(
        session,
        text="Hello world",
        filename="notes.pdf",  # deliberately bad file type, to see a 'deny' get recorded
        document_id=None,
        actor_id=1,
        actor_role="admin",
    )
    for d in decisions:
        print(d)