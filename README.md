# Khyaal

**Everyday Support, Made Personal**

Khyaal is a full-stack caregiving and everyday support platform designed to help guardians and dependents stay connected through personalized care routines, memory support, wellbeing check-ins, and engaging activities.

🌐 **Live Demo:** https://khyaal-pi.vercel.app/  
💻 **Source Code:** https://github.com/Harshalraheja1180/Khyaal

## Key Features

- **Guardian & Dependent Accounts:** Relationship-based access and sharing permissions.
- **Care Management:** Medicine plans, daily routines, reminders, and trusted contacts.
- **Memory Studio:** Personalized memory profiles and familiar content.
- **Quiz Studio:** Custom quizzes and interactive learning.
- **Games:** Five casual memory and pattern-based games.
- **Daily Wellbeing:** Private, non-clinical wellbeing check-ins.
- **Guardian Reports:** Shared activity and wellbeing summaries.
- **Location Sharing:** Optional, user-controlled location sharing.

## Tech Stack

| Layer | Technologies |
|---|---|
| Frontend | Next.js, React, TypeScript |
| Backend | Python, FastAPI |
| Database | PostgreSQL |
| ORM | SQLAlchemy |
| Migrations | Alembic |
| Frontend Hosting | Vercel |
| Backend Hosting | Render |
| Database Hosting | Neon PostgreSQL |

## Architecture

Browser → Next.js Frontend → FastAPI REST API → SQLAlchemy → PostgreSQL

The frontend communicates with the backend through authenticated API requests. Database access and permission validation are handled server-side.

## What is running

```text
Next.js browser app  ── JSON / private media over HTTP ──▶  FastAPI API  ── SQLAlchemy ──▶  PostgreSQL
                                                               │
                                                               └── authenticated files ──▶ storage/private
```

The browser never connects to PostgreSQL. The frontend sends an authenticated request to FastAPI. FastAPI validates it, checks the account role and the dependent's sharing permissions, and then reads or writes PostgreSQL. Guardian photos travel to FastAPI, are validated and stored outside the frontend's public folder, and have a database reference. Every photo read goes through an authenticated API endpoint.

## Project structure

```text
MemoryCare/
├── frontend/             Next.js, React, TypeScript, responsive app
├── backend/              FastAPI, SQLAlchemy, authentication, API, tests
│   └── alembic/           PostgreSQL schema migrations
├── database/              Database workflow notes
├── storage/private/       Private local files; never served as public assets
├── docs/                  Architecture, schema, API references
├── .env.example
└── README.md
```

## Windows PowerShell setup

Commands below use the current project location. If you moved the folder, change `$projectRoot` to its new full path. PostgreSQL examples use the local `postgres` administrator. Use a unique local password and URL-encode special characters in `DATABASE_URL`.

### 1. Install prerequisites

Install Python 3.12, Node.js LTS, and PostgreSQL 16 or newer if they are not installed:

```powershell
winget install --id Python.Python.3.12 --exact
winget install --id OpenJS.NodeJS.LTS --exact
winget install --id PostgreSQL.PostgreSQL.16 --exact
```

Restart PowerShell and check:

```powershell
py -3.12 --version
node --version
npm --version
psql --version
```

If PostgreSQL's command line tools are not on `PATH`, add them for this PowerShell session. Change `18` to the installed PostgreSQL version:

```powershell
$env:Path += ";C:\Program Files\PostgreSQL\18\bin"
```

### 2. Create the PostgreSQL role and databases

Open the PostgreSQL prompt:

```powershell
psql -U postgres -h localhost -d postgres
```

At the `postgres=#` prompt, replace the sample password with a strong local password, run these SQL statements, and then exit:

```sql
CREATE ROLE memorycare_app WITH LOGIN PASSWORD 'CHOOSE_A_LOCAL_PASSWORD';
CREATE DATABASE memorycare OWNER memorycare_app;
CREATE DATABASE memorycare_test OWNER memorycare_app;
\q
```

If you already created the role, change its password instead of creating it again:

```sql
ALTER ROLE memorycare_app WITH PASSWORD 'CHOOSE_A_LOCAL_PASSWORD';
```

`memorycare_test` is separate because the test suite drops and recreates its tables. Never point it at data you want to keep.

### 3. Configure the backend `.env`

