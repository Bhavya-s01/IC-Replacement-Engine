# Deployment Guide

## What it is

A FastAPI service plus a SQLite database (`ic_database.db`, ~120 MB) that recommends replacement ICs.
Lookups read only the database; **no LLM call is made when a user searches**. The LLM is used only by
admin jobs that add or enrich parts.

## Requirements

- Python 3.11+ (tested on 3.14), Windows or Linux
- Microsoft Edge for Playwright (`python -m playwright install msedge`), needed only for scraping and datasheet search
- An OpenAI-compatible LLM key (Gemini free tier works), needed only for enrichment
- ~500 MB disk (database, optional `datasheets/` PDF cache)

## Setup

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt     # Linux: .venv/bin/python
python -m playwright install msedge
cp .env.example .env        # fill LLM_API_KEY; set ADMIN_TOKEN for remote admin access
```

`database.py` creates every table on first start, so an empty database also boots.

## Run

```bash
python -m uvicorn api:app --host 0.0.0.0 --port 8000
```

Docs and try-it UI: `http://<host>:8000/docs`.

| Area | Endpoints |
|---|---|
| Lookup | `GET /api/search`, `/api/lookup/{mpn}`, `/api/compare`, `/api/browse`, `/api/categories` |
| Alternatives | `GET /api/alternatives/{mpn}` (parts without a datasheet return only the Excel replacement and a "Datasheet not found" status), `/api/alternatives-full/{mpn}` |
| Supply chain | `GET /api/supply-chain/{mpn}`, `/api/supply-chain-stats` |
| Admin | `/api/admin/*`, see below |

## Admin portal (`/api/admin`)

Allowed from localhost, or from anywhere with header `x-admin-token: $ADMIN_TOKEN`.
Jobs run as background processes (one at a time), with logs under `admin_logs/`.

| Task | Use |
|---|---|
| `add_mpns` | New MPNs: find datasheet, extract specs, update cache. They are searchable afterwards. |
| `scrape` | Pull more ICs from DigiKey for chosen categories. |
| `retry_datasheets` / `fetch_datasheets` | Look for missing datasheets (LCSC, Alldatasheet, Datasheet4U). |
| `enrich_local` / `enrich_description` | LLM spec extraction from datasheet URLs / Excel descriptions. |
| `reclassify`, `db_status`, `enrich_stats` | Maintenance and reports. |
| `POST /upload/supply-chain`, `/upload/mpns` | Import an ODM Excel template; queue MPNs. |

Equivalent CLI: `python add_mpns.py -c ldo_ic MPN1 MPN2`, `python main.py scrape -c ldo_ic -m 5`.

## Data

- `ic_database.db`: components (DigiKey candidates plus supply-chain parts), specs, `supply_chain`, `specs_cache`, `datasheet_queue`. Back it up before bulk jobs; `*.bak` files are not needed in production.
- `python clean_specs.py --apply` and `python build_specs_cache.py` rebuild derived data (the cache is what the finder reads).
- Datasheets are streamed from their URL; only validated URLs are stored.

## Operating notes

- Run behind a reverse proxy with TLS; restrict CORS in `api.py` (currently `*`) to your frontend origin.
- Set `ADMIN_TOKEN` in any shared environment; without it admin endpoints answer 403 to non-local clients.
- Gemini free tier is rate-limited; 503/429 responses fall back to regex extraction for that part.
- A compatibility score is an engineering aid, not a replacement for pinout, lifecycle, qualification or supply-chain review.
- Tests: `python -m unittest test_datasheet_pipeline`.
