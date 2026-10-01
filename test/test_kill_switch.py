from app.db import engine
from sqlalchemy.orm import Session

from app.models import Control
from app.policy.service import run_policy_checks

with Session(engine) as session:
    # Disable the model
    session.merge(Control(key="model:gpt-oss-120b:enabled", value="false", updated_by=1))
    session.commit()

    decisions = run_policy_checks(
        session,
        text="Hello world",
        filename="notes.txt",
        document_id=None,
        actor_id=1,
        actor_role="admin",
    )
    for d in decisions:
        print(d)