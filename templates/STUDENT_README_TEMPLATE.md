# Smart Lost & Found Service

> A lost-and-found matching application that validates image inputs, extracts item descriptions using a Vision-Language Model, embeds them for similarity search, and stores the results in a persistent repository.

**Team:** _SWE Final Project Team_  •  **Topic:** _1_  •  **Course:** AI-ENG-110 Software Engineering

**Due:** **September 20, 2026**

---

## Quick start

```bash
# clone and setup
git clone https://github.com/ParvinSalahov/SWE-final-proj.git
cd SWE-final-proj
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Fill the API keys in `.env`, then run the project:

```bash
pytest tests/test_ai_smoke.py -v
pytest -q
python scripts/demo.py > artefacts/demo_run_output.txt 2>&1
```

## Docker

```bash
docker build -t lost-found-final .
docker run --rm --env-file .env lost-found-final python scripts/demo.py
```

To start the PostgreSQL dependency from `docker-compose.yml`:

```bash
docker compose up -d
```

## Benchmark

```bash
python scripts/bench.py
```

Measured result on the project benchmark:

| Method | Time |
|---|---:|
| Sequential | 0.5028 s |
| Concurrent | 0.1009 s |
| Speedup | 4.98x |

## Project layout

```text
.
├── ai/
├── src/
├── tests/
├── scripts/
├── artefacts/
├── report/
├── slides/
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
├── .env.example
├── README.md
└── templates/
```

## Notes

- Do not modify the provided `ai/` package contract.
- Keep `.env` out of version control; use `.env.example` as the template.
- The defence artefacts are expected to live under `artefacts/` and are reproducible via the demo script.
