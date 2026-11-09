# CLAUDE.md

Guidance for Claude Code when working in this repository.

## Project

**CramPlan** — a language prep app that builds a day-by-day cram plan for one real event (job interview, relocation, speech) by one fixed date, runs voice roleplay rehearsals, and tracks a 0–100 readiness score until the deadline.

This is a portfolio SWE project built over an 8-week plan (see Roadmap in `README.md`). It is in early development; much of the layout below is the target structure, not yet present. Check what actually exists before assuming a file or module is there.

## Stack

- **Backend:** Python, FastAPI, Pydantic v2, SQLAlchemy 2.0 async + asyncpg, Alembic, Postgres, Redis, arq, instructor, PyJWT + passlib
- **Frontend:** Next.js + TypeScript PWA in `web/`, calling the API through a TypeScript client **generated from FastAPI's OpenAPI schema** (never hand-write API types)
- **Storage:** S3 or Cloudflare R2 for audio and transcripts
- **Tooling:** uv, ruff, mypy, pre-commit, Docker Compose, GitHub Actions

## Commands

Run from `backend/` unless noted.

```bash
docker compose up                              # full stack: api, worker, postgres, redis
uv sync                                        # install deps
uv run uvicorn --factory app.main:create_app --reload --no-access-log  # API on :8000, docs at /docs; the app writes its own JSON access log
uv run arq app.workers.tasks.WorkerSettings    # background worker
uv run alembic revision --autogenerate -m "…"  # new migration
uv run alembic upgrade head                    # apply migrations
uv run pytest                                  # all tests
uv run pytest tests/unit                       # pure-logic tests only (fast, no DB)
uv run pytest --cov=app/services               # coverage (target 80%+ on services)
uv run ruff check . --fix && uv run ruff format .
uv run mypy app
```

Always use `uv run` / `uv add` — never `pip install`.

## Architecture rules

- **FastAPI owns all I/O.** Only the API and the arq worker touch Postgres, Redis, S3/R2 and external AI APIs. The frontend talks only to `/api/v1` (REST) and one WebSocket (`/roleplay/{milestone_id}`).
- **`services/planner.py` and `services/srs.py` are pure functions.** No FastAPI, SQLAlchemy, Redis or network imports. Inputs and outputs are plain data / Pydantic models. This keeps them trivially testable and explainable. `scoring.py` should follow the same rule.
- **Layering:** `api/v1/*` routers → `services/*` → `models/*` via the DB session. Routers stay thin: validate, call a service, return a schema.
- **Schemas vs models:** `schemas/` holds Pydantic request/response models; `models/` holds SQLAlchemy tables. Don't return ORM objects directly from routes without a response schema.
- **Dependencies:** get the DB session and current user via `Depends(get_db)` / `Depends(get_current_user)` from `core/deps.py`. `get_db` is a `yield` dependency.
- **Config:** all settings come from `core/config.py` (pydantic-settings). Locally they're read from env vars plus the single repo-root `.env`; containers get real env vars from compose, not files. No hardcoded URLs, keys or secrets; never commit `.env`.
- **Composition roots:** only `create_app`, the arq worker's startup and `alembic/env.py` call `load_settings()`. Everything else receives `Settings` as a parameter or via `Depends(get_settings)` from `core/deps.py`. `app.main` has no module-level app: the API runs with `uvicorn --factory app.main:create_app`.
- **Long work goes to the worker.** Plan and report generation run as arq jobs in `workers/tasks.py`, not in the request path. `POST /events` enqueues plan generation.
- **Plans are versioned.** Re-planning creates a new `Plan` version; it must never lose or overwrite completed tasks.
- **Startup/shutdown** (DB engine, Redis pool, HTTP clients) goes in the `lifespan` context manager in `main.py`.

## LLM and voice

- Every LLM call returns a Pydantic-validated object via instructor. No free-text parsing.
- Every LLM generation path needs: retries, a fallback to hand-written templates, and Redis caching keyed by (language, event type, level).
- Track tokens and cost per call; track voice minutes and per-turn latency per session (`RoleplaySession.cost_usd`, `duration_sec`).
- Voice loop target: **< 1.5 s per turn** (STT → LLM → TTS, streamed). Don't add blocking work to the WebSocket loop.
- Enforce session length caps and per-user rate limits (middleware).
- Default to current Claude models if using Anthropic (e.g. `claude-sonnet-5-5`; `claude-opus-5-5` for harder generation).

## Core algorithms (get these right)

- **Deadline-compressed SRS** (`srs.py`): SM-2/FSRS-style, but intervals shrink as the event date approaches, and **every item must be reviewed at least once in the final 48 hours** before the event. Review grades are 0–5.
- **Backward planner** (`planner.py`): given N days, M milestones and a daily time budget, distribute vocab/listen/speak tasks so harder milestones get more reps; 3–4 tasks per day.
- **Readiness score** (`scoring.py`): combine SRS retention, task completion and roleplay grades into 0–100. Document the formula and weights in `README.md` whenever it changes.

## Testing

- `tests/unit/` — pure-logic tests for `srs.py`, `planner.py`, `scoring.py`. Use **hypothesis** property tests for invariants (e.g. the 48-hour guarantee, no review scheduled after the event date, intervals non-increasing as deadline nears).
- `tests/api/` — endpoint tests with `httpx.AsyncClient` and `app.dependency_overrides` to swap in a test DB and a **fake LLM**. Tests must never call real LLM, STT or TTS APIs.
- One Playwright E2E test: onboarding → first task.
- Add or update tests with every behavior change; run `pytest`, `ruff` and `mypy` before calling work done.

## Conventions

- Full type hints everywhere; code must pass `mypy`.
- Async all the way down in the API (async SQLAlchemy sessions, async HTTP clients).
- All routes under `/api/v1`, protected by default: new routes go on the protected router. The only public exceptions are `/auth/*`, `/health` and `/health/ready`, on `public_router`. Admin-only routes (e.g. `/admin/metrics`) check role.
- Every route has exactly one tag; OpenAPI operation IDs are `{tag}-{route name}` (e.g. `health-liveness`) and feed the generated TS client.
- Structured JSON logging with a request ID per call.
- Security: hashed passwords, short-lived JWTs, no secrets in the repo.
- Schema changes always go through an Alembic migration.
- After changing API routes or schemas, regenerate the frontend TypeScript client.

## Scope

MVP: Spanish + at most one more language; event templates = interview, relocation, speech.

**Do not build** (unless explicitly asked): payments/Stripe, B2B/multi-tenant, native mobile, more than 2 languages, phoneme-level pronunciation scoring. These are post-MVP stretch goals.

## Quality bar

A reviewer should be able to clone the repo, run `docker compose up`, and try the seeded demo account ("Job interview in Spanish, 12 days out") in under 5 minutes. Keep that path working.

## Agent skills

### Issue tracker

Issues and specs live in GitHub Issues for Kenneth882/Fecha, via the `gh` CLI. See `docs/agents/issue-tracker.md`.

### Triage labels

Default five-role vocabulary (needs-triage, needs-info, ready-for-agent, ready-for-human, wontfix). See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: one `GLOSSARY.md` + `docs/adr/` at the repo root. See `docs/agents/domain.md`.
