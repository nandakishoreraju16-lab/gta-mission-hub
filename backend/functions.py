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

class PlayerMission(Base):
    __tablename__ = "player_missions"
    id = Column(Integer, primary_key=True)
    player_id = Column(Integer, ForeignKey("users.id"))
    mission_id = Column(Integer, ForeignKey("missions.id"))
    status = Column(String, default="accepted")
    completion_details = Column(String, nullable=True)
    accepted_at = Column(DateTime, default=datetime.now)

class Reward(Base):
    __tablename__ = "rewards"
    id = Column(Integer, primary_key=True)
    mission_id = Column(Integer, ForeignKey("missions.id"))
    name = Column(String)
    description = Column(String)
    created_at = Column(DateTime, default=datetime.now)

class PlayerReward(Base):
    __tablename__ = "player_rewards"
    id = Column(Integer, primary_key=True)
    player_id = Column(Integer, ForeignKey("users.id"))
    reward_id = Column(Integer, ForeignKey("rewards.id"))
    assigned_at = Column(DateTime, default=datetime.now)


Base.metadata.create_all(engine)

def verify_login(email, password):
    session = Session(engine)
    user = session.query(User).filter_by(email=email).first()
    if user is None:
        session.close()
        return False
    try:
        ph.verify(user.hashed_password, password)
    except VerifyMismatchError:
        session.close()
        return False
    user_id = user.id
    role = user.role
    session.close()
    access_token = create_token(user_id=user_id, token_type="access")
    refresh_token = create_token(user_id=user_id, token_type="refresh")
    return {"access_token": access_token,"refresh_token": refresh_token,"role": role}

def create_token(user_id, token_type):
    time = ACCESS_TOKEN_EXPIRY
    if token_type == "refresh":
        time = REFRESH_TOKEN_EXPIRY
    payload = {"user_id": user_id,"token_type": token_type,"exp": datetime.now(timezone.utc) + timedelta(minutes=time)}
    token = jwt.encode(payload,key=SECRET_KEY,algorithm=ALGORITHM)
    return token

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


# Missions (E2 - E5)

def mission_dict(mission):
    return {
        "id": mission.id,
        "title": mission.title,
        "description": mission.description,
        "difficulty": mission.difficulty,
        "xp": DIFFICULTY_XP[mission.difficulty],
        "location": mission.location,
        "reward": mission.reward,
        "is_active": mission.is_active,
        "created_by": mission.created_by,
        "created_at": mission.created_at
    }


def add_mission(title, description, difficulty, location, reward, created_by):
    session = Session(engine)
    mission = Mission(title=title, description=description, difficulty=difficulty,
                      location=location, reward=reward, created_by=created_by)
    session.add(mission)
    session.commit()
    result = mission_dict(mission)
    session.close()
    return result


def get_active_missions():
    session = Session(engine)
    missions = session.query(Mission).filter_by(is_active=1).order_by(Mission.created_at.desc()).all()
    result = []
    for mission in missions:
        result.append(mission_dict(mission))
    session.close()
    return result


def get_mission(mission_id):
    session = Session(engine)
    mission = session.get(Mission, mission_id)
    if mission is None:
        session.close()
        return None
    result = mission_dict(mission)
    session.close()
    return result


def player_mission_dict(player_mission, mission):
    return {
        "id": player_mission.id,
        "player_id": player_mission.player_id,
        "mission_id": player_mission.mission_id,
        "mission_title": mission.title,
        "difficulty": mission.difficulty,
        "xp": DIFFICULTY_XP[mission.difficulty],
        "status": player_mission.status,
        "completion_details": player_mission.completion_details,
        "accepted_at": player_mission.accepted_at
    }


def has_open_mission(player_id, mission_id):
    session = Session(engine)
    rows = session.query(PlayerMission).filter_by(player_id=player_id, mission_id=mission_id).all()
    found = False
    for row in rows:
        if row.status == "accepted" or row.status == "submitted":
            found = True
    session.close()
    return found


def accept_mission(player_id, mission_id):
    session = Session(engine)
    player_mission = PlayerMission(player_id=player_id, mission_id=mission_id)
    session.add(player_mission)
    session.commit()
    mission = session.get(Mission, mission_id)
    result = player_mission_dict(player_mission, mission)
    session.close()
    return result

