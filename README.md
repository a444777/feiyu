# Feiyu

Feiyu is a minimal FastAPI application used to practise governed, fork-based GitHub delivery before implementing the full knowledge-precipitation system described in `docs/`.

## Local development

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
.venv/bin/ruff check app tests
.venv/bin/pytest
.venv/bin/uvicorn app.main:app --reload
```

## Container

```bash
docker build -t feiyu:local .
docker run --rm -p 8000:8000 feiyu:local
curl http://127.0.0.1:8000/health
```

## Governance

Changes to `main` arrive through pull requests. CI, CodeQL, resolved review conversations, and approval from the code owner are required before merge. See [CONTRIBUTING.md](CONTRIBUTING.md).
