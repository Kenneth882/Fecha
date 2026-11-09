# CramPlan

[![CI](https://github.com/Kenneth882/Fecha/actions/workflows/ci.yml/badge.svg)](https://github.com/Kenneth882/Fecha/actions/workflows/ci.yml)

**A language prep app that builds a day-by-day cram plan for one real event by one fixed date.**

Tell CramPlan what's coming — a job interview in Spanish, a wedding speech in Korean, a move to Spain — when it happens, and your current level. It generates a backward-planned study schedule, runs voice roleplay rehearsals of the actual scenario, and tracks a readiness score until the deadline.

Existing apps, courses and tutors don't sell one prep pack for one event by one date. CramPlan does.

> **Status:** In development (8-week build plan, see [Roadmap](#roadmap)). Sections marked _TBD_ will be filled in with real measurements as features ship.

---

## Features (MVP)

- **Onboarding** — event type, target language, event date, self-rated level, optional 10-question placement quiz.
- **Plan generator** — works backward from the event date to produce daily tasks (vocab, listening, speaking), grouped into milestones (e.g. _Airport → Apartment check-in → Utilities → Asking for help_).
- **Daily practice** — today's 3–4 tasks, check-off, streak and a days-to-event countdown.
- **Deadline-aware spaced repetition** — review intervals compress as the event nears; every item is guaranteed a review in the final 48 hours.
- **Voice roleplay** — you speak, the AI plays the landlord or interviewer; the session saves a transcript and feedback.
- **Readiness report** — a 0–100 score per milestone, plus what you nailed and what to revise.

**MVP scope:** Spanish plus one more language; three event templates — job interview, relocation, speech.

**Out of scope for MVP:** payments, B2B team seats, native mobile app, more than 2 languages, phoneme-level pronunciation scoring.

---

## Architecture

```
┌──────────────┐   REST + 1 WebSocket (voice)   ┌──────────────────┐
│  Next.js PWA │ ─────────────────────────────▶ │     FastAPI      │
│ (TS client   │                                │  /api/v1/*       │
│  from OpenAPI)│ ◀───────────────────────────── │                  │
└──────────────┘                                └───┬───┬───┬──────┘
                                                    │   │   │
                                  ┌─────────────────┘   │   └──────────────┐
                                  ▼                     ▼                  ▼
                            ┌──────────┐         ┌──────────┐        ┌──────────┐
                            │ Postgres │         │  Redis   │        │  S3 / R2 │
                            │ (core)   │         │ cache,   │        │ audio,   │
                            └──────────┘         │ limits,  │        │ transcr. │
                                                 │ queue    │        └──────────┘
                                                 └────┬─────┘
                                                      ▼
                                                ┌───────────┐      ┌────────────────┐
                                                │ arq worker│ ───▶ │ LLM / STT / TTS│
                                                │ plan +    │      │   APIs         │
                                                │ reports   │      └────────────────┘
                                                └───────────┘
```

- The web app talks to FastAPI over REST, plus one WebSocket for voice roleplay.
- FastAPI owns every read and write to Postgres, Redis and S3/R2.
- The arq worker runs plan and report generation off the request path and calls the LLM API itself.

### Tech stack

| Layer | Choice |
|---|---|
| API | FastAPI + Pydantic v2 (auto docs at `/docs`) |
| ORM | SQLAlchemy 2.0 (async) + asyncpg |
| Migrations | Alembic |
| Database | Postgres |
| Cache / queue | Redis |
| Background jobs | arq |
| LLM output | Pydantic models + instructor |
| Auth | PyJWT + passlib |
| Voice | STT + LLM + TTS (or a realtime voice API), streamed over WebSockets |
| Storage | S3 or Cloudflare R2 |
| Testing | pytest, pytest-asyncio, httpx.AsyncClient, hypothesis, Playwright |
| Tooling | uv, ruff, mypy, pre-commit, Docker Compose |
| Frontend | Next.js + TypeScript (PWA) |
| Deployment | Vercel (web) · Fly.io or Railway (API + worker) · Neon or Supabase (Postgres) · Upstash (Redis) |

---

## Quick start

Goal: clone, run one command, and try the seeded demo in under 5 minutes.

```bash
git clone <repo-url> cramplan && cd cramplan
cp .env.example .env          # add your LLM / voice API keys
docker compose up             # api, worker, postgres, redis
```

- API: http://localhost:8000 — interactive docs at http://localhost:8000/docs
- Web: http://localhost:3000
- Demo account: **"Job interview in Spanish, 12 days out"** — credentials _TBD_

### Local backend development

```bash
cp .env.example .env          # the one .env, at the repo root; set JWT_SECRET (32+ chars)
cd backend
uv sync
uv run pre-commit install     # ruff, ruff-format and mypy on every commit
uv run alembic upgrade head
uv run uvicorn --factory app.main:create_app --reload
uv run arq app.workers.tasks.WorkerSettings   # in a second terminal
```

### Tests and checks

```bash
cd backend
uv run pytest                 # unit + API tests
uv run pytest --cov=app/services
uv run ruff check . && uv run ruff format --check .
uv run mypy app tests
```

---

## API overview

All routes live under `/api/v1` and require a JWT by default. The only public routes are `/auth/*`, `/health` (liveness) and `/health/ready` (readiness).

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | Liveness (public) |
| GET | `/health/ready` | Readiness: Postgres and Redis (public; added in #3) |
| POST | `/auth/register` | Create account |
| POST | `/auth/login` | Return access token |
| GET | `/auth/me` | Current user |
| POST | `/events` | Create event; enqueues plan generation |
| GET | `/events` | List my events |
| GET | `/events/{id}` | Event detail + days to event |
| GET | `/events/{id}/plan` | Full plan with milestones |
| POST | `/events/{id}/replan` | Rebalance after missed days |
| GET | `/events/{id}/today` | Today's tasks |
| POST | `/tasks/{id}/complete` | Mark a task done |
| GET | `/reviews/due` | SRS items due now |
| POST | `/reviews/{item_id}` | Submit a review grade (0–5) |
| WS | `/roleplay/{milestone_id}` | Stream a voice roleplay session |
| GET | `/roleplay/sessions/{id}` | Transcript + feedback |
| GET | `/events/{id}/readiness` | Readiness report + daily trend |
| GET | `/admin/metrics` | LLM cost and voice latency (admin only) |

---

## Data model

| Table | Key columns | Notes |
|---|---|---|
| User | id, email, password_hash, native_language, created_at | |
| Event | id, user_id, type, target_language, event_date, level, goals | type = interview, relocation, speech |
| Plan | id, event_id, version, status, generated_at | New version on every re-plan |
| Milestone | id, plan_id, title, target_date, order | e.g. "Utilities" |
| Task | id, milestone_id, day, kind, payload (JSON), completed_at | kind = vocab, listen, speak |
| VocabItem | id, phrase, translation, audio_url, scenario_tag, language | Shared across users, cached |
| ReviewState | user_id, vocab_item_id, ease, interval_days, due_at, lapses | One row per user per item |
| RoleplaySession | id, milestone_id, transcript (JSON), audio_url, scores, duration_sec, cost_usd | |
| ReadinessSnapshot | id, event_id, date, per_milestone_scores (JSON), overall | One per day; drives the trend chart |

---

## Engineering highlights

1. **Deadline-compressed spaced repetition.** Standard SM-2/FSRS assumes unlimited time. CramPlan's scheduler shrinks intervals as the event nears and guarantees every item is reviewed at least once in the final 48 hours. Verified with `hypothesis` property tests.
2. **Backward planning.** Given N days, M milestones and a daily time budget, tasks are spread so harder milestones get more reps. Missed days trigger an automatic re-plan that preserves completed work.
3. **Structured LLM output.** Plans and scenarios are generated as JSON validated by Pydantic, with retries, a fallback to hand-written templates, and caching per (language, event type, level).
4. **Low-latency voice loop.** STT → LLM → TTS streamed over a WebSocket, targeting < 1.5 s per turn.
5. **Cost control.** Voice minutes and LLM tokens tracked per user, session length capped, cost per active user reported on the admin page.
6. **Readiness scoring.** SRS retention, task completion and roleplay grades combine into one 0–100 score (formula below).

### Scheduling algorithm

_TBD — document the deadline-compression rule and the final-48-hour guarantee once `srs.py` lands._

### Readiness score formula

_TBD — document inputs, weights and normalization once `scoring.py` lands._

### Measured performance

| Metric | p50 | p95 |
|---|---|---|
| Voice turn latency (target < 1.5 s) | _TBD_ | _TBD_ |
| Plan generation time | _TBD_ | _TBD_ |

| Cost metric | Value |
|---|---|
| LLM + voice cost per active user / month | _TBD_ |
| Plan-generation cost reduction from caching | _TBD_ |

### Tradeoffs

_TBD — e.g. arq vs. Celery, pipelined STT/LLM/TTS vs. realtime voice API, template fallback quality._

---

## Project layout

```
backend/
├── app/
│   ├── main.py            # app factory, lifespan, middleware, routers
│   ├── core/              # config (pydantic-settings), security (JWT, hashing), deps
│   ├── db/                # base, async engine + sessionmaker
│   ├── models/            # SQLAlchemy tables
│   ├── schemas/           # Pydantic request/response models
│   ├── api/v1/            # auth, events, plans, practice, roleplay (WebSocket)
│   ├── services/
│   │   ├── planner.py     # backward planning algorithm (pure Python)
│   │   ├── srs.py         # deadline-compressed scheduler (pure Python)
│   │   ├── llm.py         # plan/scenario generation
│   │   ├── voice.py       # STT/TTS pipeline
│   │   └── scoring.py     # readiness score
│   └── workers/tasks.py   # arq jobs: plan + report generation
├── alembic/
├── tests/
│   ├── unit/              # srs, planner (no DB)
│   └── api/               # endpoint tests with dependency overrides
├── pyproject.toml
└── docker-compose.yml     # api, worker, postgres, redis
web/                       # Next.js + TypeScript PWA
```

---

## Roadmap

Part-time build (~10–15 h/week). Each week ends with something running and tested.

- [ ] **Week 1 — Foundation:** uv/ruff/mypy/pre-commit, Docker Compose, config + async DB + Alembic, User + JWT auth, GitHub Actions CI
- [ ] **Week 2 — Events & template planner:** Event/Plan/Milestone/Task models, Event CRUD, template-based `planner.py`, `GET /events/{id}/today`
- [ ] **Week 3 — Spaced repetition:** VocabItem/ReviewState, `srs.py` + property tests, review endpoints, Spanish seed vocab, Next.js onboarding + daily practice
- [ ] **Week 4 — LLM generation:** `llm.py` with instructor, arq worker, retries/fallback/Redis cache, fake-LLM test override
- [ ] **Week 5 — Roleplay (text):** WebSocket text turns, per-milestone scenario prompts, transcript + feedback
- [ ] **Week 6 — Voice:** STT/TTS streaming, audio to S3/R2, per-turn latency + per-session cost logging
- [ ] **Week 7 — Scoring & re-planning:** `scoring.py` + daily snapshot job, readiness page, re-plan endpoint, rate limiting + session caps
- [ ] **Week 8 — Ship:** deploy, admin metrics page, Playwright E2E, README/diagram/demo video/seeded demo account

### Stretch goals (post-MVP)

Phoneme-level pronunciation scoring · React Native/Expo app · Stripe one-time event packs · B2B mode for HR relocation teams · offline final-day review via PWA caching · more languages and event templates

---

## Demo

_TBD — 2-minute demo video link._
