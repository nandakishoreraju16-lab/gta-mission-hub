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


def update_mission(mission_id, title, description, difficulty, location, reward, is_active):
    session = Session(engine)
    mission = session.get(Mission, mission_id)
    if mission is None:
        session.close()
        return None
    if title is not None:
        mission.title = title
    if description is not None:
        mission.description = description
    if difficulty is not None:
        mission.difficulty = difficulty
    if location is not None:
        mission.location = location
    if reward is not None:
        mission.reward = reward
    if is_active is not None:
        mission.is_active = is_active
    session.commit()
    result = mission_dict(mission)
    session.close()
    return result
