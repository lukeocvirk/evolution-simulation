Evolution Sim (Python + React)

An evolution simulation with a Python backend and a React canvas frontend.

Requirements
- Python 3.11+ (with pip)
- Node 18+ (for the frontend)

Run (Web UI)
1) Backend
   - Create/activate a venv (optional) and install deps:
     - `python -m pip install fastapi pydantic uvicorn[standard]`
   - Start the server:
     - `python -m uvicorn backend.api:app --reload --port 8000`
2) Frontend
   - `cd frontend`
   - `npm install` (or `npm ci`)
   - `npm run dev` (open the shown URL)

Notes
- The server starts stepping only when a page is connected and resets on first connect.
- State is sent as `{ entity_id, species_id, x, y, colour }` (x/y in [0,1]).

CLI (no UI)
- `cd backend && python3 run.py`

Outputs
- Written under `backend/output/`:
  - `output.txt` per‑timestep summary
  - `molecules.txt` species info log
  - `final.txt` final summary
