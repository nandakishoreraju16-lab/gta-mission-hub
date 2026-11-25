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
        raise HTTPException(status_code=401,detail="Invalid Credentials")
    return token
