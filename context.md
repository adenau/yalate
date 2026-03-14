# YaLate Agent Context

This file is for coding agents working in this repository.

## Project summary

**YaLate** = *Yet Another Late Dashboard*.

Current goal: calendar-first dashboard that can authenticate users, register external content calendars (GetLate/Ghost), sync posts into local DB, and display those posts on a React calendar.

## Repo architecture

Monorepo:

- `backend/`: Flask API + SQLAlchemy + Alembic migrations + pytest
- `frontend/`: React + Vite + `react-big-calendar`
- `docs/`: provider reference docs (`getlate-llms-full.txt`, `ghostblog-llms-full.txt`)

## Backend current status

### Core stack

- App factory + extensions in `backend/app/__init__.py`, `backend/app/extensions.py`
- Config in `backend/app/config.py`
  - dev: SQLite (`DATABASE_URL` default)
  - prod: MySQL (`mysql+pymysql://...`)
  - tests: in-memory SQLite
- Auth/session: Flask-Login
- Migrations: Flask-Migrate/Alembic

### Domain model

In `backend/app/models.py`:

- `User` with password hashing and login timestamps
- `Calendar` with source enum (`getlate`, `ghost_blog`, `wordpress`), encrypted API key, profile metadata
- `PostType`
- `Post` linked to `Calendar` and `PostType`
- Unique constraint for idempotent sync: `(calendar_id, external_id)`

### Security

- API keys encrypted at rest using Fernet helpers in `backend/app/security.py`
- Env var: `CALENDAR_KEYS_ENCRYPTION_KEY` (fallback derived from `SECRET_KEY`)

### API endpoints implemented

- Health/hello: `GET /health`, `GET /api/hello`
- Auth: `POST /api/auth/signup`, `POST /api/auth/login`, `POST /api/auth/logout`, `GET /api/auth/me`
- Calendars: `POST /api/calendars`, `GET /api/calendars`
- Posts:
  - `POST /api/posts/sync` (pull from providers + upsert into DB)
  - `GET /api/posts` (read DB-backed posts for current user)

### Sync service

Implemented in `backend/app/post_ingestion.py`:

- Provider fetchers for GetLate and Ghost
- Upsert behavior by `(calendar_id, external_id)`
- Post-type auto-create by slug
- Title/preview normalization:
  - first 100 chars of content (fallback to title)
  - line-break preservation + basic HTML cleanup
- Debug logging around requests and sync counts
- GetLate pagination now uses documented `limit` + `offset` pattern

### Sync debugging additions

`POST /api/posts/sync` now supports debug mode (`debug=true` body/query) and returns per-calendar diagnostics:

- `fetched`, `created`, `updated`
- `db_post_count`
- optional error + traceback when debug is enabled

## Frontend current status

Main app in `frontend/src/App.jsx`:

- Login/signup/logout flow
- Sidebar calendars loaded from backend
- Add-calendar form (source-aware fields)
- Manual `Sync Posts` button
- Sync on load after auth and after calendar creation
- Events loaded from `GET /api/posts` and rendered via `react-big-calendar`
- Active/inactive calendar filtering is currently UI-local state (not persisted yet)

Styling in `frontend/src/App.css` includes:

- Dashboard/sidebar layout
- Add-calendar form styles
- Event content line breaks (`white-space: pre-line`)

## Migrations status

Latest migration chain includes:

1. users schema
2. calendars/post_types/posts
3. calendar credential/profile fields
4. unique constraint on posts `(calendar_id, external_id)` (SQLite batch-safe)

## Environment notes

Backend env example (`backend/.env.example`) includes:

- `CALENDAR_KEYS_ENCRYPTION_KEY`
- `GETLATE_API_BASE_URL` (default `https://getlate.dev/api/v1`)
- `GHOST_API_BASE_URL`
- `DATABASE_URL`

## Test/build status (latest)

- Backend: `14 passed` (`pytest`)
- Frontend: `npm run build` successful

## Known current caveats

1. If backend code changes while server is running, restart backend before re-testing sync.
2. Calendar active/inactive toggle is not persisted to backend yet.
3. If provider response contracts differ from docs, use sync debug payload/logs to inspect raw behavior and adjust mapping.

## Suggested next steps

1. Persist calendar toggle state (`PATCH /api/calendars/<id>` for `is_active`).
2. Add lightweight in-UI sync diagnostics panel (instead of console-only debug logging).
3. Add provider-contract tests/mocks for GetLate list-posts response variants.
4. Add optional background/queued sync strategy and explicit reload semantics.
