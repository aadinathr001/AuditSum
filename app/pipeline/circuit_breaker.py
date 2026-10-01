import os
from dotenv import load_dotenv
load_dotenv()
from datetime import datetime, timezone
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.models import Run


def tokens_used_today(session: Session) -> int:
    today = datetime.now(timezone.utc).date()

    total = session.scalar(
        select(func.coalesce(func.sum(Run.total_prompt_tokens + Run.total_completion_tokens), 0))
        .where(func.date(Run.created_at) == today)
        .where(Run.provider != "mock")
    )
    return total or 0


def should_use_mock(session: Session) -> bool:
    cap = int(os.environ.get("DEMO_DAILY_TOKEN_CAP", "5"))
    return tokens_used_today(session) >= cap