```powershell
$projectRoot = "C:\Users\Lenovo\Documents\Codex\2026-09-25\start-with-phase-1-only-do\outputs\MemoryCare"
Set-Location $projectRoot
Copy-Item .env.example .env
py -3.12 -c "import secrets; print(secrets.token_urlsafe(48))"
notepad .env
```

Paste the generated random value into `SECRET_KEY`. Set `DATABASE_URL` using your PostgreSQL password:

```text
postgresql+psycopg://memorycare_app:YOUR_URL_ENCODED_PASSWORD@localhost:5432/memorycare
```

Keep `.env` private. Its `DEMO_PASSWORD` setting is only for fictional local accounts; change it before running the seed command. Do not commit `.env` or use the sample values for a shared deployment.

### 4. Create the backend virtual environment and install dependencies

```powershell
$projectRoot = "C:\Users\Lenovo\Documents\Codex\2026-09-25\start-with-phase-1-only-do\outputs\MemoryCare"
Set-Location "$projectRoot\backend"
py -3.12 -m venv .venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### 5. Create the database schema and seed fictional demo accounts

The migration creates or updates the PostgreSQL tables; you do not need to edit tables by hand.

```powershell
Set-Location "$projectRoot\backend"
.\.venv\Scripts\Activate.ps1
alembic upgrade head
python -m app.seed_demo
```

To generate a migration after changing SQLAlchemy models, then apply it:

```powershell
alembic revision --autogenerate -m "describe the schema change"
alembic upgrade head
```

To roll back one migration:

```powershell
alembic downgrade -1
```

Review generated migration files before applying them, especially when upgrading a database containing care data.

### 6. Start the FastAPI backend

Keep this PowerShell window open:

```powershell
Set-Location "$projectRoot\backend"
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload
```

Check the API and database connection at [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health), [http://127.0.0.1:8000/health/ready](http://127.0.0.1:8000/health/ready), or explore the endpoints at [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs). The ready check reports whether PostgreSQL is reachable.

### 7. Configure and start the Next.js frontend

Open a second PowerShell window:

```powershell
$projectRoot = "C:\Users\Lenovo\Documents\Codex\2026-09-25\start-with-phase-1-only-do\outputs\MemoryCare"
Set-Location "$projectRoot\frontend"
Copy-Item .env.local.example .env.local
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000). The frontend API address is `NEXT_PUBLIC_API_URL` in `frontend/.env.local`; the example points to `http://127.0.0.1:8000/api/v1`.

### 8. Run backend tests

Use a third PowerShell window. These tests recreate tables only in `memorycare_test`:

```powershell
$projectRoot = "C:\Users\Lenovo\Documents\Codex\2026-09-25\start-with-phase-1-only-do\outputs\MemoryCare"
Set-Location "$projectRoot\backend"
.\.venv\Scripts\Activate.ps1
$env:DATABASE_URL = "postgresql+psycopg://memorycare_app:YOUR_URL_ENCODED_PASSWORD@localhost:5432/memorycare_test"
$env:TEST_DATABASE_URL = $env:DATABASE_URL
python -m pytest -v
Remove-Item Env:DATABASE_URL
Remove-Item Env:TEST_DATABASE_URL
```

For a production frontend build and lint check:

```powershell
Set-Location "$projectRoot\frontend"
npm run lint
npm run build
```

## Demo accounts and first walkthrough

`python -m app.seed_demo` creates fictional accounts. All demo accounts use the value of `DEMO_PASSWORD` in the project `.env` at seed time.

| Role | Demo email | Experience |
|---|---|---|
| Admin | `admin@memorycare.example.com` | Aggregate platform counts only |
| Guardian | `guardian@memorycare.example.com` | Linked dependents, care planning and reports |
| Dependent | `meera.demo@memorycare.example.com` | Older adult mode |
| Dependent | `aarav.demo@memorycare.example.com` | Memory support mode |

The seed links both fictional dependent accounts to the demo guardian and gives the guardian the demo sharing scopes. Real accounts use invitations: the guardian enters the dependent's registered email, then the dependent accepts or declines and selects sharing categories. Location is not shared by default. It becomes available to linked guardians only after the dependent turns it on.

