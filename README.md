# Lineup – Queue Management App

Full-stack queue manager. **React (Vite) + FastAPI + SQLite**, JWT auth.

## Features
| # | Requirement | Where |
|---|-------------|-------|
| 1 | Manager login, create queues | `/api/auth/*`, `POST /api/queues` · `Login.jsx`, sidebar |
| 2 | Each queue has a name | unique per manager (case-insensitive) |
| 3 | Add person → token created | `POST /api/queues/{id}/tokens` (auto-numbered `T-001`, `T-002`…) |
| 4 | Waiting list | live list with position and waiting time (auto-refresh every 4 s) |
| 5 | Move tokens up/down | `POST /api/tokens/{id}/move` |
| 6 | Assign top token for service | **Call next** button → `POST /api/queues/{id}/serve-next`; **Mark done** completes it |
| 7 | Cancel a token | `POST /api/tokens/{id}/cancel` |
| 8 | Analytics dashboard | avg/max wait, avg service time, peak length, queue-length trend, wait per token |

## Run locally
```bash
# 1. Backend (http://127.0.0.1:8000, docs at /docs)
cd backend
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload

# 2. Frontend (http://localhost:5173) – new terminal
cd frontend
npm install
npm run dev
```
Open http://localhost:5173, click **Create an account**, then create a queue.

**Single-process mode:** `cd frontend && npm run build`, then run `uvicorn main:app` from `backend/` – FastAPI serves the built UI at http://127.0.0.1:8000.

## Tests
```bash
cd backend && pytest -q
```

## Design notes (for the interview)
- **Token lifecycle:** `waiting → serving → served`, or `waiting → cancelled`. Timestamps `created_at`, `called_at`, `completed_at` give wait time (`called_at − created_at`) and service time (`completed_at − called_at`).
- **Ordering:** each waiting token has an integer `position`. Moving swaps two neighbours and renumbers the line (1..n) in one transaction, so order never ties or drifts.
- **Trend data:** an `events` table stores a queue-length snapshot every time the waiting count changes (add, call, cancel); the chart plots it as a step line.
- **Auth:** PBKDF2-SHA256 password hashing (stdlib), JWT (7 days). Every queue/token endpoint checks ownership, so managers can't see each other's data.
- **Config:** `SECRET_KEY` and `DATABASE_URL` env vars (defaults are dev-only).
