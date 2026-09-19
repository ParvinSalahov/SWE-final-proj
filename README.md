# Smart Lost & Found

> An image-based lost-and-found service that uses a vision-language model and
> embedding similarity to register items and find likely matches.

**Team:** Repository Team
**Topic:** Topic 1 -- Lost and Found
**Course:** AI-ENG-110 Software Engineering, AI Academy
**Repository:** <https://github.com/ParvinSalahov/SWE-final-proj>

## Overview

The service accepts a photograph and an optional description of a lost or found
item. It validates the image, stores it, extracts a structured description with
a VLM, generates an embedding, and persists the item. Matching compares lost
items with found items (and vice versa) using cosine similarity.

The software-engineering layer is provider-agnostic. The selected online run
used OpenAI GPT-4o-mini for image descriptions and
`text-embedding-3-small` for embeddings. Anthropic and Gemini adapters are also
available through the provider factory.

## Features

- JPEG and PNG validation, including magic-byte and Pillow integrity checks.
- Five-megabyte upload limit by default.
- Structured `ItemDescription` validation with Pydantic.
- FastAPI HTTP API for registration, listing, health checks, and matching.
- Typer CLI for registration, listing, and match searches.
- PostgreSQL persistence through SQLAlchemy and filesystem image storage.
- Bounded asynchronous batch processing with `asyncio.gather()` and a
  semaphore.
- Retry with exponential backoff for transient provider failures.
- In-memory embedding cache with normalized SHA-256 keys.
- Offline unit/API tests using fake providers and mocked services.
- Docker image running as a non-root user with an HTTP health check.

## Quick start

### 1. Install

```powershell
git clone https://github.com/ParvinSalahov/SWE-final-proj
cd SWE-final-proj
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 2. Configure

```powershell
Copy-Item .env.example .env
```

Edit `.env` and provide credentials for the selected provider. Never commit
`.env` or real API keys.

### 3. Start PostgreSQL

```powershell
docker compose up -d postgres
```

The compose file exposes PostgreSQL on `localhost:5433`. The application
expects an async SQLAlchemy connection string in `DATABASE_URL`; use the
connection format required by your local environment.

### 4. Run the API

```powershell
uvicorn src.api:app --host 0.0.0.0 --port 8000
```

Health check:

```powershell
Invoke-RestMethod http://localhost:8000/
```

Expected response:

```json
{
  "status": "ok",
  "message": "Smart Lost & Found API is running"
}
```

## HTTP API

### Register a lost item

PowerShell:

```powershell
curl.exe -X POST http://localhost:8000/items/lost `
  -F "image=@data/lost/backpack_navy.png" `
  -F "user_text=Navy backpack with a worn front zipper"
```

### Register a found item

PowerShell:

```powershell
curl.exe -X POST http://localhost:8000/items/found `
  -F "image=@data/found/backpack_navy_2.png" `
  -F "user_text=Blue backpack found near the library"
```

Successful registration returns HTTP `201` with an item record containing an
ID, status, description, image path, and creation timestamp.

### List items

```powershell
curl.exe "http://localhost:8000/items"
curl.exe "http://localhost:8000/items?status=lost"
curl.exe "http://localhost:8000/items?status=found"
```

### Find matches

Replace `<ITEM_ID>` with the ID returned during registration:

```powershell
curl.exe "http://localhost:8000/items/<ITEM_ID>/matches?k=3"
```

`k` must be between `1` and `50`. The response contains the query item,
ranked matches, similarity scores, explanations, and the number of candidates
evaluated.

## CLI

The CLI talks to the API at `http://localhost:8000` and therefore requires the
API server to be running.

```powershell
python -m src.cli --help
python -m src.cli register-lost --image data/lost/backpack_navy.png --text "Navy backpack"
python -m src.cli register-found --image data/found/backpack_navy_2.png --text "Blue backpack"
python -m src.cli search-matches --id <ITEM_ID> --k 3
python -m src.cli list-items
python -m src.cli list-items --status lost
```

Images must exist locally and must be JPEG or PNG files no larger than five
megabytes. The CLI reports API errors and exits with a non-zero status when the
server cannot be reached or rejects a request.

## Environment variables

| Variable | Required | Default | Purpose |
|---|---:|---|---|
| `LLM_PROVIDER` | Online use | `anthropic` | VLM provider: `anthropic`, `openai`, or `gemini` |
| `LLM_MODEL` | Online use | `claude-sonnet-4-6` | VLM model identifier |
| `ANTHROPIC_API_KEY` | If Anthropic selected | empty | Anthropic credentials |
| `OPENAI_API_KEY` | If OpenAI selected | empty | OpenAI credentials |
| `GOOGLE_API_KEY` | If Gemini selected | empty | Google Gemini credentials |
| `EMBEDDING_PROVIDER` | Online use | `openai` | Embedding provider: `openai` or `gemini` |
| `EMBEDDING_MODEL` | Online use | `text-embedding-3-small` | Embedding model identifier |
| `DATABASE_URL` | Deployment | local configured value | Async SQLAlchemy database URL |
| `IMAGE_STORAGE_DIR` | No | `./storage/images` | Filesystem image directory |
| `MAX_IMAGE_SIZE_MB` | No | `5` | Maximum upload size |
| `HTTP_HOST` | No | `0.0.0.0` | API bind address |
| `HTTP_PORT` | No | `8000` | API port |
| `LOG_LEVEL` | No | `INFO` | Logging level |
| `AI_MAX_RETRIES` | No | `3` | Maximum transient-error attempts |
| `AI_RETRY_MIN_WAIT` | No | `1.0` | Initial retry delay in seconds |
| `AI_RETRY_MAX_WAIT` | No | `8.0` | Maximum retry delay in seconds |