1. Sign in as `guardian@memorycare.example.com` to add a medicine, routine, appointment and trusted contact. Select Meera or Aarav from the care-circle selector.
2. Open Memory studio to add familiar people, places or objects. A photo upload is optional; if added, the file remains private. Use fictional or family-approved demo images only.
3. In Quiz studio, create a quiz, add a question and two or more answers, choose its correct answer, then activate it. Dependent accounts only see active quizzes.
4. In Games, choose which of the five built-in casual brain games are available. Guardians can pause or resume a game; dependents can play Sequence Memory, Tile Memory, Pattern Memory, Matching Pairs or Odd One Out. Results are stored as game sessions.
5. Sign out, then sign in as Meera or Aarav to see their distinct dependent experience. Try a Daily Reminder, the visual wellbeing check-in, a quiz, a casual game or a help request.
6. Return to the guardian account and open Reports. If the dependent granted wellbeing access, the report shows today's shared check-in, response summary, category indicators and recent trends alongside care activity.

## Daily wellbeing check-in and casual games

- The wellbeing screen presents eight short, illustrated questions one at a time. The frontend sends selected answer IDs to FastAPI; it does not calculate or send a score.
- FastAPI validates the answer set, calculates a private overall score and seven category scores, stores the responses and result in PostgreSQL, and permits one completed check-in per calendar day. A guardian can reset today's completion only with the dependent's `wellbeing` permission; reset records remain in history.
- The guardian report is served by `GET /api/v1/dependents/{dependent_id}/wellbeing/report`. Question and daily-status routes are `GET /api/v1/dependents/{dependent_id}/wellbeing/questions` and `/wellbeing/today`. Submission uses the existing `POST /api/v1/dependents/{dependent_id}/wellbeing-checkins` route.
- The report uses gentle descriptive labels and does not claim to diagnose or measure a medical condition. If a guardian has no wellbeing grant, the API denies access.
- Game sessions are started through `POST /api/v1/dependents/{dependent_id}/game-sessions` and completed through the existing `/api/v1/game-sessions/{session_id}/finish` route. The game prompts use general symbols and patterns rather than personal photos or memory-profile entries.
- These changes are in the `4d237a8a91cf` and `a651e28f14c0` Alembic migrations. Apply them with `alembic upgrade head` before starting the app.

## What the main parts do

- `frontend/app/` contains the landing page, sign-in, registration and role-specific application screens.
- `frontend/lib/api.ts` sends requests to FastAPI and attaches the short-lived bearer token. The token is held in `sessionStorage` for the current browser tab; care records remain in PostgreSQL.
- `backend/app/api/v1/` contains authentication, relationship, care, memory, media, quiz, wellbeing, location, report and admin routes.
- `frontend/features/wellbeing/daily-checkin.tsx` contains the dependent check-in UI and public question/result types; scoring stays in `backend/app/services/wellbeing.py`.
- `frontend/features/games/game-center.tsx` contains the five general-purpose game experiences and persists their sessions through FastAPI.
- `backend/app/models/entities.py` defines SQLAlchemy's PostgreSQL tables.
- `backend/alembic/versions/` contains versioned schema changes.
- `storage/private/` stores local private media files. It is not inside `frontend/public/` and is not a static web directory.
- `docs/` and `database/` contain design and database references.

## Privacy and product limits

- Guardian access requires an active guardian/dependent relationship and a category grant. A dependent can change grants or revoke a link.
- Passwords use Argon2 hashes. JWT logout increments the server token version and invalidates active tokens for that user.
- Quiz answers, casual game sessions, routine events, wellbeing check-ins and scores, alerts and location consent/events are stored in PostgreSQL.
- Location is opt-in and user-triggered. The browser asks for device permission only after the dependent presses “Share current location”; this is not continuous background tracking. Browser geolocation requires localhost or HTTPS.
- The wellbeing check-in is not a clinical assessment. Alerts and help requests do not automatically contact emergency services.
- Reminders appear in the application, but there is no background scheduler, push notification delivery, SMS/email delivery, video-call integration, or automatic inactivity escalation yet.
- Files use local private storage. Production use needs deployment-specific object storage, backups, retention enforcement, malware scanning, secure transport, monitoring, account recovery, rate limits and a review of privacy and legal requirements.
- The demo seed contains fictional identities, phone numbers, schedules and sample activity. Do not use real health information in this development setup.
