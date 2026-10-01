from app.db import engine
from app.models import User

# import os
# from dotenv import load_dotenv
# from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from argon2 import PasswordHasher

from app.models import User

# load_dotenv()

# engine = create_engine(os.environ["DATABASE_URL"])
hasher = PasswordHasher()

with Session(engine) as session:
    regular_user = User(
        email="user@example.com",
        password_hash=hasher.hash("AnotherPassword456"),
        role="user",
        is_active=True,
    )
    session.add(regular_user)
    session.commit()
    print(f"Created user with id={regular_user.id}")