# CLAUDE.md

## Overview

A LangGraph agent that turns a topic into a researched, citable Markdown blog post. The system has a FastAPI backend with PostgreSQL-backed durable jobs and a React + Vite frontend. The agent graph handles research, planning, parallel section writing, and a human-in-the-loop review gate before finalizing the blog.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Agent framework | LangGraph |
| Backend API | FastAPI |
| LLM runtime | Ollama (local) |
| Web search / research | Tavily |
| Database | PostgreSQL (via `psycopg2`) |
| Frontend | React + Vite |
| Backend package manager | `uv` |
| Frontend package manager | `npm` |

---

## Commands

**Backend** (run from repo root — imports are absolute `from Server.*`):

```bash
uv sync                                         # install deps
uv run uvicorn Server.api.app:app --reload      # API at http://localhost:8000
uv run python -m Server.main                    # one-off CLI run
```

**Frontend:**

```bash
cd client && npm install
npm run dev        # dev server at http://localhost:5173
npm run build      # production build (also catches JSX/import errors)
```

**Quick validation:**

```bash
python -m py_compile Server/services/blog_job_service.py Server/graph.py
python -c "from langgraph.checkpoint.memory import MemorySaver; from Server.graph import build_blog_agent; build_blog_agent(MemorySaver())"
python -c "import Server.api.app; print('ok')"
```

**Running tests:**

```bash
# Backend (install once: uv sync --group test)
uv run pytest tests/ -v
uv run pytest tests/unit/ -v          # unit only
uv run pytest tests/integration/ -v   # integration only
uv run pytest tests/ --cov=Server --cov-report=term-missing

# Frontend (install once: cd client && npm install)
cd client && npm test
cd client && npm run test:watch
```

**Required `.env`:** `DATABASE_URI`, `OLLAMA_URL`, `LLM_MODEL`, `TAVILY_API_KEY`

---

## Project Structure

```
blog_agent/
├── Server/
│   ├── api/
│   │   ├── app.py              # FastAPI routes
│   │   └── schemas.py          # Request/response models
│   ├── nodes/
│   │   ├── queries_generator.py
│   │   ├── research.py
│   │   ├── orchestrator.py
│   │   ├── review_gate.py
│   │   ├── fanout.py
│   │   ├── worker.py
│   │   └── synthesizer.py
│   ├── persistence/
│   │   ├── database.py         # Schema + migrations (run on startup)
│   │   ├── checkpointer.py     # PostgresSaver setup
│   │   ├── job_repository.py   # DB reads/writes for blog_jobs
│   │   └── schema.sql
│   ├── services/
│   │   └── blog_job_service.py # Job lifecycle: execute, retry, decision
│   ├── graph.py                # LangGraph graph definition
│   ├── state.py                # BlogState TypedDict + Plan model
│   ├── model.py                # Ollama LLM client
│   └── config.py               # Env config, UTF-8 stdout fix
├── client/
│   └── src/
│       ├── components/         # BlogForm, BlogView, ProgressView, Sidebar, Toasts
│       ├── App.jsx
│       ├── api.js              # HTTP polling client
│       └── stages.js
└── pyproject.toml
```

---

## Architecture

`thread_id == job_id` — a single key ties the LangGraph checkpoint thread to the `blog_jobs` DB row. This is what makes durability, retry, and HITL resume work.

**Graph flow:**
`START → queries_generator → research_node → orchestrator → review_gate → (fanout: worker×N) → synthesizer → END`

- `review_gate`: pauses via `interrupt()` on weak research coverage; resumes with `Command(resume="proceed"|"redo")`.
- Workers fan out via `Send` (one per plan section), results accumulate via `operator.add` reducer.
- `_execute_graph` in `BlogJobService` is the single streaming loop for all three entry points: fresh run, retry, and decision resume.

**Job statuses:** `IN-PROGRESS` → `COMPLETE` | `HALTED` (retry-able) | `FAILED` | `AWAITING_INPUT` (at review gate)

**Reliability:** background heartbeat thread keeps the lease alive while nodes run; sweeper thread reclaims expired `IN-PROGRESS` jobs. The sweeper only ever touches `IN-PROGRESS` rows — `AWAITING_INPUT` must never be set to `IN-PROGRESS`.

---

## Coding Standards

### Import hygiene
Only import what is actually used in the file. Do not pull in entire modules or libraries speculatively. Unused imports must be removed.

### Logging
Add `logging` to every backend module. Use named loggers (`logger = logging.getLogger(__name__)`). Log meaningful events: job start/end, node entry/exit, errors with context. This is the primary debugging and monitoring tool since there is no test suite.

### Naming
Use names that describe intent, not implementation. Functions should read like actions (`fetch_research_results`, `mark_job_complete`). Variables should describe what they hold (`evidence_coverage`, `job_id`, `section_drafts`). Avoid single-letter names, abbreviations, or generic names like `data`, `result`, `obj`.

### Backward compatibility
When refactoring or adding a feature, never silently drop existing logic. If old code must move or be restructured, carry it forward explicitly — do not assume it is no longer needed. Every existing feature must continue to work exactly as before after a change. If removing something is intentional, confirm with the user first.

### Test while you build
Every feature or change ships with the corresponding test update in the same session. Minimum bar per feature type:

| Changed file | Test file to create/update |
|---|---|
| `Server/nodes/<name>.py` | `tests/unit/test_<name>.py` |
| `Server/api/app.py` (route) | `tests/integration/test_api_jobs.py` |
| `Server/services/blog_job_service.py` | `tests/unit/test_blog_job_service.py` |
| `Server/persistence/job_repository.py` | `tests/unit/test_job_repository.py` |
| `Server/api/schemas.py` | `tests/unit/test_schemas.py` |
| `client/src/components/<Name>.jsx` | `client/src/__tests__/<Name>.test.jsx` |
| `client/src/api.js` | `client/src/__tests__/api.test.js` |

- **New graph node**: unit-test pure helpers + one new flow in `tests/integration/test_graph_flow.py`
- **New API route**: service unit test + HTTP integration test + `api.test.js` entry
- **New status or stage**: repository test + service lifecycle test + sweeper invariant test

---

## Key Invariants

- **Sweeper only touches `IN-PROGRESS`.** New paused/waiting statuses must never use `IN-PROGRESS`.
- **Adding a job status** requires updating both the `CHECK` constraint in `BLOG_JOBS_SCHEMA` and `BLOG_JOBS_STATUS_MIGRATION` in `Server/persistence/database.py`.
- **`Plan` may be a Pydantic object or a plain dict** after checkpoint reload — use the `_attr` / `_task_count_from_plan` helpers.
- **Resume via `Command(resume=...)` or `None`, never `update_state`.**
- Run all backend commands from repo root (absolute `Server.*` imports).
- `pyproject.toml` lists `streamlit`, `torch`, `transformers` — these are not used. The real stack is FastAPI + LangGraph + Ollama + Tavily + Postgres.