If the selected provider key is missing, the provider adapter raises an
explicit configuration error. `.env.example` contains variable names but no
secrets.

## Demo and benchmark

The demo processes the sample lost/found images and prints top matches:

```powershell
python scripts/demo.py
```

The committed demo output is [`artefacts/demo_run_output.txt`](artefacts/demo_run_output.txt).

### Sequential versus concurrent benchmark

The benchmark compares the same ten-item registration workload in sequential
and bounded-concurrent modes. The recorded run used Windows, Python 3.11.9,
and cleared cache state between phases.

| Workload | N | Sequential | Concurrent | Speedup |
|---|---:|---:|---:|---:|
| Registration pipeline | 10 | 0.611 s | 0.061 s | 9.95x |

```powershell
python scripts/bench.py
```

The concurrent path uses `asyncio.gather()` and a semaphore. The benchmark
isolates pipeline overlap; real provider latency, rate limits, and database
capacity can reduce the observed speedup. In the recorded online run, average
embedding latency was 0.901 seconds and PostgreSQL was reachable.

The complete output is in
[`artefacts/bench_run_output.txt`](artefacts/bench_run_output.txt).

## Testing and static analysis

Run the complete test suite with coverage:

```powershell
python -m pytest --cov=src --cov-report=term-missing -q
```

Current results:

- **82 tests passed**
- **91% total coverage for `src`**
- `src/api.py`: 95% coverage
- `src/cli.py`: 99% coverage
- Provided AI smoke tests: passing
- Tests use fake AI providers, mocked HTTP services, and fake repositories;
  unit tests do not require network access.

Run type checkers:

```powershell
python -m mypy src tests
npx pyright
```

Current results:

```text
mypy: Success: no issues found in 22 source files
pyright: 0 errors, 0 warnings, 0 informations
```

## Docker

Build and run the API container:

```powershell
docker build -t lostfound .
docker run --env-file .env -p 8000:8000 lostfound
```

Or start the application and PostgreSQL together:

```powershell
docker compose up --build
```

The Dockerfile uses a single-stage `python:3.12-slim` image, runs as the
non-root `appuser`, exposes port `8000`, and checks the health endpoint.

## Architecture

```text
                    +----------------------+
                    | CLI / FastAPI HTTP    |
                    +----------+-----------+
                               |
                               v
                    +----------------------+
                    | ItemManager          |
                    | validation + matches |
                    +----+------------+----+
                         |            |
                         v            v
              +----------------+  +-------------------+
              | asyncio batch  |  | AIService         |
              | semaphore      |  | retry/cache/log   |
              +----------------+  +--------+----------+
                                           |
                                           v
                                  +-------------------+
                                  | provided ai/      |
                                  | VLM + embeddings  |
                                  +-------------------+
                         +----------------+----------------+
                         |                                 |
                         v                                 v
                +------------------+             +------------------+
                | PostgreSQL       |             | Filesystem images|
                | repository       |             | ImageStorage     |
                +------------------+             +------------------+
```

The provided `ai/` package is isolated behind `AIService`. Domain models and
repository interfaces keep the core logic independent from HTTP and provider
SDK details. See [`docs/architecture.md`](docs/architecture.md) for the
component-level description.

## Project layout

```text
.
├── ai/                         # Provided AI package; public interface preserved
├── src/
│   ├── api.py                  # FastAPI application
│   ├── cli.py                  # Typer CLI
│   ├── config.py               # Typed environment settings
│   ├── models.py               # Pydantic domain/response models
│   ├── core/                   # ItemManager and business rules
│   ├── services/               # AI wrapper, retries, cache, logging
│   ├── concurrency/            # Async bounded batch pipeline
│   └── storage/                # SQLAlchemy repository and image storage
├── tests/                      # Unit, API, smoke, and concurrency tests
├── data/                       # Sample lost/found images
├── artefacts/                  # Demo and benchmark output
├── scripts/                    # Demo and benchmark runners
├── docs/                       # Architecture and project documentation
├── templates/                  # Official submission templates
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── pyrightconfig.json
└── README.md
```

## Limitations and future work

- There is no authentication or authorization; production use needs user
  ownership and access control.
- The semaphore limits one process only. Multiple workers need a shared
  provider quota or distributed token bucket.
- Embedding provider, model, and vector dimension are not stored in the
  database, so model changes require controlled re-embedding.
- Provider failover is manual rather than automatic.
- Text-length limits, tracing, migration tooling, and sustained PostgreSQL
  load tests should be added before production deployment.

## Submission artefacts

The official report and defense deck are created from the templates in
`templates/` and should be added before the final submission:

```text
report/report.tex
report/report.pdf
slides/slides.tex
slides/slides.pdf
```

The signed contribution statement is based on
[`templates/CONTRIBUTION_STATEMENT.md`](templates/CONTRIBUTION_STATEMENT.md).
The final submission must also include the `v1.0-final` Git tag.

## AI-tool disclosure

AI assistants were used for repository navigation, test scaffolding,
type-checking fixes, and documentation drafting. The team reviewed generated
suggestions against the existing interfaces and tests, adapted the code where
needed, and verified the result with the full test suite, mypy, and Pyright.
The team can defend the final implementation.

## License

This is academic coursework and is not currently distributed as a
production library.
