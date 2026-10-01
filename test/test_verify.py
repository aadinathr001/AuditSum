from app.db import engine
from sqlalchemy.orm import Session

from app.audit.verify import verify_chain

with Session(engine) as session:
    result = verify_chain(session)
    print(result)