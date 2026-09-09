# FirstGlanceKnox

A local Django application connecting the public window-cleaning website to customer estimates, crew assignments, job completion, invoicing, and compensation records.

## Run the local preview (PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env  # First setup only; preserve an existing .env.
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py seed_demo
.\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8765
```

Open [the website](http://127.0.0.1:8765/), [crew workspace](http://127.0.0.1:8765/crew/), or [customer portal](http://127.0.0.1:8765/portal/). Use the generated credentials in `.local/demo-access.txt`. The demo command preserves existing accounts and passwords on subsequent runs and refuses to run with `DEBUG=false`.

The original logo is `static/brand/logo.jpg`. Temporary photos and initial copy are in `marketing/content.py`; the gallery supports administrator-published media. Never treat demo prices or customers as business facts.

Local emails are written under `.local/emails/`. Estimate and invoice deliveries enter a persistent outbox; explicitly run `python manage.py drain_outbox` using the virtual environment to deliver queued messages through the configured backend. The default backend writes files only.

## Verify

```powershell
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py makemigrations --check --dry-run
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m pytest -q
```

Browser tests are opt-in. Install Chromium once, then run these against a running local preview:

```powershell
.\.venv\Scripts\python.exe -m playwright install chromium
$env:FGK_E2E_BASE_URL='http://127.0.0.1:8765'
$env:FGK_RUN_CREW_E2E='1'
.\.venv\Scripts\python.exe -m pytest tests/test_public_browser.py tests/test_crew_browser.py -q
```

Public browser checks use the preview URL. Crew browser checks create an isolated test database and local test server with synthetic records. They do not change the preview's demo records. Screenshots are written to ignored `.local/screenshots/`.

## Documentation

- [Staff instruction manuals and customer response guide](docs/manuals/START-HERE.md)
- [Product scope](docs/product-spec.md) and [implementation checklist](docs/checklist.md)
- [Architecture](docs/architecture.md) and [data model](docs/data-model.md)
- [Workflows](docs/workflows.md) and [permissions](docs/permissions.md)
- [Decisions](docs/decisions.md) and [production release gates](docs/deployment.md)

This is a development preview, not a completed production release. SQLite provides local persistence; concurrent production writes require PostgreSQL validation. See the checklist for remaining product work and release checks.
