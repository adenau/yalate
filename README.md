# YaLate (Yet Another Late Dashboard)

Monorepo for a calendar-focused social publishing dashboard.

## Structure

- `backend/`: Flask API (`Flask`, `Flask-SQLAlchemy`, `pytest`)
- `frontend/`: React app (`Vite`)
- `docs/getlate-llms-full.txt`: Downloaded GetLate API LLM documentation

## Backend setup (virtual environment)

From repository root:

```powershell
# Environment is configured at .venv
.\.venv\Scripts\Activate.ps1
pip install -r backend\requirements.txt
```

Run backend API:

```powershell
python backend\run.py
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

Run tests:

```powershell
cd backend
pytest
```

## Frontend setup

```powershell
cd frontend
npm install
npm run dev
```

The Vite dev server proxies `/api/*` to `http://127.0.0.1:5000`.

## Hello World flow

1. Start backend on port `5000`.
2. Start frontend on port `5173`.
3. Open the frontend and it will call `/api/hello` and render the backend message.
