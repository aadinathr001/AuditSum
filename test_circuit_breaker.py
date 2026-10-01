from app.db import engine
from sqlalchemy.orm import Session

from app.pipeline.circuit_breaker import tokens_used_today, should_use_mock

with Session(engine) as session:
    print("tokens used today:", tokens_used_today(session))
    print("should use mock:", should_use_mock(session))