# 📝 Blogging Agent

An AI agent that researches the web and writes **accurate, citable technical blog posts** from a single topic prompt. Built on [LangGraph](https://langchain-ai.github.io/langgraph/), it orchestrates a multi-node pipeline — generate search queries → research the web → plan an outline → write sections in parallel → synthesize a final Markdown post.

The project ships as a full V1 product: a **FastAPI** backend exposing the agent over HTTP, durable **PostgreSQL**-backed job tracking and checkpointing, and a **React + Vite** client with live progress tracking.

---

## ✨ Features

- **Topic → published-ready blog** — give it a topic, get back a structured Markdown post.
- **Evidence-first writing** — a research stage gathers sources via [Tavily](https://tavily.com/) search, and the writer is held to a tiered citation policy:
  - **Tier 1 (citation required):** framework/API/product claims, deployment steps, benchmarks, pricing — every claim gets an inline link to a real source, or it isn't stated as fact.
  - **Tier 2 (internal knowledge allowed):** general engineering patterns, clearly labelled as illustrative.
- **Honest coverage signalling** — the plan classifies evidence as `sufficient | partial | insufficient` and prepends a reader-facing **research note** banner when sources are thin, so the blog never oversells its depth.
- **Parallel section writing** — the orchestrator splits the blog into 1–4 sections and `Send`s them to worker nodes that run concurrently (LangGraph map-reduce / fan-out).
- **Durable & crash-resilient** — every node's output is checkpointed to Postgres. A job that crashes mid-run can be **resumed from its last checkpoint** instead of starting over.
- **Reliability built in** — transient-failure `RetryPolicy` on every node, graceful handling of empty research, and parallel web search with per-query failure isolation.
- **Live progress UI** — the React client polls job status and renders a stage-by-stage stepper (queued → generating queries → researching → planning → writing → synthesizing → complete).
- **Job dashboard** — list, view, and retry past jobs; read generated blogs rendered as Markdown.

---

## 🧠 Architecture & Workflow

The agent is a `StateGraph` of five nodes plus a conditional fan-out edge. Each node reads and writes a shared `BlogState`.

```mermaid
flowchart TD
    START([START]) --> QG[queries_generator<br/>LLM picks 3–5 search queries]
    QG --> RN[research_node<br/>Tavily web search + dedup + synthesize evidence]
    RN --> ORC[orchestrator<br/>LLM builds the outline / Plan<br/>scores evidence coverage]
    ORC -.->|fanout: Send one task per section| W1[worker<br/>writes section 1]
    ORC -.-> W2[worker<br/>writes section 2]
    ORC -.-> W3[worker<br/>writes section N]
    W1 --> SYN[synthesizer<br/>stitch sections + research banner<br/>write final .md]
    W2 --> SYN
    W3 --> SYN
    SYN --> END([END])
```

### Node responsibilities

| Node | Role |
|------|------|
| `queries_generator` | Turns the topic into 3–5 scoped, high-signal search queries aimed at official docs, release notes, and production guides. |
| `research_node` | Runs all queries against Tavily in parallel (`ThreadPoolExecutor`), deduplicates by URL, and uses the LLM to normalize hits into a structured `EvidencePack` (no invented facts). Handles the empty-research case gracefully. |
| `orchestrator` | Reads the evidence, assigns a coverage rating (`sufficient`/`partial`/`insufficient`), and produces a `Plan` — title, audience, research note, and 1–4 section `Task`s with typed bullets and target word counts. |
| `fanout` | A conditional edge that emits a LangGraph `Send` per task, fanning the sections out to parallel workers. |
| `worker` | Writes a single section in Markdown, enforcing the tiered citation policy and the bullet types from the plan. Sections accumulate via a reducer (`operator.add`). |
| `synthesizer` | Joins all sections, prepends the research-coverage banner when needed, writes the final `.md` to `Server/blogs/`, and returns the full blog. |

### State shape

`BlogState` carries: `topic`, `search_queries`, `evidence` (EvidencePack), `plan` (Plan), `sections` (accumulating list), and `final_blog`.

### Durability & job lifecycle

- A **PostgresSaver checkpointer** persists graph state after every node, keyed by `thread_id` (= job id).
- A `blog_jobs` table tracks each job's `status` (`IN-PROGRESS` / `COMPLETE` / `HALTED`), fine-grained `stage`, `recoverable` flag, and `research_done` flag.
- On failure: if research already completed, the job is marked **HALTED & recoverable** so it can resume from the checkpoint; otherwise the partial job and checkpoint are cleaned up.
- The FastAPI layer runs jobs on a background `ThreadPoolExecutor` and returns a job id immediately for polling.

---

## 🛠️ Tech Stack & Tools

**Agent / Backend**
- **Python 3.11+**
- **LangGraph** — agent orchestration (`StateGraph`, `Send` fan-out, `RetryPolicy`, checkpointing)
- **LangChain** + **langchain-ollama** — LLM integration
- **Ollama** — local LLM runtime (model configurable via env)
- **langchain-tavily** — web search / research
- **FastAPI** + **Uvicorn** — HTTP API
- **PostgreSQL** via **psycopg 3** + **psycopg-pool** — job store & LangGraph checkpoint backend
- **Pydantic v2** — structured LLM outputs (`Plan`, `EvidencePack`, etc.) and API schemas

**Frontend**
- **React 18** + **Vite**
- **react-markdown** + **remark-gfm** — render generated blogs

---

## 🔌 API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Service + database readiness check. |
| `POST` | `/jobs` | Start a blog job. Body: `{ "topic": "..." }`. Returns a job id (202). |
| `GET` | `/jobs` | List jobs newest-first (`limit`, `offset`). |
| `GET` | `/jobs/{job_id}` | Poll a job's status and current stage. |
| `GET` | `/jobs/{job_id}/blog` | Fetch the generated Markdown (409 if not ready). |
| `POST` | `/jobs/{job_id}/retry` | Resume a halted, recoverable job from its last checkpoint. |

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
```

> The Postgres tables and LangGraph checkpoint tables are created automatically on startup — no manual migration needed.

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

Open the printed URL (default `http://localhost:5173`), enter a topic, and watch the agent work through each stage. Generated blogs are also written to `Server/blogs/`.

---

## 🗺️ Future Improvements

Planned and explored enhancements (tracked in `Server/thinking_to_add_improvements.txt`):

- **Research sufficiency loop** — an agentic loop that judges whether enough information has been gathered before writing, and runs additional research rounds until coverage is sufficient.
- **LLM-as-a-judge** — a quality-review node that evaluates each section produced by the workers and requests rewrites when standards aren't met.
- **Human-in-the-loop (HITL)** — pause for human approval/edits of the outline (or sections) before continuing generation.
- **Richer synthesizer prompt** — automatically generate an introduction, prerequisites, and conclusion to wrap the body sections into a complete post.

✅ Already shipped from the original wishlist: reliability/failure handling across the pipeline (retries, halt-and-resume), and graceful handling of empty research results.

---

## 📂 Project Structure

```
blog_agent/
├── Server/
│   ├── api/                # FastAPI app + request/response schemas
│   ├── nodes/              # LangGraph nodes (queries, research, orchestrator, fanout, worker, synthesizer)
│   ├── persistence/        # Postgres pool, checkpointer, job repository, schema
│   ├── services/           # BlogJobService — create / execute / retry / read jobs
│   ├── blogs/              # Generated Markdown blogs
│   ├── graph.py            # Builds & compiles the StateGraph
│   ├── state.py            # BlogState + Pydantic models (Plan, Task, EvidencePack…)
│   ├── model.py            # LLM (ChatOllama) setup
│   ├── config.py           # Env-driven configuration
│   └── main.py             # CLI entry point for a one-off run
└── client/                 # React + Vite frontend
    └── src/                # App, components, API client, stages
```
