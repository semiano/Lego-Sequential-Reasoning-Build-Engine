# LeoCAD Tool Kit v0

Deterministic local control plane for LeoCAD + LDraw experimentation.

## Stack
- Backend: FastAPI + SQLAlchemy + SQLite (`backend/`)
- Frontend: Next.js App Router + TypeScript + Three.js (`frontend/`)
- Runtime artifacts: filesystem under `data/`

## Prerequisites
- Windows (first-class), macOS, or Linux
- Python 3.11+
- Node.js 20+
- LeoCAD installed locally
- Local LDraw parts library directory

## Environment Variables (Backend)
Set these before running backend:

- `LEOCAD_EXE` (optional): LeoCAD executable path. Default: `leocad`
- `LDRAW_PARTS_DIR` (recommended): local LDraw parts library root
- `DATA_DIR` (optional): defaults to `./data`
- `DATABASE_URL` (optional): defaults to `sqlite:///./data/app.db`
- `CORS_ORIGINS` (optional): comma-separated, default `http://localhost:3000`

Example PowerShell:

```powershell
$env:LEOCAD_EXE = "C:\Program Files\LeoCAD\leocad.exe"
$env:LDRAW_PARTS_DIR = "C:\LDraw"
```

## Run Backend

```powershell
cd backend
python -m pip install -e ".[dev]"
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Health check: `http://localhost:8000/health`

## Run Frontend

```powershell
cd frontend
npm install
$env:NEXT_PUBLIC_API_BASE = "http://localhost:8000"
npm run dev
```

Open `http://localhost:3000`.

Note: frontend dev and production builds use separate output dirs (`.next-dev` for dev, `.next` for build) to avoid runtime chunk/module conflicts when both commands are run in parallel.

## Optional: Docker Compose

```powershell
docker compose up --build
```

Backend: `http://localhost:8000`  
Frontend: `http://localhost:3000`

To stop:

```powershell
docker compose down
```

## Example LDraw Line

```text
1 16 0 0 0 1 0 0 0 1 0 0 0 1 3001.dat
```

## Implemented API (v0)

### Workspaces
- `POST /api/workspaces`
- `GET /api/workspaces`
- `GET /api/workspaces/{id}`
- `GET /api/workspaces/{id}/timeline`
- `GET /api/workspaces/{id}/current`

### Model Operations
- `POST /api/workspaces/{id}/append`
- `POST /api/workspaces/{id}/checkpoint`
- `POST /api/workspaces/{id}/render`

### Artifacts
- `GET /api/workspaces/{id}/artifacts/{rel_path}`

### Parts
- `GET /api/parts/search?q=3023&limit=25`
- `GET /api/parts/{part_id}`
- `GET /api/parts/{part_id}/preview?view=iso&w=512&h=512`

## Storage Layout

```text
data/
  workspaces/
    {workspace_id}/
      model/
        current.ldr
        step_0001.ldr
      renders/
        step_0002/
          iso.png
          front.png
          side.png
          top.png
          turntable/
            frame_0001.png
      meta/
```

`current.ldr` is source of truth.

## LeoCAD CLI Notes

`backend/app/core/leocad_cli.py` includes a small command adapter with fallback behavior:
- tries a couple of argument styles
- if non-`iso` view fails, falls back to `iso` while keeping artifact naming

If your local LeoCAD CLI syntax differs, update command candidates in `LeoCADCLI.render_single`.

## Tests

```powershell
cd backend
python -m pytest
```

Current tests cover:
- workspace creation
- append writes file + DB rows
- checkpoint snapshot
- artifact path traversal safety

## Troubleshooting
- **Render fails with executable not found**: set `LEOCAD_EXE` explicitly.
- **Part search returns nothing**: set `LDRAW_PARTS_DIR` to your LDraw root.
- **Frontend cannot reach backend**: verify `NEXT_PUBLIC_API_BASE` and CORS settings.
- **Camera preset issues**: keep using `iso` and adjust CLI flags in wrapper.

## AI Build Engine (v1 baseline)

The repo now includes a production-structured engine under `engine/` with provider abstraction, persistence, retrieval, planning, generation, evaluation, and orchestration.

### Engine Setup

```powershell
cd engine
python -m pip install -e .
```

Required env vars:

- `OPENAI_API_KEY`
- `MODEL_PLANNER` (optional, default `gpt-4.1`)
- `MODEL_BUILDER` (optional, default `gpt-4.1-mini`)
- `MODEL_NAMER` (optional, default `gpt-4.1-mini`)
- `OPENAI_BASE_URL` (optional override)

Optional retrieval var:

- `SERPAPI_API_KEY`

### Run Engine

```powershell
python -m engine.main run --concept .\bird.png --name hummingbird --control-plane http://localhost:8000 --preset .\presets\bird_sculpt.json
```

Other commands:

```powershell
python -m engine.main resume --run-id <run_id> --control-plane http://localhost:8000
python -m engine.main stop --run-id <run_id>
python -m engine.main report --run-id <run_id> --control-plane http://localhost:8000
python -m engine.main export --run-id <run_id> --output .\run_report.md
```

### Engine Notes

- All mutations go through control-plane API (`append`, `render`, `checkpoint`, `timeline`).
- Planner and builder outputs are JSON-schema validated with retry/repair.
- Raw LLM responses and per-step plan/render traces are written under `data/engine/runs/<run_id>/`.
- Evaluation is local-first (CLIP if available, fallback image embedding otherwise).
