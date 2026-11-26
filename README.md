# GTA – Open World Mission Hub

Team 10 · Main Project

Backend for an open-world mission game. Players accept missions, submit completion details and earn rewards and experience points (XP). Mission managers create missions and approve completions. The admin manages mission managers.

FastAPI + SQLite, JWT access and refresh tokens, role-based access, Docker, GitHub Actions CI/CD, AWS EC2. Backend only.

**Live API (EC2):** http://54.167.63.95:8001/docs

## Work split

| Member | Endpoints |
|---|---|
| Nanda Kishore (team lead) | A1, E1 – E5 |
| Jyoshna | A2, E6 – E10 |
| Monica | A3, E11 – E15 |

Docker, GitHub Actions and EC2 deployment: team work.

## Roles

| Role | Can do |
|---|---|
| Admin | Create mission manager accounts |
| Mission Manager | Create and update missions, approve or reject completions, create and assign rewards |
| Player | Accept missions, submit completion, view own missions and completed history |

New registrations get the player role. Only the admin can create mission managers.

## API contract

Protected endpoints read the access token from the `token` header. `/auth/refresh` reads the refresh token from the `refresh-token` header.

### Authentication

| # | Functionality | Method | Path | Request body | Success |
|---|---|---|---|---|---|
| A1 | Register a new account | POST | `/auth/register` | `{username, email, password}` | 200 |
| A2 | Login, get access and refresh tokens | POST | `/auth/login` | `{email, password}` | 200 |
| A3 | New access token | POST | `/auth/refresh` | header `refresh-token` | 200 |

### Project APIs

| # | Functionality | Access | Method | Path | Request body | Success |
|---|---|---|---|---|---|---|
| E1 | Create a mission manager account | Admin | POST | `/admin/managers` | `{username, email, password}` | 201 |
| E2 | Create a new mission | Manager | POST | `/missions` | `{title, description, difficulty, location, reward}` | 201 |
| E3 | Get all available missions | All | GET | `/missions` | – | 200 |
| E4 | Get details of a mission | All | GET | `/missions/{mission_id}` | – | 200 |
| E5 | Update mission details or availability | Manager | PATCH | `/missions/{mission_id}` | any of `{title, description, difficulty, location, reward, is_active}` | 200 |
| E6 | Accept a mission | Player | POST | `/missions/{mission_id}/accept` | – | 201 |
| E7 | Get my accepted missions | Player | GET | `/my-missions` | – | 200 |
| E8 | Submit mission completion details | Player | POST | `/my-missions/{player_mission_id}/submit` | `{completion_details}` | 200 |
| E9 | Approve or reject a completion | Manager | PATCH | `/completions/{player_mission_id}` | `{decision}` (`approve` or `reject`) | 200 |
| E10 | Get my completed mission history | Player | GET | `/my-missions/completed` | – | 200 |
| E11 | Create a reward for a mission | Manager | POST | `/rewards` | `{mission_id, name, description}` | 201 |
| E12 | Get available rewards | All | GET | `/rewards` | – | 200 |
| E13 | Assign a reward to a player | Manager | POST | `/rewards/{reward_id}/assign` | `{player_id}` | 201 |
| E14 | Get player leaderboard | All | GET | `/leaderboard` | – | 200 |
| E15 | Get player profile and statistics | All | GET | `/players/{player_id}/profile` | – | 200 |

### Error rules

| Rule | Status |
|---|---|
| No token, invalid or expired token | 401 |
| Wrong email or password | 401 |
| Logged in but role not allowed | 403 |
| Mission, completion, reward or player not found | 404 |
| Email already registered | 409 |
| Same active mission accepted twice | 409 |
| Same reward assigned twice | 409 |
| Empty fields, invalid email, invalid difficulty or decision | 422 |
| Not allowed in the current state (inactive mission, approve before submit, reward before approval) | 400 |

## Business rules

- A mission has a title, description, difficulty, location and reward.
- Difficulty is `easy`, `medium`, `hard` or `special`.
- Managers can publish and deactivate missions.
- A player cannot accept the same active mission more than once.
- A player must submit completion details before the mission can be approved.
- Managers approve or reject submitted completions.
- Rewards can be assigned only after an approved completion.
- The leaderboard ranks players by XP.

| Difficulty | XP |
|---|---|
| easy | 50 |
| medium | 100 |
| hard | 200 |
| special | 500 |

XP is calculated by the backend from approved completions.

## Database

One SQLite file, `gta.db`, stored in `/app/data` (mounted from `/opt/gta/data` on EC2).

| Table | Columns |
|---|---|
| `users` | `id`, `username`, `email` (unique), `hashed_password`, `role`, `created_at` |
| `missions` | `id`, `title`, `description`, `difficulty`, `location`, `reward`, `is_active`, `created_by` (→ users), `created_at` |
| `player_missions` | `id`, `player_id` (→ users), `mission_id` (→ missions), `status`, `completion_details`, `accepted_at` |
| `rewards` | `id`, `mission_id` (→ missions), `name`, `description`, `created_at` |
| `player_rewards` | `id`, `player_id` (→ users), `reward_id` (→ rewards), `assigned_at` |

## File structure

```
backend/
  main.py           endpoints and request validation
  functions.py      tables, password hashing, JWT and database functions
  requirements.txt
  dockerfile
.github/workflows/deploy.yml   CI/CD to Docker Hub and EC2
README.md
```

## How to run

```
git clone https://github.com/nandakishoreraju16-lab/gta-mission-hub.git
cd gta-mission-hub/backend
pip install -r requirements.txt
uvicorn main:app --port 8001
```

Open http://127.0.0.1:8001/docs

With Docker:

```
cd backend
docker build -t gta-api -f dockerfile .
docker run -d --name gta-api -p 8001:8001 -v gta-data:/app/data gta-api
```

## Deployment

Every push to `main` runs `.github/workflows/deploy.yml`: build the Docker image, push it to Docker Hub, connect to the EC2 instance over SSH and replace the running container. `gta.db` is kept in `/opt/gta/data` on EC2, so data stays after every redeploy.

GitHub Actions secrets: `DOCKERHUB_USERNAME`, `DOCKERHUB_TOKEN`, `EC2_HOST`, `EC2_USER`, `EC2_SSH_KEY`, `JWT_SECRET_KEY`.

## Daily progress

### Day 1 – Tue 24 Nov 2026
- Chose the project and split the endpoints.
- Created the repository and added the work split.
- Added `main.py` with the register endpoint (A1).

### Day 2 – Wed 25 Nov 2026
- Nanda: `users` and `missions` tables, E1 – E5.
- Jyoshna: database setup, `player_missions` table, login (A2), E6 – E10.
- Monica: refresh token (A3), `rewards` and `player_rewards` tables, E11 – E15.
- Added the Dockerfile and GitHub Actions workflow.
- Launched the EC2 instance in US East (N. Virginia), installed Docker and set the GitHub secrets.
- First deployment to EC2.
- Started adding endpoints one per commit and testing each on EC2: E1 – E3 (Nanda), A3 and E11 – E15 (Monica), E7 – E10 (Jyoshna).

### Day 3 – Thu 26 Nov 2026
- Nanda: added E4 and E5, each merged and tested on EC2.
- Tested all 18 endpoints through Swagger on EC2, including error cases.
- Updated the README.
