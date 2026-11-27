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
git clone https://github.com/Kenneth882/Fecha.git cramplan && cd cramplan
cp .env.example .env          # the placeholders work as-is on your machine
docker compose up             # web, api, worker, postgres, redis
```

The api container applies migrations (`alembic upgrade head`) and loads the seed vocabulary and the fallback Listen Dialogues (`python -m app.load_seed_vocab`) before it starts serving, so a fresh database needs no manual steps.

- Web: http://localhost:3000 — register or log in (the demo login is below), then create an Event in onboarding and practise from Today: Vocab Tasks, Reviews and the Plan
- API: http://localhost:8000 — interactive docs at http://localhost:8000/docs, readiness at http://localhost:8000/api/v1/health/ready
- Demo account: **"Job interview in Spanish, 12 days out — day 4"**. Seed it once the stack is up:

  ```bash
  docker compose exec api python -m app.seed   # or, on the host: cd backend && uv run python -m app.seed
  ```

  Then log in at http://localhost:3000/login (or through `/docs`) as `demo@example.com` / `local-demo-only-2026!` (local placeholders, set by `DEMO_EMAIL` / `DEMO_PASSWORD`). The demo starts on Day 4 of 15 with three days of history, built through the real services: Days 1–3's Vocab Tasks are done, their Reviews graded (mostly Good, a few Again), and about 20 Reviews are due today. Days 1–3's Listen and Speak Tasks show as Missed; today's Listen Tasks can be played, on hand-written Listen Dialogues, with no Anthropic API key. Re-running it is safe: it recreates the demo User and replays that history so that today is always Day 4, with the Event Day 12 days away, so the demo never goes stale. It needs the seed vocabulary and fallback Listen Dialogues, which the api container loads on start (on the host, run `python -m app.load_seed_vocab` first). It doesn't run on `docker compose up` yet (Week 8).

### Local backend development

```bash
cp .env.example .env          # the one .env, at the repo root
docker compose up -d postgres redis   # only the services; also creates the cramplan_test database
cd backend
uv sync
uv run pre-commit install     # ruff, ruff-format and mypy on every commit
uv run alembic upgrade head
uv run python -m app.load_seed_vocab         # upsert the Spanish seed Vocab Items and fallback Listen Dialogues (safe to re-run)
uv run uvicorn --factory app.main:create_app --reload --no-access-log
uv run arq app.workers.tasks.WorkerSettings   # in a second terminal
uv run python -m app.seed                     # recreate the demo User on Day 4 of their Event
```

### Local web development

Node is pinned in `web/.nvmrc`; the package manager is npm, with exact versions in `package-lock.json`.

```bash
cd web
npm ci
API_URL=http://localhost:8000 npm run dev    # http://localhost:3000; needs the API running
```

`API_URL` is FastAPI's address. Only the Next.js server reads it: browser code calls the web app's own origin, never FastAPI (ADR 0007).

**The API client is generated, never hand-written.** `npm run generate:api` exports the OpenAPI schema straight from `create_app()` (`uv run python -m app.export_openapi`, no server, database or `.env` needed), then `openapi-typescript` turns it into `web/src/lib/api/schema.ts`, which `openapi-fetch` uses. Run it after any change to the API's routes or schemas and commit both files; CI regenerates them and fails if anything differs.

**Sessions go through the Next.js server (ADR 0007).** Browser code never sees a token:
- `/api/session/login`, `/register`, `/refresh` and `/logout` are Next.js route handlers that call FastAPI and keep its tokens in `HttpOnly`, `SameSite=Lax` cookies (`Secure` everywhere but localhost). The access cookie (`cramplan_access`, `Path=/`) lasts as long as the access token. The refresh cookie (`cramplan_refresh`) is sent only to `/api/session/*` and lasts as long as the refresh token.
- `/api/v1/*` is forwarded to FastAPI with the access cookie as `Authorization: Bearer` and no cookies. It refuses `/api/v1/auth/*` (except `/auth/me`), whose bodies carry tokens.
- `src/proxy.ts` rejects any `POST`, `PATCH`, `PUT` or `DELETE` whose `Origin` isn't the app's own (taken from the `Host` header), and sends a page request whose access token is missing or under 2 minutes from expiring through `GET /api/session/refresh?next=…`, which rotates the tokens and comes back, or goes to `/login?next=…` once the session is over. If FastAPI is down, that refresh shows a plain "can't be reached" page and keeps the session.
- A Server Component that gets a 401 from FastAPI (it refused a live-looking token) sends the User to `/login?next=…`; `/login` and `/register` are always reachable, so that can't loop.
- In browser code, `createBrowserApiClient()` (`src/lib/api/browser.ts`) answers a 401 by calling `POST /api/session/refresh` and retrying once; requests that fail together share one refresh. Server Components use `createUserApiClient()` (`src/lib/api/server.ts`).

### Tests and checks

```bash
cd backend
uv run pytest                 # unit + API tests; needs postgres and redis running
uv run pytest --cov=app/services
uv run ruff check . && uv run ruff format --check .
uv run mypy app tests alembic

cd ../web
npm run lint && npm run typecheck && npm test && npm run build
```

**End-to-end test.** One Playwright test, `web/e2e/onboarding-to-first-task.spec.ts`, covers the main path in a real browser: register → onboarding → Today → open the first Vocab Task → Done → the Task shows as Done, even after a reload. It also checks that no token or JWT can be read from `document.cookie`, `localStorage` or `sessionStorage` (ADR 0007). It drives the full stack, so start that first. Each run registers a new User, so it needs no cleanup and can run again on the same stack.

```bash
cp .env.example .env          # from the repo root, if you haven't yet
docker compose up --build     # --build so the containers run your current code
cd web
npx playwright install chromium   # once, or after Playwright is upgraded; on Linux add --with-deps
npm run test:e2e                  # against http://localhost:3000; set E2E_BASE_URL to use another address
npx playwright show-report        # the HTML report, with a trace for any failure
```

Playwright doesn't start a server itself. To test uncommitted web changes without rebuilding the image, run `docker compose stop web` and then `API_URL=http://localhost:8000 npm run dev` on the same port. CI's `e2e` job builds the stack from the commit, waits for `/api/v1/health/ready`, runs the test, and on failure uploads the report and traces and prints the stack's logs.

### Security headers

Every web response carries `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff` and `Referrer-Policy: strict-origin-when-cross-origin`, set in `web/next.config.ts`. Pages also get a Content-Security-Policy from `web/src/proxy.ts`: `connect-src 'self'`, `frame-ancestors 'none'`, and scripts and styles only with a fresh per-request nonce (no `'unsafe-inline'`), which Next.js adds to its own tags. Nonces need per-request rendering, so every page is dynamic.

---

## API overview

All routes live under `/api/v1` and require a JWT by default. The only public routes are `/auth/register`, `/auth/login`, `/auth/refresh`, `/health` (liveness) and `/health/ready` (readiness). Send the access token from `/auth/login` as `Authorization: Bearer <token>`; it lasts `ACCESS_TOKEN_EXPIRE_MINUTES` (default 30).

Login also returns a refresh token (ADR 0007). Send it to `/auth/refresh` before the access token expires to get a new access token and a new refresh token; the one you sent stops working, so keep only the newest. A session ends after `REFRESH_TOKEN_IDLE_DAYS` (default 30) without a refresh, and `REFRESH_TOKEN_ABSOLUTE_DAYS` (default 90) after its login however often it's refreshed. Presenting a refresh token that's already been used or revoked counts as theft and ends every session of that User, with two exceptions: a token swapped by a refresh less than `REFRESH_TOKEN_REUSE_GRACE_SECONDS` ago (default 30) gets a new token of its own, unless its session was logged out since, so two tabs or a retry racing one refresh stay logged in; and an expired token is simply refused. `/auth/logout` ends the session on the server. Only a SHA-256 hash of each refresh token is stored.

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | Liveness (public) |
| GET | `/health/ready` | Readiness: Postgres and Redis (public; added in #3) |
| POST | `/auth/register` | Create a User; returns the profile (public; added in #6) |
| POST | `/auth/login` | Exchange email and password for an access token and a refresh token, starting a session (public; added in #7, refresh token added in #45) |
| POST | `/auth/refresh` | Swap a refresh token for a new access token and refresh token; the old one is revoked. 401 `invalid_refresh_token` if it's unknown, expired or revoked, and a revoked one also revokes every session of its User (public; added in #45) |
| POST | `/auth/logout` | Revoke the session the given refresh token belongs to; 204. Unknown tokens and other Users' tokens are ignored (added in #45) |
| GET | `/auth/me` | The current User's profile (added in #7) |
| POST | `/events` | Create the User's Event and build its first Plan in the same transaction; 409 if they already have an Active Event (added in #21) |
| GET | `/events` | List my Events, newest first, each with its state (`active`, `event_day` or `past`; abandoned Events are `past`) (added in #22) |
| GET | `/events/{id}` | Event detail: state (`active`, `event_day` or `past`), days until the Event Day, Current Plan version; 404 for another User's Event (added in #21) |
| GET | `/events/{id}/plan` | The Current Plan: its version and Milestones in order (Scenario title and difficulty from the catalog), each with its Tasks grouped by Plan Day. A Task is `completed` once done, `missed` if still incomplete after its Plan Day ended in the User's timezone, else `pending`. Each Task also has `vocab_batch_size`: how many Vocab Items a Vocab Task teaches, null for Listen and Speak Tasks (added in #40). Superseded Plans aren't shown; 404 for another User's Event (added in #23) |
| GET | `/events/{id}/today` | What to do on the User's local today: "Day N of M" (Plan Day 1 is the Event's local creation date), days until the Event Day, state, Current Plan version and today's Tasks in order (id, Scenario title, kind, estimated minutes, `vocab_batch_size` (null except on Vocab Tasks, added in #40), status). On the Event Day or for a Past Event: 200 with no Plan Day and no Tasks; 404 for another User's Event (added in #24) |
| POST | `/events/{id}/abandon` | Abandon the Active Event, so another can be created; it stays readable as `past`. 409 if it's already past, 404 for another User's Event (added in #22) |
| GET | `/tasks/{id}/vocab` | A Vocab Task's batch: each Vocab Item's id, phrase and translation, in order. The first call fixes it (the Scenario's next available items for the Event's language and Level, in `position` order, up to `vocab_batch_size`); later calls return the same batch. Opening introduces nothing, and a Task that can no longer be completed (Missed, or a Past Event's) is read-only: it shows the batch fixed before, or an empty one. The batch is shorter, possibly empty, once the Scenario runs out. 409 `not_a_vocab_task` for Listen and Speak Tasks; 404 `task_not_found` for another User's Task, identical to an unknown ID (added in #42) |
| POST | `/tasks/{id}/complete` | Complete a Vocab Task: fixes its batch if needed, sets `completed_at` and introduces the batch, each item first due for Review the next day. Returns the Task's `status` and `items_introduced`. Idempotent: completing it again changes nothing and returns the same body, even once the Event is past. 409 `task_missed` for a Missed Task, `task_in_future` for a Task of a later Plan Day, `completed_by_answering` for a Listen Task (it completes by answering), `not_a_vocab_task` for a Speak Task, `event_already_past` for a Past Event's Task; 404 as above (added in #42) |
| GET | `/tasks/{id}/listen` | A Listen Task: its `status`, whether it's `answerable` now, and its Listen Dialogue (two `speakers`, the `lines`) with three Comprehension Questions, each with a `number` (1–3), `prompt`, three `options` and the `answer` given (`choice`, `correct`, `correct_option`; null until answered, so the correct option is never sent first). The first call fixes the dialogue: for now always the Scenario's hand-written fallback. Later calls return the same one. A Task that can no longer be completed is read-only and fixes nothing. 409 `not_a_listen_task` for Vocab and Speak Tasks; 404 as above (added in #67) |
| POST | `/tasks/{id}/answers` | Answer a Comprehension Question for good: body `{question, choice}`, both 1–3. Returns whether it was `correct`, the `correct_option` and the Task's `status`: the third answer, right or wrong, completes the Task in the same transaction. 409 `question_already_answered`, `task_missed`, `task_in_future`, `event_already_past`, `not_a_listen_task`; 422 for a question or choice out of range; 404 as above (added in #67) |
| POST | `/events/{id}/replan` | Re-plan after Missed Tasks (planned) |
| GET | `/events/{id}/reviews/due` | The Review Queue: Introduced Vocab Items due on the User's local today or earlier, oldest first, each with its vocab item id, phrase, translation, Scenario title and `due_on`, plus a `count`. Overdue items stay until graded (Reviews are never Missed). Empty on the Event Day and for a Past Event; 404 `event_not_found` for another User's Event, identical to an unknown ID (added in #43) |
| POST | `/events/{id}/reviews` | Grade a due Review: body `{vocab_item_id, grade}`, `grade` one of `again`, `hard`, `good`, `easy` (Grades 1, 3, 4, 5). Locks the item's Review State, applies `srs.py`, appends one row to the `reviews` log (never updated or deleted) and returns the new `due_on` (null once nothing more is due before the Event Day). 409 `review_not_due` if the item isn't in today's queue (so a second Grade the same day is refused), `event_day_reached` on the Event Day, `event_already_past` for a Past Event; 404 `vocab_item_not_introduced` for an item not Introduced for this Event, and as above for the Event (added in #43) |
| WS | `/roleplay/{milestone_id}` | Stream a voice roleplay session |
| GET | `/roleplay/sessions/{id}` | Transcript + feedback |
| GET | `/events/{id}/readiness` | Readiness report + daily trend |
| GET | `/admin/metrics` | LLM cost and voice latency (admin only) |

### Errors

Every 4xx and 5xx response has the same body (`ErrorResponse` in the OpenAPI schema):

```json
{
  "error": {
    "code": "validation_error",
    "message": "The request is invalid",
    "details": [
      {"field": "password", "code": "password_no_digit", "message": "Password must contain a digit (0-9)"}
    ],
    "request_id": "3f2a9c..."
  }
}
```

- `code` is machine-readable and stable, so clients branch on it rather than on `message`. Codes so far: `validation_error` (422), `email_taken` (409), `internal_error` (500), and the HTTP reason phrase in snake case for the rest (`not_found`, `method_not_allowed`).
- `details` lists one entry per problem; it's empty unless the error is about specific fields. For a 422, each entry names the `field` and a `code` such as `invalid_timezone`, `password_too_short`, `password_too_long`, `password_no_digit`, `password_no_special_character` or `password_too_common`.
- `request_id` matches the `X-Request-ID` header.
- Error bodies never echo submitted values, so a rejected password never comes back in a response.

The one exception is the 503 from `/health/ready`, which reports which dependency is down.

### Passwords

A new password must be 8–128 characters, with a digit (0–9) and a special character (anything that isn't a letter, digit or whitespace). It also can't be on the bundled list of common passwords, compared ignoring letter case; see `backend/app/data/README.md`. Passwords are stored only as argon2 hashes. The 128-character cap keeps every password under passlib's 4,096-byte hashing limit. A client can't choose its role: registration always creates a `user`.

### Request IDs and logs

Every HTTP response carries an `X-Request-ID` header. If the request sent one, it's echoed back, but only if it is 1–128 characters of `A–Z a–z 0–9 . _ -`. Anything else is replaced with a generated ID, since the ID is written to logs. Crashed requests get their 500 with the header too.

The API logs JSON lines to stdout. Each request writes one access line (`method`, `path`, `status`, `duration_ms`, `request_id`): INFO normally, ERROR with the traceback when the route crashed. Every other log line written during a request carries the same `request_id`. `LOG_LEVEL` (default `INFO`) sets the level, so `WARNING` and above keeps only the crash lines. Run uvicorn with `--no-access-log` so it doesn't write a second, plain-text access line.

---

## Data model

| Table | Key columns | Notes |
|---|---|---|
| User | id, email, password_hash, native_language, timezone, role, created_at | email stored lowercased and unique; password_hash is argon2; role = user, admin |
| Event | id, user_id, type, target_language, event_day, level, daily_budget, goals, abandoned_at, created_at | type = interview, relocation, speech; level = A1–C1; daily_budget = 15, 30, 45 minutes. No status column: active / event day / past is derived from `abandoned_at`, `event_day` and the User's local today (ADR 0005) |
| Plan | id, event_id, version, generated_at | (event_id, version) unique; the Current Plan is the highest version, and re-planning adds a version |
| Milestone | id, plan_id, scenario_slug, position, target_date | A Scenario from the in-code Scenario Catalog, by slug (no foreign key; a test checks stored slugs); title comes from the catalog |
| Task | id, milestone_id, date, kind, position, estimated_minutes, vocab_batch_size, vocab_batch_fixed_at, listen_dialogue_id, listen_dialogue_fixed_at, completed_at | kind = vocab, listen, speak; `date` is the Plan Day; `vocab_batch_size` is how many Vocab Items a Vocab Task teaches, set by the planner (required for vocab, null otherwise, by a check constraint); `listen_dialogue_id` is a Listen Task's Listen Dialogue, fixed on first open or answer and never changed (listen only, by a check constraint) |
| VocabItem | id, scenario_slug, language, level, item_key, phrase, translation, position, source, retired_at | Shared across Users. (scenario_slug, language, item_key) unique; `position` orders a Scenario's items, easiest and most essential first; level null = suits every Level; source = seed, generated. Seed items come from `app/data/seed-vocab-es.json`, upserted by `load_seed_vocab`; items that leave the file are retired, never deleted |
| VocabTaskItem | task_id, position, vocab_item_id | A Vocab Task's batch, written once when it's fixed (on first open or completion; `tasks.vocab_batch_fixed_at` records when, so an empty batch stays fixed too). (task_id, vocab_item_id) unique. Two of an Event's Tasks that can still be completed never share an item; a Missed Task's items go back into the pool |
| ListenDialogue | id, scenario_slug, language, level, source, speakers, lines, questions, created_at, retired_at | Shared across Users. source = fallback (level null: suits every Level) or generated (level set), by a check constraint; `speakers`, `lines` and `questions` are JSONB holding a validated `ListenDialogueContent`. Never edited in place: a changed or bad one is retired, and Listen Tasks keep theirs. At most one live fallback per (scenario_slug, language); fallbacks come from `app/data/fallback-listen-es.json` (added in #67). Generated ones are added by the worker, up to 3 per (scenario_slug, language, level); a Listen Task takes one its Event hasn't used, else the one it used longest ago, else the fallback (#69) |
| LlmCall | id, content_kind, scenario_slug, language, level, model, input_tokens, output_tokens, cost_usd, latency_ms, outcome, called_at | One row per content generation attempt. outcome = generated, fallback_after_failure, skipped_no_key, skipped_cap; a skipped attempt made no call (no model or latency, cost 0). The day's (UTC) total `cost_usd` is checked against `LLM_DAILY_BUDGET_USD` before each call (added in #69) |
| ListenAnswer | task_id, question, choice, is_correct, answered_at | A User's final answer to one Comprehension Question of a Listen Task; (task_id, question) is the key, so a question takes one answer. question and choice are 1–3 (added in #67) |
| RefreshToken | id, user_id, token_hash, family_id, created_at, last_used_at, expires_at, revoked_at, replaced_by_id | token_hash (unique) is the SHA-256 of a random 32-byte token; the token itself is never stored. A family is one session: every refresh adds its next token and revokes the last, linked by replaced_by_id. expires_at is 30 days after the token was issued, never past 90 days after the family's first login. Revoked rows are kept, to detect reuse (ADR 0007) |
| ReviewState | event_id, vocab_item_id, introduced_on, ease, interval_days, repetitions, lapses, due_on, reviewed_in_final_window | One row per Introduced Vocab Item per Event, (event_id, vocab_item_id) the key: nothing carries over between Events (ADR 0001). Created when a Vocab Task is completed and updated by `srs.py`; `due_on` is null once nothing more is scheduled before the Event Day |
| Review | id, event_id, vocab_item_id, plan_day, grade, reviewed_at | Append-only log: rows are never updated or deleted. `plan_day` is the User's local date; grade 0–5. (event_id, vocab_item_id) refers to its Review State. Written from #43 |
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

`services/srs.py` schedules each Introduced Vocab Item's Reviews. It's pure: it takes the Review State, the Grade, the Plan Day it was given on and the Event Day, and returns the new Review State.

- **SM-2.** Grades are 0–5, and the four buttons map to Again = 1, Hard = 3, Good = 4, Easy = 5. Ease starts at 2.5 and changes by the standard SM-2 rule, `ease += 0.1 − (5 − g)(0.08 + 0.02(5 − g))`, with a floor of 1.3. Passing Grades (3 or more) give intervals of 1 day, then 6, then `interval × ease`, rounded half up. Again resets repetitions, counts a lapse and gives 1 day. An item's first Review is the day after it's introduced.
- **Deadline compression.** `interval = min(SM-2 interval, max(1, ⌊days left before the Final Window ÷ 2⌋))`. The cap never increases as the Event Day nears, so with 9 days left before the Final Window no interval is longer than 4 days, and in the last 3 days before it every interval is 1 day.
- **Final Window clamp.** The Final Window is the two Plan Days before the Event Day. When an item not yet reviewed there would come due on or after Final Window day 1, it's assigned day 1 or day 2, picked from a SHA-256 hash of its id. That spreads the load over both days and gives the same answer in every process. It's never due later than its natural due date, meaning this Review's SM-2 interval before the cap. So a forgotten or brand-new item still comes back the next day, and only items SM-2 would leave longer wait for day 2. A Grade given in the Final Window marks the item reviewed there. After that, Again on day 1 brings it back on day 2, and otherwise nothing more is due. Nothing is ever due on or after the Event Day.
- **The guarantee.** A User who clears the Review Queue every day reviews every Introduced Vocab Item at least once in the Final Window, for any Plan dates and any Grades. `hypothesis` property tests check this in `tests/unit/test_srs_properties.py`, along with the cap, the Event Day bound, the ease floor and determinism.
- **The cap on new items (ADR 0006).** Every Introduced Vocab Item needs a Review in the Final Window, and those Reviews have to fit in the Daily Budget's Review allowance. So a Plan introduces at most what two Final Window days can review: 60, 120 or 180 items at 15, 30 or 45 minutes a day, at about 8 seconds per Review.

**Vocab batch sizes and the Final Window cap (ADR 0006).** The planner decides how many Vocab Items each Vocab Task teaches, as part of the schedule. Each batch is the Task's `estimated_minutes`, kept between 3 and 8. A Plan's total is capped at what the Final Window's two days of Review allowance can review at about 8 seconds a Review: 60 / 120 / 180 items for Daily Budgets of 15 / 30 / 45 minutes. When the cap binds, batches shrink evenly, in Plan order: each gets `min(minutes-based size, remaining cap ÷ remaining Vocab Tasks)`, rounded down and never below 1. So the 12-day demo (30 min) teaches 14 × 6 = 84 items uncapped, and a 60-day 45-minute Plan teaches exactly 180. Only the longest 15-minute Plans have more Vocab Tasks than their cap (up to 64 against 60); their latest surplus Vocab Tasks become Listen Tasks, so every batch keeps at least 1 item.

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

Entries marked _(planned)_ don't exist yet; they land with the roadmap weeks below.

```
docker-compose.yml         # web, api, worker, postgres, redis (run from the repo root)
.env.example               # every setting, with local placeholders; copy to .env
docker/postgres/init/      # first-run SQL: creates the cramplan_test database
docs/adr/                  # architecture decision records
GLOSSARY.md                # domain language
backend/
├── Dockerfile             # one image for the api and worker services
├── app/
│   ├── main.py            # app factory, lifespan, middleware, routers
│   ├── export_openapi.py  # prints the OpenAPI schema without a server, for the web client
│   ├── core/              # config (pydantic-settings), deps (incl. the clock), JSON logging, middleware
│   ├── db/                # async engine + sessionmaker, Redis client
│   ├── models/            # SQLAlchemy tables
│   ├── data/              # bundled data: common passwords, seed-vocab-es.json, fallback-listen-es.json
│   ├── schemas/           # Pydantic request/response models
│   ├── api/v1/            # health, auth, events, tasks; reviews, roleplay (planned)
│   ├── services/
│   │   ├── health.py      # readiness checks
│   │   ├── catalog.py     # the Scenario Catalog: fixed Scenarios per Event Type, pure
│   │   ├── content_generator.py  # the content generator seam (one method per content kind), pure
│   │   ├── content_generation.py # fill an Event's shared content pools, in the worker (ADR 0008)
│   │   ├── fallback_listen.py  # reads the fallback Listen Dialogues file and loads it
│   │   ├── events.py      # create/read Events and their Plans; one Active Event per User
│   │   ├── listen_content.py  # what a Listen Dialogue holds and the checks it passes, pure
│   │   ├── listen_tasks.py    # open a Listen Task (fix its dialogue) and answer its questions
│   │   ├── local_time.py  # UTC moment + IANA timezone → the User's local today, pure
│   │   ├── planner.py     # backward planning algorithm, pure Python
│   │   ├── seed_vocab.py  # reads the seed vocabulary file and upserts it into vocab_items
│   │   ├── refresh_tokens.py  # issue, rotate and revoke refresh tokens (ADR 0007)
│   │   ├── srs.py         # deadline-compressed SM-2 scheduler, pure Python
│   │   ├── tasks.py       # open a Vocab Task (fix its batch) and complete it (introduce it)
│   │   ├── llm.py         # plan/scenario generation (planned)
│   │   ├── voice.py       # STT/TTS pipeline (planned)
│   │   └── scoring.py     # readiness score (planned)
│   └── workers/
│       ├── tasks.py       # arq jobs (generate_event_content) and WorkerSettings; report jobs (planned)
│       └── queue.py       # the job queue routes use to queue jobs (`Depends(get_job_queue)`)
├── alembic/
├── tests/
│   ├── unit/              # pure logic: local time, srs, planner, scoring (no DB)
│   ├── api/               # endpoint tests with dependency overrides
│   ├── db/                # transactional test session, seed vocabulary and fallback loaders
│   └── workers/           # the content job with a fake generator; arq round-trips against test Redis
└── pyproject.toml
web/                       # Next.js (App Router) + TypeScript + Tailwind PWA, http://localhost:3000
├── Dockerfile             # standalone Next.js server for the web service
├── e2e/                   # the Playwright test, onboarding → first Task (playwright.config.ts)
├── next.config.ts         # standalone output, frame/nosniff/referrer headers
├── src/
│   ├── proxy.ts           # nonce CSP, Origin check (CSRF), page session redirects
│   ├── app/
│   │   ├── api/session/   # login, register, refresh, logout: set/clear the session cookies
│   │   ├── api/v1/        # forwards /api/v1/* to FastAPI with the access cookie as Bearer
│   │   ├── login/, register/  # the auth screens
│   │   └── …              # pages, web manifest, icons
│   └── lib/
│       ├── session/       # cookies, origin, safe `next` paths, refresh-token rotation
│       └── api/
│           ├── openapi.json   # generated: the API's schema, from app.export_openapi
│           ├── schema.ts      # generated: openapi-typescript types (never edit)
│           ├── client.ts      # openapi-fetch client for FastAPI, server-side only (API_URL)
│           ├── server.ts      # the same, as the logged-in User, for Server Components
│           └── browser.ts     # same-origin client with silent refresh, for browser code
└── public/icons/          # install icons for the manifest
```

---

## Roadmap

Part-time build (~10–15 h/week). Each week ends with something running and tested.

- [x] **Week 1 — Foundation:** uv/ruff/mypy/pre-commit, Docker Compose, config + async DB + Alembic, User + JWT auth, GitHub Actions CI
- [x] **Week 2 — Events & template planner:** Event/Plan/Milestone/Task models, Event CRUD, template-based `planner.py`, `GET /events/{id}/today`
- [x] **Week 3 — Spaced repetition:** VocabItem/ReviewState, `srs.py` + property tests, review endpoints, Spanish seed vocab, Next.js onboarding + daily practice
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
