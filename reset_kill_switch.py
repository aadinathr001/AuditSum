from app.db import engine
from sqlalchemy.orm import Session

from app.models import Control

with Session(engine) as session:
    session.merge(Control(key="model:gpt-oss-120b:enabled", value="true", updated_by=1))
    session.commit()
    print("Re-enabled")