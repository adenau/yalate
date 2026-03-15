# YaLate (Yet Another Late Dashboard)

Monorepo for a calendar-focused social publishing dashboard.

## Structure

- `backend/`: Flask API (`Flask`, `Flask-SQLAlchemy`, `pytest`)
- `frontend/`: React app (`Vite`)
- `docs/getlate-llms-full.txt`: Downloaded Late API LLM documentation

## Backend setup (virtual environment)

From repository root, create and activate a virtual environment at `.venv`:

```bash
# macOS / Linux
python3 -m venv .venv
source .venv/bin/activate
```

```powershell
# Windows (PowerShell)
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

```bat
:: Windows (Command Prompt)
python -m venv .venv
.venv\Scripts\activate.bat
```

Then install backend dependencies:

```bash
pip install -r backend/requirements.txt
```

Run backend API:

```bash
python backend/run.py
```

Backend host/port are configurable:

- `BACKEND_HOST` (default: `0.0.0.0`)
- `BACKEND_PORT` (default: `5001`)

Examples:

```bash
# macOS / Linux
BACKEND_PORT=5050 python backend/run.py
```

```powershell
# Windows PowerShell
$env:BACKEND_PORT=5050; python backend/run.py
```

```bat
:: Windows Command Prompt
set BACKEND_PORT=5050 && python backend\run.py
```

Initialize DB tables quickly:

```powershell
cd backend
flask --app run.py init-db
```

Or use migrations:

```powershell
cd backend
flask --app run.py db init
flask --app run.py db migrate -m "create users table"
flask --app run.py db upgrade
```

API endpoints:

- `GET /health`
- `GET /api/hello`
- `POST /api/auth/signup`
- `POST /api/auth/login`
- `POST /api/auth/logout`
- `GET /api/auth/me`
- `POST /api/calendars`
- `GET /api/calendars`
- `POST /api/calendars/validate`
- `PATCH /api/calendars/<id>`
- `DELETE /api/calendars/<id>`
- `POST /api/posts/sync`
- `GET /api/posts`

`POST /api/posts/sync` returns:

- `200` when all selected calendars sync successfully.
- `207` when one or more calendars fail, with per-calendar errors in `results`.

Calendar setup notes:

- `getlate` calendars require: `api_key`, `profile_id` (and optional `profile_name`, `name`).
- `ghost_blog` calendars require: `api_key`, `blog_url` (and optional `name`).
	- Ghost Content API key works for published content.
	- Ghost Admin API key (`id:secret`) enables admin-post sync, including scheduled and email-only posts.
- Use `POST /api/calendars/validate` to check provider credentials before saving.
- Calendars can be updated with `PATCH /api/calendars/<id>` and removed with `DELETE /api/calendars/<id>`.

Optional backend environment variables for provider fetches:

- `LATE_API_BASE_URL` (defaults to `https://getlate.dev/api/v1`)
- `GHOST_API_BASE_URL` (fallback only when a Ghost calendar does not provide `blog_url`)
- `CALENDAR_VALIDATE_ON_CREATE` (`true`/`false`, default `true`)
- `CALENDAR_VALIDATE_ON_UPDATE` (`true`/`false`, default `true`)

Run tests:

```powershell
cd backend
pytest
```

## Frontend setup

```bash
cd frontend
npm install
npm run dev
```

Frontend/server ports are configurable:

- `FRONTEND_PORT` (default: `5173`)
- `BACKEND_HOST` (default: `127.0.0.1` for Vite proxy)
- `BACKEND_PORT` (default: `5001` for Vite proxy)

Examples:

```bash
# macOS / Linux
cd frontend
FRONTEND_PORT=5174 BACKEND_PORT=5050 npm run dev
```

```powershell
# Windows PowerShell
cd frontend
$env:FRONTEND_PORT=5174; $env:BACKEND_PORT=5050; npm run dev
```

```bat
:: Windows Command Prompt
cd frontend
set FRONTEND_PORT=5174 && set BACKEND_PORT=5050 && npm run dev
```

## Hello World flow

1. Start backend on your chosen `BACKEND_PORT` (default `5001`).
2. Start frontend on your chosen `FRONTEND_PORT` (default `5173`).
3. Open the frontend and it will call `/api/hello` and render the backend message.
