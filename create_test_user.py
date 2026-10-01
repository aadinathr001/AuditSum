# import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from argon2 import PasswordHasher

from app.db import engine
from app.models import User

# load_dotenv()

# engine = create_engine(os.environ["DATABASE_URL"])
hasher = PasswordHasher()

with Session(engine) as session:
    test_user = User(
        email="test@example.com",
        password_hash=hasher.hash("MyTestPassword123"),
        role="admin",
        is_active=True,
    )
    session.add(test_user)
    session.commit()
    print(f"Created user with id={test_user.id}")