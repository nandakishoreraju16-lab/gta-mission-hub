from fastapi import FastAPI, HTTPException, Header
from pydantic import BaseModel, Field
import functions

app = FastAPI()


class RegisterIn(BaseModel):
    username: str = Field(min_length=1)
    email: str = Field(min_length=1)
    password: str = Field(min_length=1)

class LoginIn(BaseModel):
    email: str = Field(min_length=1)
    password: str = Field(min_length=1)

class MissionIn(BaseModel):
    title: str = Field(min_length=1)
    description: str = Field(min_length=1)
    difficulty: str
    location: str = Field(min_length=1)
    reward: str = Field(min_length=1)


class CompletionIn(BaseModel):
    completion_details: str = Field(min_length=1)


class DecisionIn(BaseModel):
    decision: str

class RewardIn(BaseModel):
    mission_id: int
    name: str = Field(min_length=1)
    description: str = Field(min_length=1)

class AssignIn(BaseModel):
    player_id: int


# A1 - Register
@app.post("/auth/register")
def register_user(user: RegisterIn):
    if user.username.strip() == "" or user.password.strip() == "":
        raise HTTPException(status_code=422, detail="Username and password cannot be empty")
    if "@" not in user.email or "." not in user.email.split("@")[-1]:
        raise HTTPException(status_code=422, detail="Invalid email format")
    result = functions.register_user(username=user.username, email=user.email, password=user.password)
    if not result:
        raise HTTPException(status_code=409, detail="Email already registered")
    return {"message": "User registered successfully"}

# A2 - Login

@app.post("/auth/login")
def login(data: LoginIn):
    token = functions.verify_login(email=data.email,password=data.password)
    if not token:
        raise HTTPException( status_code=401,detail="Invalid Credentials")
    return token


# E1 - Create a mission manager account (Admin)
@app.post("/admin/managers", status_code=201)
def create_manager(user: RegisterIn, token = Header(None)):
    user_id = functions.verify_token(token=token, token_type="access")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    if functions.get_user_role(user_id) != "admin":
        raise HTTPException(status_code=403, detail="Only admin can do this")
    if user.username.strip() == "" or user.password.strip() == "":
        raise HTTPException(status_code=422, detail="Username and password cannot be empty")
    if "@" not in user.email or "." not in user.email.split("@")[-1]:
        raise HTTPException(status_code=422, detail="Invalid email format")
    result = functions.register_user(username=user.username, email=user.email, password=user.password, role="manager")
    if not result:
        raise HTTPException(status_code=409, detail="Email already registered")
    return result


# E2 - Create a new mission (Mission Manager)
@app.post("/missions", status_code=201)
def create_mission(data: MissionIn, token = Header(None)):
    user_id = functions.verify_token(token=token, token_type="access")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    if functions.get_user_role(user_id) != "manager":
        raise HTTPException(status_code=403, detail="Only mission managers can do this")
    if data.title.strip() == "" or data.description.strip() == "" or data.location.strip() == "" or data.reward.strip() == "":
        raise HTTPException(status_code=422, detail="Fields cannot be empty")
    if data.difficulty not in functions.DIFFICULTY_XP:
        raise HTTPException(status_code=422, detail="Difficulty must be easy, medium, hard or special")
    return functions.add_mission(title=data.title, description=data.description, difficulty=data.difficulty,
                                 location=data.location, reward=data.reward, created_by=user_id)


# E6 - Accept a mission (Player)
@app.post("/missions/{mission_id}/accept", status_code=201)
def accept_mission(mission_id: int, token = Header(None)):
    user_id = functions.verify_token(token=token, token_type="access")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    if functions.get_user_role(user_id) != "player":
        raise HTTPException(status_code=403, detail="Only players can do this")
    mission = functions.get_mission(mission_id)
    if mission is None:
        raise HTTPException(status_code=404, detail="Mission not found")
    if mission["is_active"] == 0:
        raise HTTPException(status_code=400, detail="Mission is not active")
    if functions.has_open_mission(user_id, mission_id):
        raise HTTPException(status_code=409, detail="Mission already accepted")
    return functions.accept_mission(player_id=user_id, mission_id=mission_id)


# E7 - Get missions accepted by the logged-in player (Player)
@app.get("/my-missions")
def get_my_missions(token = Header(None)):
    user_id = functions.verify_token(token=token, token_type="access")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    if functions.get_user_role(user_id) != "player":
        raise HTTPException(status_code=403, detail="Only players can do this")
    return functions.get_player_missions(user_id)


