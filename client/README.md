# Blog Studio — React client

A single-page React app for the LangGraph blog agent. Create a topic, watch the
agent research → plan → write in real time, browse your library, and retry any
runs that were interrupted.

## Prerequisites

- Node.js 18+
- The FastAPI server running (default `http://localhost:8000`). Its CORS config
  already allows this app's dev origin (`http://localhost:5173`).

## Setup

```bash
cd client
npm install
npm run dev        # http://localhost:5173
```

Point it at a different server by editing `.env`:

```
VITE_API_URL=http://localhost:8000
```

## Build

```bash
npm run build      # outputs to client/dist
npm run preview    # serve the production build locally
```

## What it does

- **Create:** topic field with live word/character counter and the same
  10–2000 char validation the server enforces.
- **Live progress:** polls `GET /jobs/{id}` every 3s and animates the current
  stage (queries → research → planning → writing → synthesizing → complete).
- **Library sidebar:** lists past blogs; click one to read the rendered Markdown.
- **Recoverable tab:** lists halted-but-resumable jobs with a Retry button.
- **Graceful errors:** server `{detail}` messages surface as toast notifications.
