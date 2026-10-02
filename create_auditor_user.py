from app.db import engine
from app.models import User
from sqlalchemy.orm import Session
from argon2 import PasswordHasher

hasher = PasswordHasher()

with Session(engine) as session:
    auditor_user = User(
        email="auditor@example.com",
        password_hash=hasher.hash("AuditorPassword789"),
        role="auditor",
        is_active=True,
    )
    session.add(auditor_user)
    session.commit()
    print(f"Created user with id={auditor_user.id}")