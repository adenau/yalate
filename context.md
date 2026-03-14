# YaLate Agent Context

This file is for coding agents working in this repository.

## What this project is

**YaLate** = *Yet Another Late Dashboard*.

Goal: provide a calendar-focused dashboard for scheduled social posts, starting with GetLate as a source (and potentially additional publication sources later).

## Current architecture

Monorepo with two apps:

- `backend/`: Python + Flask API
- `frontend/`: React + Vite web app

Current hello-world integration is complete:

- Backend exposes `GET /api/hello`
- Frontend fetches `/api/hello` and renders the message

## Backend status (Flask)

Implemented:

- App factory pattern in `backend/app/__init__.py`
- SQLAlchemy via Flask extension in `backend/app/extensions.py`
- Environment-based config in `backend/app/config.py`
  - Development/default: SQLite
  - Production: MySQL (`mysql+pymysql://...`)
  - Testing: in-memory SQLite
- API routes in `backend/app/routes.py`
- Entrypoint in `backend/run.py`
- Basic model placeholder in `backend/app/models.py`
- Pytest smoke test in `backend/tests/test_api.py`

Dependencies are in `backend/requirements.txt` and include:

- `Flask`
- `Flask-SQLAlchemy`
- `Flask-Cors`
- `python-dotenv`
- `pytest`
- `PyMySQL`

## Frontend status (React/Vite)

Implemented:

- Vite React app scaffold in `frontend/`
- API proxy in `frontend/vite.config.js`:
  - `/api` -> `http://127.0.0.1:5000`
- Main app in `frontend/src/App.jsx` calls `/api/hello`

## Environment / run notes

Python environment:

- Project virtual environment is at `.venv/`
- Typical activation (PowerShell): `\.venv\Scripts\Activate.ps1`

Run backend:

- `python backend/run.py`

Run tests:

- `cd backend`
- `pytest`

Run frontend:

- `cd frontend`
- `npm run dev`

Build frontend:

- `npm run build`

## API/domain reference files

These docs are available under `docs/` for future integration work:

- `docs/getlate-llms-full.txt` (GetLate API context)
- `docs/ghostblog-llms-full.txt` (Ghost blog API/context file added by user)

Use these files as source context before implementing integrations.

## Conventions and intent for future agents

1. Keep backend and frontend as separate projects in the same repo.
2. Prefer small, incremental changes and keep hello-world flow working.
3. Maintain DB portability:
   - local/dev -> SQLite
   - prod -> MySQL
4. Add/maintain pytest coverage for backend behavior changes.
5. Avoid large refactors unless explicitly requested.

## Recommended next implementation steps

1. Add `Flask-Migrate` + Alembic migrations.
2. Define core data model(s) for scheduled posts and source mapping.
3. Add GetLate client/service layer and env-configured API key handling.
4. Expose first real endpoint (e.g., list scheduled posts normalized for calendar UI).
5. Replace hello-world frontend with basic calendar/list view consuming that endpoint.
6. Add tests for service and endpoint behavior.
