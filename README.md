# Smart Lost & Found Service

> A small, production-minded lost-and-found matching service that combines image validation, VLM-based description extraction, embedding similarity, and a bounded async concurrency pipeline for scalable batch processing.

**Team:** SWE Final Project Team  •  **Topic:** 1 — Lost & Found Matching Service  •  **Course:** AI-ENG-110 Software Engineering

**Repository:** https://github.com/ParvinSalahov/SWE-final-proj  •  **Final tag:** `v1.0-final`

---

## Quick start

```bash
# 1. create environment
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 2. configure runtime
cp .env.example .env
# fill provider keys and optional database settings

# 3. run smoke tests
pytest tests/test_ai_smoke.py -v
pytest -q

# 4. run the demo
python scripts/demo.py > artefacts/demo_run_output.txt 2>&1
```

## Docker

```bash
# build
docker build -t lost-found-final .

# run the app with env vars and the default HTTP server
docker run --rm --env-file .env -p 8000:8000 lost-found-final

# run the demo script inside the container
docker run --rm --env-file .env lost-found-final python scripts/demo.py
```

If you want the PostgreSQL dependency from `docker-compose.yml`:

```bash
docker compose up -d
# then run the app or demo against the database
```

## Demo command and expected output

```bash
python scripts/demo.py > artefacts/demo_run_output.txt 2>&1
head -n 20 artefacts/demo_run_output.txt
```

Example output includes ranked candidate matches such as:

```text
Processing LOST items (mode=online)...
  - backpack_navy.png: backpack (0.90)
  - phone_apple_black.png: mobile phone (0.90)

Top matches for LOST item: 'backpack_navy.png'
  -> backpack_navy_2.png  score=+0.826
  -> wallet_brown_2.png  score=+0.672
```

## Sequential vs concurrent benchmark

The project benchmark compares a sequential registration loop with the bounded async pipeline in `src/concurrency/pipeline.py`.

| Workload | N | Sequential | Concurrent | Speedup |
|---|---:|---:|---:|---:|
| 10 mock item registrations | 10 | 0.5028 s | 0.1009 s | 4.98x |

Reproduce with:

```bash
python scripts/bench.py
```

The benchmark is intentionally deterministic and uses mocked work to isolate the concurrency layer rather than external provider latency.

## Testing

```bash
pytest -q
```

Current status:

- `82 passed` in the repository test suite
- provided `tests/test_ai_smoke.py` passes (`27 passed`)
- static checks:
  - `python -m mypy src tests scripts --python-version 3.12` → success
  - `python -m pyright src scripts tests` → 0 errors

## Project structure

```text
.
├── ai/                     # provided AI package; contract is fixed
├── src/
│   ├── config.py           # typed settings via pydantic-settings
│   ├── core/
│   ├── services/
│   ├── concurrency/
│   ├── storage/
│   ├── api.py
│   ├── cli.py
│   └── models.py
├── tests/
├── data/
├── scripts/
│   ├── demo.py
│   └── bench.py
├── artefacts/
├── report/
│   ├── report.tex
│   └── report.pdf
├── slides/
│   ├── slides.tex
│   └── slides.pdf
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── .env.example
├── README.md
└── templates/
```

## Architecture summary

The system is layered in four clear blocks:

1. Entry points: CLI and HTTP API call into the business layer.
2. Core service layer: image validation, AI orchestration, match generation.
3. Concurrency layer: `asyncio.gather()` plus `asyncio.Semaphore` bounds the number of simultaneous item registrations.
4. Storage layer: filesystem for uploaded image blobs and SQLAlchemy/SQLite/PostgreSQL-backed persistence for metadata and embeddings.

## Limitations

- The benchmark isolates the concurrency logic and does not model external AI/provider latency under load.
- The runtime is still tuned for a single deployment context rather than large multi-instance production scaling.
- If the provider rate limit is hit repeatedly, the system falls back to retry windows rather than a full distributed queue.

## AI tooling disclosure

We used GitHub Copilot to draft selected implementation scaffolds and tests; the team reviewed, adapted, and validated every line before integrating it into the solution.

## License

Academic coursework project. No external deployment or commercial license is implied.
