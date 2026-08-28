# 📝 Blogging Agent

An AI agent that researches the web and writes **accurate, citable technical blog posts** from a single topic prompt. Built on [LangGraph](https://langchain-ai.github.io/langgraph/), it orchestrates a multi-node pipeline — generate search queries → research the web → plan an outline → **pause for human review when evidence is thin** → write sections in parallel → synthesize a final Markdown post.

The product has a **FastAPI** backend exposing the agent over HTTP, durable **PostgreSQL**-backed job tracking and checkpointing, a **crash-resilient job runtime** (heartbeat leases + background sweeper), and a **React + Vite** client with live progress tracking and a human-in-the-loop review panel.

---

## 🚧 Active Development

I build this in versioned milestones. Each one is a self-contained, shipped increment — the goal is to grow it like a real product rather than a one-off script.

| Version        | Milestone                                                                                                                                                                             | Status     |
| -------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------- |
| **v1.0** | Core agent pipeline (queries → research → plan → parallel writing → synthesis), FastAPI API, React client, Postgres checkpointing & resumable jobs                                | ✅ Shipped |
| **v1.1** | **Reliability layer** — per-job **heartbeat leases** and a background **sweeper thread** that reclaims crash-orphaned jobs; multi-instance safe                    | ✅ Shipped |
| **v1.2** | **Human-in-the-loop (HITL) research review gate** — the graph pauses after planning when coverage is weak and lets the user *proceed* or *re-research* (bounded loop-back) | ✅ Shipped |
|                |                                                                                                                                                                                       |            |

---

## 🔄 CI / CD pipeline integrated with branch specific rulesets

Two GitHub Actions workflows automate testing and deployment

```mermaid
flowchart TD
    DEV([Developer pushes\nto feature branch]) --> PR[Opens Pull Request → main]

    PR --> CHK{Server/ or tests/\nor .github/workflows/\nchanged?}
    CHK -- No --> SKIP[Steps skipped\n✅ PR can be reviewed]
    CHK -- Yes --> TESTS[pytest — full suite\nunit + integration\nfully mocked · no DB needed]

    TESTS -- All pass --> READY[✅ PR ready to merge]
    TESTS -- Any fail --> BLOCKED[❌ PR blocked\nresults posted to\nActions summary]

    READY --> MERGE([Merge to main])

    MERGE --> DCHK{Dockerfile or\nServer/ changed?}
    DCHK -- No --> NOOP[No deploy triggered]
    DCHK -- Yes --> OIDC[Authenticate to AWS\nvia GitHub OIDC\nno long-lived keys]
    OIDC --> ECR[Login to Amazon ECR]
    ECR --> BUILD[Build Docker image\nmulti-stage · python:3.12-slim]
    BUILD --> PUSH[Push to ECR\n:latest + :git-sha]
```

| Workflow         | Trigger                                                                            | What it does                                                                                                                                        |
| ---------------- | ---------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------- |
| `pr-tests.yml` | PR to`main` (only if `Server/`, `tests/`, or `.github/workflows/` changed) | Runs the full pytest suite; posts results to the Actions summary; blocks merge on failure                                                           |
| `deploy.yml`   | Push to`main` (only if `Dockerfile` or `Server/` changed)                    | Builds the multi-stage Docker image and pushes it to Amazon ECR tagged`:latest` and `:<git-sha>` via GitHub OIDC. No long-lived AWS credentials |

**Required GitHub secrets:** `AWS_ACCOUNT_ID`, `AWS_REGION`, `ECR_REPOSITORY_NAME`

---

## ✨ Features

- **Topic → published-ready blog** — give it a topic, get back a structured Markdown post.
- **Evidence-first writing** — a research stage gathers sources via [Tavily](https://tavily.com/) search, and the writer is held to a tiered citation policy:
  - **Tier 1 (citation required):** framework/API/product claims, deployment steps, benchmarks, pricing — every claim gets an inline link to a real source, or it isn't stated as fact.
  - **Tier 2 (internal knowledge allowed):** general engineering patterns, clearly labelled as illustrative.
- **Honest coverage signalling** — the plan classifies evidence as `sufficient | partial | insufficient` and prepends a reader-facing **research note** banner when sources are thin, so the blog never oversells its depth.
- **Human-in-the-loop review gate** *(v1.2)* — when coverage is weak, the agent **pauses before spending compute on drafting** and shows the user the planned title, outline, and sources. The user can **proceed with limited research** or **re-research** (loop back to generate fresh queries), bounded by a configurable retry cap. Paused jobs wait durably and never get swept as crashed.
- **Parallel section writing** — the orchestrator splits the blog into 1–4 sections and `Send`s them to worker nodes that run concurrently (LangGraph map-reduce / fan-out).
- **Crash-resilient job runtime** *(v1.1)* — every node's output is checkpointed to Postgres, and each running job holds a **lease** renewed by a background **heartbeat thread**. A **sweeper thread** reclaims jobs whose lease expired (owner crashed) — resumable ones become `HALTED & recoverable`, the rest `FAILED`. Safe to run across multiple instances.
- **Reliability built in** — transient-failure `RetryPolicy` on every node, graceful handling of empty research, and parallel web search with per-query failure isolation.
- **Live progress UI** — the React client polls job status and renders a stage-by-stage stepper (queued → generating queries → researching → planning → *review pause* → writing → synthesizing → complete), plus a **"Needs input"** inbox tab surfacing paused jobs.
- **Job dashboard** — list, view, retry, and respond to past jobs; read generated blogs rendered as Markdown.

---

## 🧠 Architecture & Workflow

The agent is a `StateGraph` of **six nodes** plus a conditional fan-out edge and a human-in-the-loop gate. Each node reads and writes a shared `BlogState`.

```mermaid
flowchart TD
    START([START]) --> QG[queries_generator<br/>LLM picks 3–5 search queries]
    QG --> RN[research_node<br/>Tavily web search + dedup + synthesize evidence]
    RN --> ORC[orchestrator<br/>LLM builds the outline / Plan<br/>scores evidence coverage]
    ORC --> RG{review_gate<br/>coverage weak?}
    RG -->|sufficient · or retry cap reached| FO
    RG -. interrupt: pause for human .-> HITL[[👤 Human decision<br/>proceed / re-research]]
    HITL -->|proceed| FO
    HITL -->|redo → fresh queries| QG
    FO[[fanout: Send one task per section]] -.-> W1[worker<br/>writes section 1]
    FO -.-> W2[worker<br/>writes section 2]
    FO -.-> W3[worker<br/>writes section N]
    W1 --> SYN[synthesizer<br/>stitch sections + research banner<br/>write final .md]
    W2 --> SYN
    W3 --> SYN
    SYN --> END([END])
```

### Node responsibilities

| Node                       | Role                                                                                                                                                                                                                                                                                 |
| -------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `queries_generator`      | Turns the topic into 3–5 scoped, high-signal search queries aimed at official docs, release notes, and production guides.                                                                                                                                                           |
| `research_node`          | Runs all queries against Tavily in parallel (`ThreadPoolExecutor`), deduplicates by URL, and uses the LLM to normalize hits into a structured `EvidencePack` (no invented facts). Handles the empty-research case gracefully.                                                    |
| `orchestrator`           | Reads the evidence, assigns a coverage rating (`sufficient`/`partial`/`insufficient`), and produces a `Plan` — title, audience, research note, and 1–4 section `Task`s with typed bullets and target word counts.                                                        |
| `review_gate` *(v1.2)* | Inspects the plan's coverage. If`sufficient` (or the re-research cap is reached) it proceeds silently; otherwise it `interrupt()`s the graph for a human decision. `proceed` → fan out to workers; `redo` → loop back to `queries_generator` for another research round. |
| `fanout`                 | A conditional edge that emits a LangGraph`Send` per task, fanning the sections out to parallel workers.                                                                                                                                                                            |
| `worker`                 | Writes a single section in Markdown, enforcing the tiered citation policy and the bullet types from the plan. Sections accumulate via a reducer (`operator.add`).                                                                                                                  |
| `synthesizer`            | Joins all sections, prepends the research-coverage banner when needed, writes the final`.md` to `Server/blogs/`, and returns the full blog.                                                                                                                                      |

### State shape

`BlogState` carries: `topic`, `search_queries`, `evidence` (EvidencePack), `plan` (Plan), `sections` (accumulating list), `final_blog`, and the HITL fields `research_attempts` (re-research counter, enforces the cap) and `research_decision` (routes the gate).

---

## ⚙️ Reliability & Runtime Architecture *(v1.1)*

Jobs run asynchronously inside the FastAPI process and must survive crashes, restarts, and long-blocking LLM/search calls. The runtime combines a durable checkpointer with a **lease + heartbeat + sweeper** reconciliation loop.

```mermaid
flowchart LR
    subgraph Client["React + Vite client"]
        UI["Polls GET /jobs/:id<br/>every 3s"]
    end

    subgraph API["FastAPI process · instance_id"]
        EP["HTTP endpoints"]
        EX["ThreadPoolExecutor<br/>runs the graph per job"]
        HB["Heartbeat thread (per running job)<br/>renews lease every ~5s"]
        SW["Sweeper thread<br/>every ~10s reclaims<br/>expired-lease jobs"]
    end

    subgraph DB["PostgreSQL"]
        JT[("blog_jobs<br/>status · stage · owner_id · heartbeat_at")]
        CP[("LangGraph checkpoints<br/>keyed by thread_id = job_id")]
    end

    UI -- "POST /jobs" --> EP
    EP -- "submit(job)" --> EX
    EX -- "stream graph · checkpoint each node" --> CP
    EX -- "advance stage / status" --> JT
    HB -- "heartbeat_at = NOW()" --> JT
    SW -- "lease expired → HALTED / FAILED" --> JT
    UI -- "poll status & stage" --> JT
```

**How it stays correct:**

- **Checkpointer** — a `PostgresSaver` persists graph state after every node, keyed by `thread_id` (= job id). Any resume (`retry`, or a HITL `decision`) continues from the last checkpoint instead of restarting.
- **Lease + heartbeat** — a worker *claims* a job (stamps `owner_id`) and a companion **daemon heartbeat thread** bumps `heartbeat_at` on a fixed cadence. This is decoupled from the worker because a single node can block for minutes, so the worker can't renew its own lease inline.
- **Sweeper** — a background thread periodically reclaims `IN-PROGRESS` jobs whose lease has expired (a crashed owner). Research-complete jobs become `HALTED & recoverable`; earlier failures become `FAILED`. Because it only ever touches stale `IN-PROGRESS` rows, a live owner keeping its heartbeat fresh is never disturbed — making reconciliation **safe across multiple instances**.
- **Graceful shutdown** — on shutdown an instance reclaims its own in-flight jobs immediately (rather than waiting a full lease), so a restart recovers them right away.

### Job lifecycle & statuses

The `blog_jobs` table tracks each job's `status`, fine-grained `stage`, `recoverable` flag, `research_done` flag, and lease columns (`owner_id`, `heartbeat_at`).

| Status                        | Meaning                                                                                                                                            |
| ----------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------- |
| `IN-PROGRESS`               | Actively running (or claimed and about to run).                                                                                                    |
| `AWAITING_INPUT` *(v1.2)* | Paused at the review gate, waiting on a human decision.**Excluded from the sweeper** so it can wait indefinitely; durable in the checkpoint. |
| `COMPLETE`                  | Finished; final Markdown written and path recorded.                                                                                                |
| `HALTED`                    | Interrupted after research;**recoverable** — resumable from checkpoint via `retry`.                                                       |
| `FAILED`                    | Failed before research completed (nothing useful to resume); checkpoint cleaned up.                                                                |

---

## 🔌 API Endpoints

| Method   | Path                                   | Description                                                                                                        |
| -------- | -------------------------------------- | ------------------------------------------------------------------------------------------------------------------ |
| `GET`  | `/health`                            | Service + database readiness check.                                                                                |
| `POST` | `/jobs`                              | Start a blog job. Body:`{ "topic": "..." }`. Returns a job id (202).                                             |
| `GET`  | `/jobs`                              | List jobs newest-first (`limit`, `offset`).                                                                    |
| `GET`  | `/jobs/{job_id}`                     | Poll a job's status and current stage.                                                                             |
| `GET`  | `/jobs/{job_id}/blog`                | Fetch the generated Markdown (409 if not ready).                                                                   |
| `POST` | `/jobs/{job_id}/retry`               | Resume a halted, recoverable job from its last checkpoint.                                                         |
| `GET`  | `/jobs/{job_id}/review` *(v1.2)*   | Fetch the pending research-review for a paused job — coverage, planned title/outline, research note, and sources. |
| `POST` | `/jobs/{job_id}/decision` *(v1.2)* | Resume a paused job with the human decision. Body: `{ "decision": "proceed"                                        |

---

## 🛠️ Tech Stack & Tools

**Agent / Backend**

- **Python 3.11+**
- **LangGraph** — agent orchestration (`StateGraph`, `Send` fan-out, `RetryPolicy`, `interrupt()` / `Command` HITL, checkpointing)
- **LangChain** + **langchain-ollama** — LLM integration
- **Ollama** — local LLM runtime (model configurable via env)
- **langchain-tavily** — web search / research
- **FastAPI** + **Uvicorn** — HTTP API
- **PostgreSQL** via **psycopg 3** + **psycopg-pool** — job store & LangGraph checkpoint backend
- **Pydantic v2** — structured LLM outputs (`Plan`, `EvidencePack`, etc.) and API schemas
- **threading** — background heartbeat & sweeper daemons, `ThreadPoolExecutor` job runner

**Frontend**

- **React 18** + **Vite**
- **react-markdown** + **remark-gfm** — render generated blogs

---

## 🚀 Getting Started

### Prerequisites

- **Python 3.11+** and [**uv**](https://docs.astral.sh/uv/) (package/dependency manager)
- **Node.js 18+** and npm (for the client)
- **PostgreSQL** (running and reachable)
- **[Ollama](https://ollama.com/)** running locally with a pulled model (e.g. `ollama pull llama3.1`)
- A **[Tavily API key](https://tavily.com/)** for web search

### 1. Clone & configure environment

Create a `.env` file in the project root:

```env
# LLM (Ollama)
OLLAMA_URL=http://localhost:11434
LLM_MODEL=llama3.1

# Web search
TAVILY_API_KEY=tvly-your-key-here

# PostgreSQL
DATABASE_URI=postgresql://user:password@localhost:5432/blog_agent
POOL_MIN_SIZE=1
POOL_MAX_SIZE=10

# API server (optional — defaults shown)
API_HOST=0.0.0.0
API_PORT=8000
API_MAX_WORKERS=4
CORS_ORIGINS=http://localhost:3000,http://localhost:5173

# Reliability & HITL tuning (optional — defaults shown)
JOB_HEARTBEAT_INTERVAL_SECONDS=5   # how often a running job renews its lease
JOB_LEASE_TIMEOUT_SECONDS=20       # lease age before a job is considered orphaned
JOB_SWEEP_INTERVAL_SECONDS=10      # how often the sweeper scans for orphans
RESEARCH_RETRY_CAP=2               # max user-triggered re-research rounds before auto-proceed
```

> The Postgres tables and LangGraph checkpoint tables are created automatically on startup — no manual migration needed. Status-constraint and lease-column migrations are applied idempotently, so existing databases upgrade in place.

### 2. Install backend dependencies

```bash
uv sync
```

### 3. Start Ollama & PostgreSQL

Make sure your Ollama server is running and the model from `LLM_MODEL` is pulled, and that PostgreSQL is up and reachable at `DATABASE_URI`.

### 4. Run the API server

```bash
uv run uvicorn Server.api.app:app --reload
```

The API is now available at `http://localhost:8000` (interactive docs at `http://localhost:8000/docs`).

> **One-off / CLI run (no server):** `uv run python -m Server.main` generates a single blog from a hard-coded topic — handy for quick testing.

### 5. Run the React client

```bash
cd client
npm install
npm run dev
```

Open the printed URL (default `http://localhost:5173`), enter a topic, and watch the agent work through each stage. If research is thin, the client surfaces a **review panel** (and a **"Needs input"** tab) where you decide whether to proceed or re-research. Generated blogs are also written to `Server/blogs/`.

---

## 🗺️ Future Improvements

Planned and explored enhancements (tracked in `Server/thinking_to_add_improvements.txt`):

- **LLM-as-a-judge** *(v1.3, next)* — a quality-review node that evaluates each section produced by the workers and requests rewrites when standards aren't met.
- **Richer synthesizer prompt** *(v1.4)* — automatically generate an introduction, prerequisites, and conclusion to wrap the body sections into a complete post.

✅ **Already shipped from the original wishlist:** reliability/failure handling across the pipeline (retries, halt-and-resume), graceful handling of empty research, crash-safe job leases + sweeper *(v1.1)*, and a research sufficiency + human-in-the-loop review gate *(v1.2)*.

---

## 📂 Project Structure

```
blog_agent/
├── Server/
│   ├── api/                # FastAPI app + request/response schemas
│   ├── nodes/              # LangGraph nodes (queries, research, orchestrator, review_gate, fanout, worker, synthesizer)
│   ├── persistence/        # Postgres pool, checkpointer, job repository (lease/sweeper), schema + migrations
│   ├── services/           # BlogJobService — create / execute / retry / decision / read jobs; heartbeat & reconciliation
│   ├── blogs/              # Generated Markdown blogs
│   ├── graph.py            # Builds & compiles the StateGraph (incl. review gate + loop-back edge)
│   ├── state.py            # BlogState + Pydantic models (Plan, Task, EvidencePack…)
│   ├── model.py            # LLM (ChatOllama) setup
│   ├── config.py           # Env-driven configuration (lease/heartbeat/sweeper, retry cap)
│   └── main.py             # CLI entry point for a one-off run
└── client/                 # React + Vite frontend
    └── src/                # App, components (ProgressView review panel, Sidebar tabs), API client, stages
```
