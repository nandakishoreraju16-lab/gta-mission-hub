import os
from sqlalchemy import Integer, String, Column, create_engine, DateTime, ForeignKey
from sqlalchemy.orm import Session, declarative_base
from datetime import datetime, timedelta, timezone

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

ph = PasswordHasher()

# /app/data is mounted from EC2, so gta.db survives redeploys
os.makedirs("/app/data", exist_ok=True)
DB_URL = "sqlite:////app/data/gta.db"
engine = create_engine(DB_URL)
Base = declarative_base()

ACCESS_TOKEN_EXPIRY = 30 #mins
REFRESH_TOKEN_EXPIRY = 7 * 24 * 60 #mins
SECRET_KEY = os.getenv("SECRET_KEY", "SECRET123")
ALGORITHM = "HS256"

# Experience points for each mission difficulty
DIFFICULTY_XP = {"easy": 50, "medium": 100, "hard": 200, "special": 500}


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    username = Column(String)
    email = Column(String, unique=True)
    hashed_password = Column(String)
    role = Column(String, default="player")
    created_at = Column(DateTime, default=datetime.now)


class Mission(Base):
    __tablename__ = "missions"
    id = Column(Integer, primary_key=True)
    title = Column(String)
    description = Column(String)
    difficulty = Column(String)
    location = Column(String)
    reward = Column(String)
    is_active = Column(Integer, default=1)
    created_by = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=datetime.now)

Base.metadata.create_all(engine)


def verify_token(token, token_type):
    try:
        payload = jwt.decode(jwt=token, key=SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.PyJWTError:
        return False
    if payload["token_type"] == token_type:
        return payload["user_id"]
    return False


def get_user_role(user_id):
    session = Session(engine)
    user = session.get(User, user_id)
    if user is None:
        session.close()
        return None
    role = user.role
    session.close()
    return role


# A1 - Register (new users are players) and E1 - Create manager (role="manager")

def register_user(username, email, password, role="player"):
    session = Session(engine)
    user_existing = session.query(User).filter_by(email=email).first()
    if user_existing is not None:
        session.close()
        return False

    user = User(username=username, email=email, hashed_password=ph.hash(password), role=role)
    session.add(user)
    session.commit()
    result = {"id": user.id, "username": user.username, "email": user.email, "role": user.role, "created_at": user.created_at}
    session.close()
    return result


# The first admin is created when the app starts; email and password come from GitHub secrets
def create_admin():
    email = os.getenv("ADMIN_EMAIL", "admin@gta.com")
    password = os.getenv("ADMIN_PASSWORD", "admin123")
    register_user(username="admin", email=email, password=password, role="admin")

create_admin()