# E8 - Submit mission completion details (Player)
@app.post("/my-missions/{player_mission_id}/submit")
def submit_completion(player_mission_id: int, data: CompletionIn, token = Header(None)):
    user_id = functions.verify_token(token=token, token_type="access")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    if functions.get_user_role(user_id) != "player":
        raise HTTPException(status_code=403, detail="Only players can do this")
    if data.completion_details.strip() == "":
        raise HTTPException(status_code=422, detail="Completion details cannot be empty")
    player_mission = functions.get_player_mission(player_mission_id)
    if player_mission is None or player_mission["player_id"] != user_id:
        raise HTTPException(status_code=404, detail="Accepted mission not found")
    if player_mission["status"] != "accepted":
        raise HTTPException(status_code=400, detail="Only accepted missions can be submitted")
    return functions.submit_completion(player_mission_id, data.completion_details)


# E9 - Approve or reject a mission completion (Mission Manager)
@app.patch("/completions/{player_mission_id}")
def review_completion(player_mission_id: int, data: DecisionIn, token = Header(None)):
    user_id = functions.verify_token(token=token, token_type="access")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    if functions.get_user_role(user_id) != "manager":
        raise HTTPException(status_code=403, detail="Only mission managers can do this")
    if data.decision not in ["approve", "reject"]:
        raise HTTPException(status_code=422, detail="Decision must be approve or reject")
    player_mission = functions.get_player_mission(player_mission_id)
    if player_mission is None:
        raise HTTPException(status_code=404, detail="Completion not found")
    if player_mission["status"] != "submitted":
        raise HTTPException(status_code=400, detail="Only submitted missions can be reviewed")
    return functions.review_completion(player_mission_id, data.decision)


# E10 - Get the player's completed mission history (Player)
@app.get("/my-missions/completed")
def get_completed_missions(token = Header(None)):
    user_id = functions.verify_token(token=token, token_type="access")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    if functions.get_user_role(user_id) != "player":
        raise HTTPException(status_code=403, detail="Only players can do this")
    return functions.get_completed_missions(user_id)


# A3 - Generate a new access token
@app.post("/auth/refresh")
def refresh_token(refresh_token = Header(None)):
    user_id = functions.verify_token(token=refresh_token, token_type="refresh")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")
    access_token = functions.create_token(user_id=user_id, token_type="access")
    return {"access_token": access_token, "token_type": "access"}


# E11 - Create a reward for a mission (Mission Manager)
@app.post("/rewards", status_code=201)
def create_reward(data: RewardIn, token = Header(None)):
    user_id = functions.verify_token(token=token, token_type="access")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    if functions.get_user_role(user_id) != "manager":
        raise HTTPException(status_code=403, detail="Only mission managers can do this")
    if data.name.strip() == "" or data.description.strip() == "":
        raise HTTPException(status_code=422, detail="Fields cannot be empty")
    if functions.get_mission(data.mission_id) is None:
        raise HTTPException(status_code=404, detail="Mission not found")
    return functions.add_reward(mission_id=data.mission_id, name=data.name, description=data.description)


# E12 - Get available rewards (All)
@app.get("/rewards")
def get_rewards(token = Header(None)):
    user_id = functions.verify_token(token=token, token_type="access")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return functions.get_rewards()


# E13 - Assign a reward to a player (Mission Manager)
@app.post("/rewards/{reward_id}/assign", status_code=201)
def assign_reward(reward_id: int, data: AssignIn, token = Header(None)):
    user_id = functions.verify_token(token=token, token_type="access")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    if functions.get_user_role(user_id) != "manager":
        raise HTTPException(status_code=403, detail="Only mission managers can do this")
    reward = functions.get_reward(reward_id)
    if reward is None:
        raise HTTPException(status_code=404, detail="Reward not found")
    if functions.get_user_role(data.player_id) != "player":
        raise HTTPException(status_code=404, detail="Player not found")
    if not functions.has_approved_mission(data.player_id, reward["mission_id"]):
        raise HTTPException(status_code=400, detail="Player has no approved completion for this mission")
    if functions.reward_already_assigned(data.player_id, reward_id):
        raise HTTPException(status_code=409, detail="Reward already assigned to this player")
    return functions.assign_reward(player_id=data.player_id, reward_id=reward_id)


# E14 - Get player rankings and leaderboard (All)
@app.get("/leaderboard")
def get_leaderboard(token = Header(None)):
    user_id = functions.verify_token(token=token, token_type="access")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return functions.get_leaderboard()
