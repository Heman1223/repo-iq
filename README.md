<div align="center">

# GitHub Repository AI Assistant

**Understand any GitHub repository in seconds using AI.**

Paste a repository URL. The assistant clones it, indexes the codebase with local
embeddings, and answers your questions in natural language — citing the exact
files every answer came from.

[![Python](https://img.shields.io/badge/Python-3.11%2B-3B82F6?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115%2B-2563EB?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-19-60A5FA?style=flat-square&logo=react&logoColor=white)](https://react.dev/)
[![ChromaDB](https://img.shields.io/badge/ChromaDB-vector%20store-3B82F6?style=flat-square)](https://www.trychroma.com/)
[![License](https://img.shields.io/badge/License-MIT-30363D?style=flat-square)](#license)

</div>

---

## Table of contents

- [Overview](#overview)
- [Screenshots](#screenshots)
- [Architecture](#architecture)
- [Tech stack](#tech-stack)
- [Project structure](#project-structure)
- [Installation](#installation)
- [Environment variables](#environment-variables)
- [API endpoints](#api-endpoints)
- [How the RAG pipeline works](#how-the-rag-pipeline-works)
- [Testing](#testing)
- [Design system](#design-system)
- [Security](#security)
- [Performance](#performance)
- [Troubleshooting](#troubleshooting)
- [Future improvements](#future-improvements)
- [License](#license)

---

## Overview

Reading an unfamiliar codebase is slow. This project turns any public GitHub
repository into a queryable knowledge base so you can ask the questions you would
otherwise answer by grepping through hundreds of files:

- *Explain this project.*
- *What technologies are used?*
- *How does authentication work? Where is the JWT generated?*
- *Which file handles API routing?*
- *Where is the database connection created?*
- *Generate onboarding instructions for a new developer.*

Every answer is **grounded**: only the chunks retrieved from that repository are
sent to the LLM, and if the repository does not contain the answer the assistant
says so instead of inventing one.

### What makes it more than a demo

| | |
|---|---|
| **Real retrieval** | Code-aware chunking, 384-dimensional local embeddings, cosine similarity search scoped per repository. |
| **Real citations** | Every answer lists file paths, line ranges, a relevance score and the exact retrieved snippet. |
| **Real error handling** | Private repos, 404s, rate limits, empty repos, missing API keys and embedding failures each produce a specific, actionable message. |
| **No hallucination by design** | The system prompt forbids unsupported claims, and retrieval short-circuits to a sentinel answer when nothing relevant is found. |
| **Zero embedding cost** | `all-MiniLM-L6-v2` runs locally; only the final generation call hits a paid API. |
| **Idempotent indexing** | Vectors persist in ChromaDB and are reused across restarts — a repository is never indexed twice. |

---

## Screenshots

> Replace these placeholders with your own captures.

| Landing page | Indexing pipeline |
|---|---|
| ![Landing page](docs/screenshots/landing.png) | ![Indexing](docs/screenshots/indexing.png) |

| Chat with citations | Repository dashboard |
|---|---|
| ![Chat](docs/screenshots/chat.png) | ![Dashboard](docs/screenshots/dashboard.png) |

---

## Architecture

```text
┌──────────────────────────────────────────────────────────────────────────┐
│  React + Vite + TypeScript + TailwindCSS + Framer Motion                  │
│  Landing → Indexing progress → Workspace (dashboard + chat)               │
└───────────────────────────────┬──────────────────────────────────────────┘
                                │  REST (axios)
┌───────────────────────────────▼──────────────────────────────────────────┐
│  FastAPI                                                                  │
│  /clone   /status   /ask   /summary   /health   /repositories             │
├───────────────────────────────────────────────────────────────────────────┤
│  Services (one responsibility each)                                       │
│                                                                           │
│   git_service ──▶ file_service ──▶ chunking_service ──▶ embedding_service │
│        │                                                        │         │
│  github_service                                            vector_store   │
│        │                                                        │         │
│        └───────────────▶ indexing_service (orchestrator) ◀───────┘        │
│                                    │                                      │
│                              rag_service ──▶ llm_service ──▶ Gemini       │
└───────────────────────────────────────────────────────────────────────────┘
                                    │
                      ChromaDB (persistent, one collection per repository)
```

The pipeline, end to end:

```text
GitHub URL
   ↓ validate + sanitise (allow-listed host, strict owner/repo pattern)
   ↓ fetch public metadata from the GitHub REST API
   ↓ shallow clone (depth 1, blob-filtered, no credential prompts)
   ↓ walk the tree, pruning node_modules / dist / lockfiles / binaries / media
   ↓ split with LangChain language-aware recursive splitters (overlap preserved)
   ↓ embed locally with all-MiniLM-L6-v2  → 384-d vectors
   ↓ persist to ChromaDB with file path, language and line-range metadata
   ↓ delete the clone (Chroma is now the source of truth)
Question
   ↓ embed the question
   ↓ cosine similarity search, top-k, distance-filtered
   ↓ assemble a cited CONTEXT block (never the whole repository)
   ↓ Gemini generates a grounded answer
Answer + source files
```

---

## Tech stack

**Backend**

| Concern | Choice |
|---|---|
| API | FastAPI + Uvicorn |
| Chunking | `langchain-text-splitters` (language-aware recursive splitting) |
| Embeddings | `sentence-transformers` · `all-MiniLM-L6-v2`, runs locally |
| Vector DB | ChromaDB (persistent client, cosine space) |
| Git | GitPython (shallow, non-interactive clones) |
| LLM | Google Gemini via the `google-genai` SDK |
| Config | pydantic-settings + python-dotenv |

**Frontend**

| Concern | Choice |
|---|---|
| Framework | React 19 + Vite 8 + TypeScript (strict) |
| Styling | TailwindCSS v4 (`@theme` design tokens) |
| Animation | Framer Motion |
| Icons | Lucide React |
| HTTP | Axios (single typed client) |
| Markdown | react-markdown + remark-gfm + rehype-highlight |

---

## Project structure

```text
github-repo-ai-assistant/
├── backend/
│   ├── app/
│   │   ├── main.py                  # App factory, CORS, lifespan, warm-up
│   │   ├── api/
│   │   │   ├── router.py            # Aggregates all route modules
│   │   │   └── routes/
│   │   │       ├── health.py        # GET  /health
│   │   │       ├── repository.py    # POST /clone · GET /status · /summary
│   │   │       └── chat.py          # POST /ask
│   │   ├── core/
│   │   │   ├── config.py            # Typed settings, all env-overridable
│   │   │   ├── exceptions.py        # Domain errors + JSON handlers
│   │   │   └── logging_config.py
│   │   ├── models/schemas.py        # Pydantic request/response contracts
│   │   ├── services/
│   │   │   ├── git_service.py       # Clone / cleanup
│   │   │   ├── github_service.py    # Public metadata
│   │   │   ├── file_service.py      # Walk, filter, safe read
│   │   │   ├── chunking_service.py  # LangChain splitters
│   │   │   ├── embedding_service.py # Local sentence-transformers singleton
│   │   │   ├── vector_store.py      # ChromaDB facade
│   │   │   ├── index_cache.py       # Durable registry of indexed repos
│   │   │   ├── indexing_service.py  # Pipeline orchestrator + job progress
│   │   │   ├── rag_service.py       # Retrieve → prompt → answer
│   │   │   ├── llm_service.py       # The only module that talks to Gemini
│   │   │   └── prompts.py           # All prompt engineering, in one place
│   │   └── utils/
│   │       ├── repo_url.py          # URL parsing + identifier sanitising
│   │       └── paths.py             # Traversal protection helpers
│   ├── repositories/                # Transient clones (gitignored)
│   ├── chroma_db/                   # Persisted vectors (gitignored)
│   ├── requirements.txt
│   └── .env.example
│
├── frontend/
│   ├── src/
│   │   ├── App.tsx                  # landing → indexing → workspace
│   │   ├── components/
│   │   │   ├── ui/                  # Button, Card, Chip, Skeleton, ErrorBanner
│   │   │   ├── layout/TopBar.tsx
│   │   │   ├── landing/             # Hero, URL form, feature grid
│   │   │   ├── indexing/            # Pipeline progress screen
│   │   │   ├── workspace/           # Repository dashboard + layout
│   │   │   └── chat/                # Messages, citations, composer, markdown
│   │   ├── hooks/                   # useIndexing, useChat, useHealth, useTypewriter
│   │   ├── lib/                     # api.ts, constants.ts, format.ts
│   │   ├── types/index.ts           # Mirrors the backend schemas
│   │   └── index.css                # Design tokens + component classes
│   ├── vite.config.ts
│   └── .env.example
│
└── README.md
```

---

## Installation

**Prerequisites:** Python 3.11+, Node.js 18+, Git, and a
[Gemini API key](https://aistudio.google.com/app/apikey) (free tier works).

### 1. Backend

```bash
cd backend

python -m venv venv
# Windows
venv\Scripts\activate
# macOS / Linux
source venv/bin/activate

pip install -r requirements.txt

cp .env.example .env        # Windows: Copy-Item .env.example .env
# then set GEMINI_API_KEY in .env

uvicorn app.main:app --reload --port 8000
```

The API is now on <http://127.0.0.1:8000> and interactive docs on
<http://127.0.0.1:8000/docs>.

> The first indexing run downloads the embedding model (~90 MB) from Hugging
> Face. Subsequent runs are offline and fast.

### 2. Frontend

```bash
cd frontend
npm install
npm run dev
```

Open <http://localhost:5173>.

### 3. Use it

1. Paste a public repository URL, e.g. `https://github.com/pallets/flask`.
2. Watch the pipeline: clone → read files → chunk → embed → vector database.
3. Ask questions, or click a suggested chip such as *Explain the folder structure*.

### Available scripts

| Location | Command | Purpose |
|---|---|---|
| `backend` | `uvicorn app.main:app --reload --port 8000` | Run the API with hot reload |
| `frontend` | `npm run dev` | Vite dev server |
| `frontend` | `npm run build` | Typecheck + production build |
| `frontend` | `npm run typecheck` | TypeScript only |
| `frontend` | `npm run lint` | oxlint |
| `frontend` | `npm run test:e2e` | Playwright browser tests |
| `backend` | `pytest -m "not network"` | Fast offline test suite |
| `backend` | `pytest -m network` | Real clone + indexing integration tests |

---

## Environment variables

### `backend/.env`

| Variable | Default | Description |
|---|---|---|
| `GEMINI_API_KEY` | *(empty)* | **Required for answers.** Indexing works without it; `/ask` returns 503. |
| `GEMINI_MODEL` | `gemini-flash-latest` | Generation model. The `-latest` alias keeps working as Google retires specific versions; pin a concrete model (e.g. `gemini-3.6-flash`) for stable output. |
| `GEMINI_TEMPERATURE` | `0.2` | Low by design — this is a factual tool. |
| `GEMINI_MAX_OUTPUT_TOKENS` | `2048` | Response cap. |
| `GEMINI_THINKING_LEVEL` | `minimal` | Gemini 3 reasoning depth (`minimal`/`low`/`medium`/`high`, empty for the model default). Lower is much faster; quality on repository questions is comparable. Unsupported values fall back automatically. |
| `GITHUB_TOKEN` | *(empty)* | Optional. Raises the metadata rate limit from 60 to 5000 req/h. |
| `CORS_ORIGINS` | `http://localhost:5173,…` | Comma-separated allowed origins. |
| `API_PREFIX` | *(empty)* | Set to e.g. `/api` to namespace all routes. |
| `EMBEDDING_MODEL_NAME` | `sentence-transformers/all-MiniLM-L6-v2` | Any sentence-transformers model. |
| `EMBEDDING_BATCH_SIZE` | `64` | Encoding batch size. |
| `CHUNK_SIZE` / `CHUNK_OVERLAP` | `1200` / `180` | Splitter configuration. |
| `RETRIEVAL_TOP_K` | `8` | Chunks retrieved per question. |
| `MAX_MATCH_DISTANCE` | `1.55` | Cosine distance above which a match is discarded. |
| `MAX_FILE_SIZE_BYTES` | `400000` | Per-file read cap. |
| `MAX_FILES_PER_REPO` | `4000` | Scan cap. |
| `CLONE_DEPTH` / `CLONE_TIMEOUT_SECONDS` | `1` / `300` | Clone behaviour. |
| `REPOSITORIES_DIR` / `CHROMA_DIR` | `repositories` / `chroma_db` | Storage paths. |
| `LOG_LEVEL` | `INFO` | Logging verbosity. |

### `frontend/.env`

| Variable | Default | Description |
|---|---|---|
| `VITE_API_BASE_URL` | `http://127.0.0.1:8000` | Backend base URL. |
| `VITE_API_TIMEOUT_MS` | `180000` | Axios timeout. |

---

## API endpoints

Interactive documentation: `/docs` (Swagger) and `/redoc`.

### `POST /clone` — index a repository

```jsonc
// request
{ "repo_url": "https://github.com/pallets/flask", "force_reindex": false }

// 202 Accepted
{
  "repo_id": "pallets__flask",
  "full_name": "pallets/flask",
  "already_indexed": false,
  "status": { "stage": "queued", "progress": 0.01, "message": "Queued", ... }
}
```

Indexing runs in the background; poll `/status`. Submitting an already-indexed
repository is a no-op unless `force_reindex` is `true`.

### `GET /status?repo_id=…` — poll progress

```jsonc
{
  "repo_id": "pallets__flask",
  "stage": "embedding",             // queued|validating|cloning|reading_files|
  "progress": 0.71,                 // chunking|embedding|storing|finalizing|ready|failed
  "message": "Generating embeddings (820/1328 chunks)",
  "is_ready": false,
  "metadata": { "stars": 70000, "default_branch": "main", ... },
  "stats": { "total_files_indexed": 208, "total_chunks": 1328, ... }
}
```

### `POST /ask` — ask a question

```jsonc
// request
{
  "repo_id": "pallets__flask",
  "question": "How is the request context created?",
  "history": [{ "role": "user", "content": "..." }]
}

// response
{
  "answer": "The request context is created in `src/flask/ctx.py` …",
  "sources": [
    {
      "file_path": "src/flask/ctx.py",
      "start_line": 118, "end_line": 151,
      "relevance": 0.75,
      "snippet": "class RequestContext:\n    ..."
    }
  ],
  "grounded": true,
  "model": "gemini-flash-latest",
  "retrieved_chunks": 8,
  "elapsed_ms": 2310
}
```

### `GET /summary?repo_id=…[&refresh=true]`

Multi-facet retrieval (README, manifests, entry points, routes, models, auth,
tests…) condensed into an onboarding briefing. Cached after the first call.

### `GET /health`

Reports LLM configuration, embedding model state, vector store readiness and the
number of indexed repositories. Returns `degraded` when `GEMINI_API_KEY` is unset.

### `GET /repositories` · `DELETE /repositories/{repo_id}`

List everything indexed on this server, or drop a repository's vectors and
cached metadata.

### Error envelope

Every failure shares one shape, with a stable machine-readable code:

```jsonc
{ "error": { "code": "private_repository", "message": "…", "hint": null } }
```

`invalid_repository_url` · `repository_not_found` · `private_repository` ·
`empty_repository` · `clone_failed` · `github_api_error` · `repository_not_indexed` ·
`indexing_in_progress` · `embedding_failed` · `llm_not_configured` · `llm_error`

---

## How the RAG pipeline works

**1 · File selection.** `file_service` prunes `node_modules`, `dist`, `build`,
`coverage`, `.git`, virtualenvs and caches during the walk itself, then rejects
lockfiles, minified bundles, binaries, media and anything failing a NUL-byte
sniff. Supported: Python, JS/TS/JSX/TSX, Java, Go, Rust, Ruby, PHP, C/C++/C#,
Swift, Kotlin, SQL, HTML/CSS/SCSS, Markdown/RST, JSON/YAML/TOML, Dockerfiles,
Makefiles, `requirements.txt`, `package.json`, `.env.example` and more.

**2 · Chunking.** LangChain's `RecursiveCharacterTextSplitter.from_language`
splits along class and function boundaries where the language is known, falling
back to paragraph/line separators otherwise. Chunks overlap (default 180 chars)
so context is never severed mid-definition, and each records its real
`start_line`/`end_line` for citation.

**3 · Embeddings.** `all-MiniLM-L6-v2` encodes chunks in batches on the local
CPU, producing normalised 384-dimensional vectors. The model loads lazily behind
a lock and is warmed up in a background thread at startup.

**4 · Storage.** One Chroma collection per repository (cosine space), with
`repo_id`, `file_path`, `file_name`, `language`, `chunk_index` and line range on
every vector. Re-indexing drops and rebuilds the collection atomically.

**5 · Retrieval.** The question is embedded with the same model; the top *k*
chunks are fetched and filtered by distance. If nothing survives, the API returns
the sentinel answer without spending an LLM call.

**6 · Generation.** Retrieved passages are assembled into a numbered, file-labelled
`CONTEXT` block (hard-capped at ~28k characters) alongside a directory outline and
the recent conversation. The system prompt requires the model to answer only from
that context, to cite file paths in backticks, and to reply with exactly
*"I couldn't find that information in the indexed repository."* when it cannot.

---

## Testing

Two suites: pytest for the backend and pipeline, Playwright for the UI.

```bash
# Backend — fast, offline (URL validation, file filtering, chunking,
# grounding logic, API contracts, security)
cd backend
pytest -m "not network"

# Backend — real clone + local embeddings + retrieval + persistence
pytest -m network

# Frontend — real Chromium, API responses stubbed for determinism
cd frontend
npm run test:e2e          # add --ui for the interactive runner
```

| Suite | Tests | Covers |
|---|---|---|
| `pytest -m "not network"` | 136 | URL parsing, include/exclude rules, chunking, embedding failures, RAG grounding and citations, prompt construction, error envelope, path traversal, prompt-injection structure |
| `pytest -m network` | 28 | Clone (shallow, cleanup, failure translation), full index of a real repository, vector persistence across restart, semantic retrieval quality, reuse/dedup, deletion |
| `npm run test:e2e` | 61 | Landing page, theme tokens, responsive layout at four viewports, client-side validation, pipeline progress screen, dashboard, chat flow, citations, typing indicator, error states, XSS/injection rendering |

The LLM boundary is mocked in tests: `llm_service.generate` is patched so grounding,
citation assembly and the "no answer" contract are verified deterministically without
an API key or token spend. Live Gemini output quality is the one thing the suites
cannot assert — run the app with a key to evaluate it.

## Design system

A restrained dark theme — GitHub Dark's structure with GitHub's green accents
replaced by an AI blue. No neon, no childish gradients.

| Token | Value | Use |
|---|---|---|
| `--color-canvas` | `#0D1117` | Page background |
| `--color-surface` | `#161B22` | Cards |
| `--color-line` | `#30363D` | Borders |
| `--color-brand` | `#3B82F6` | Primary accent |
| `--color-brand-strong` | `#2563EB` | Pressed / emphasis |
| `--color-brand-soft` | `#60A5FA` | Hover / links |
| `--color-ink` | `#F8FAFC` | Primary text |
| `--color-muted` | `#94A3B8` | Secondary text |
| `--color-danger` / `--color-success` | `#EF4444` / `#22C55E` | Feedback |

Glassmorphism is applied sparingly: 8–12px backdrop blur, ~70% surface opacity,
hairline borders and soft shadows. Typography is Inter for UI and JetBrains Mono
for code. Framer Motion handles fades, slide-ups, micro-interactions and layout
transitions; everything collapses gracefully under
`prefers-reduced-motion: reduce`.

---

## Security

- **Repository code is never executed.** Files are only ever opened for reading.
- **Host allow-list.** Only `github.com` URLs are accepted; the owner/repo
  segments must match a strict pattern before anything is cloned.
- **Path-traversal protection.** Every candidate file is resolved and verified to
  live inside its sandbox directory; symlinks are refused outright.
- **Sanitised identifiers.** `repo_id` and Chroma collection names are derived
  through a whitelist filter, so a repository name can never influence a path.
- **Non-interactive git.** `GIT_TERMINAL_PROMPT=0` and a stall timeout prevent
  credential prompts and hung requests on private repositories.
- **No secrets in the client.** The Gemini key lives only in the backend `.env`.
- **Dangerous files skipped.** Keys, certificates, archives and binaries are
  excluded from indexing.

---

## Performance

- **Index once, reuse forever.** `index_cache.json` plus the persisted Chroma
  collections survive restarts; re-submitting a repository skips straight to the
  workspace.
- **Metadata caching.** GitHub facts, directory outline and generated summaries
  are stored alongside the index.
- **Clones are disposable.** The working copy is deleted once vectors are written.
- **Batched embedding and upserts.** Configurable batch sizes keep memory flat on
  large repositories.
- **Bounded context.** Retrieval and the assembled prompt are both capped, so
  latency and token spend stay predictable regardless of repository size.
- **Non-blocking startup.** The transformer warms up in a background thread.
- **Code-split frontend.** React, Framer Motion, markdown and highlight.js ship as
  separate cacheable chunks.

Reference run (`pallets/flask`, 8-core laptop CPU): 208 files → 1,328 chunks →
1,328 vectors in ~119 s cold. Subsequent loads are instant; a typical question
answers in 2–4 s.

---

## Troubleshooting

| Symptom | Cause and fix |
|---|---|
| `Cannot reach the backend` | The FastAPI server is not running, or `VITE_API_BASE_URL` is wrong. |
| Status pill says *Gemini key missing* | Set `GEMINI_API_KEY` in `backend/.env` and restart the backend. |
| `GitHub API rate limit reached` | Anonymous limit is 60 req/h — add a `GITHUB_TOKEN`. Indexing still proceeds without metadata. |
| First index is slow | The embedding model is downloading (~90 MB). It is cached afterwards. |
| `private_repository` | Only public repositories are supported today. |
| `model ... is unavailable for this key` | Google retired that model for new keys. Use `GEMINI_MODEL=gemini-flash-latest`. |
| Answers say nothing was found | The topic genuinely is not in the repository, or `MAX_MATCH_DISTANCE` is too strict. |
| Answers take 20-40s, or `503`/`429` errors | Free-tier congestion and quota. Set `GEMINI_THINKING_LEVEL=minimal`, or use a paid key. Measured latency for the same request varied from 2s to 30s purely by server load. |

---

## Future improvements

- Private repository support via **GitHub OAuth**
- Indexing and querying **multiple repositories** at once, with cross-repo search
- **Multi-agent architecture** (planner → retriever → verifier) with **LangGraph**
- **Code graph visualisation** of imports, call paths and module boundaries
- **Repository comparison** — diff two codebases architecturally
- **Pull request analysis** and **issue summarisation**
- **MCP integration** so the index is queryable from any MCP-capable client
- Hybrid **BM25 + vector** retrieval with a re-ranking stage
- Streaming (SSE) answers and WebSocket indexing progress
- Docker Compose deployment and a pytest suite in CI

---

## License

MIT — see [LICENSE](LICENSE).

<div align="center">
<sub>Built to demonstrate production RAG engineering: retrieval quality, grounded generation, and a UI worth shipping.</sub>
</div>
"# repo-iq" 