def get_player_missions(player_id):
    session = Session(engine)
    rows = session.query(PlayerMission).filter_by(player_id=player_id).order_by(PlayerMission.accepted_at.desc()).all()
    result = []
    for row in rows:
        mission = session.get(Mission, row.mission_id)
        result.append(player_mission_dict(row, mission))
    session.close()
    return result

def get_player_mission(player_mission_id):
    session = Session(engine)
    row = session.get(PlayerMission, player_mission_id)
    if row is None:
        session.close()
        return None
    mission = session.get(Mission, row.mission_id)
    result = player_mission_dict(row, mission)
    session.close()
    return result

def submit_completion(player_mission_id, completion_details):
    session = Session(engine)
    row = session.get(PlayerMission, player_mission_id)
    row.status = "submitted"
    row.completion_details = completion_details
    session.commit()
    mission = session.get(Mission, row.mission_id)
    result = player_mission_dict(row, mission)
    session.close()
    return result

# E11 - Create a reward for a mission

def reward_dict(reward):
    return {
        "id": reward.id,
        "mission_id": reward.mission_id,
        "name": reward.name,
        "description": reward.description,
        "created_at": reward.created_at
    }


def add_reward(mission_id, name, description):
    session = Session(engine)
    reward = Reward(mission_id=mission_id, name=name, description=description)
    session.add(reward)
    session.commit()
    result = reward_dict(reward)
    session.close()
    return result


# E12 - Get available rewards

def get_rewards():
    session = Session(engine)
    rewards = session.query(Reward).all()
    result = []
    for reward in rewards:
        result.append(reward_dict(reward))
    session.close()
    return result


# E13 - Assign a reward to a player (only after mission is approved)

def get_reward(reward_id):
    session = Session(engine)
    reward = session.get(Reward, reward_id)
    if reward is None:
        session.close()
        return None
    result = reward_dict(reward)
    session.close()
    return result


def has_approved_mission(player_id, mission_id):
    session = Session(engine)
    row = session.query(PlayerMission).filter_by(player_id=player_id, mission_id=mission_id, status="approved").first()
    session.close()
    return row is not None


def reward_already_assigned(player_id, reward_id):
    session = Session(engine)
    row = session.query(PlayerReward).filter_by(player_id=player_id, reward_id=reward_id).first()
    session.close()
    return row is not None


def assign_reward(player_id, reward_id):
    session = Session(engine)
    player_reward = PlayerReward(player_id=player_id, reward_id=reward_id)
    session.add(player_reward)
    session.commit()
    result = {"id": player_reward.id, "player_id": player_reward.player_id,
              "reward_id": player_reward.reward_id, "assigned_at": player_reward.assigned_at}
    session.close()
    return result


# E14 - Leaderboard (players ranked by xp)

def get_total_xp(session, player_id):
    rows = session.query(PlayerMission).filter_by(player_id=player_id, status="approved").all()
    total_xp = 0
    for row in rows:
        mission = session.get(Mission, row.mission_id)
        total_xp = total_xp + DIFFICULTY_XP[mission.difficulty]
    return total_xp


def get_leaderboard():
    session = Session(engine)
    players = session.query(User).filter_by(role="player").all()
    board = []
    for player in players:
        board.append({"player_id": player.id, "username": player.username, "xp": get_total_xp(session, player.id)})
    session.close()
    board.sort(key=lambda item: item["xp"], reverse=True)
    rank = 1
    for item in board:
        item["rank"] = rank
        rank = rank + 1
    return board


# E15 - Player profile and stats

def get_player_profile(player_id):
    session = Session(engine)
    player = session.get(User, player_id)
    if player is None or player.role != "player":
        session.close()
        return None
    completed = session.query(PlayerMission).filter_by(player_id=player_id, status="approved").count()
    rewards = session.query(PlayerReward).filter_by(player_id=player_id).count()
    result = {
        "player_id": player.id,
        "username": player.username,
        "completed_missions": completed,
        "total_rewards": rewards,
        "xp": get_total_xp(session, player_id)
    }
    session.close()
    return result
