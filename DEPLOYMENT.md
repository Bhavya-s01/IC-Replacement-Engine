# Deployment Guide

## Runtime components

| Area | Entry point | Responsibility |
|---|---|---|
| Ingestion | `main.py` | Scrape DigiKey categories into SQLite. |
| Matching | `finder_cli.py`, `finder.py` | Find and compare electrical alternatives. |
| API | `api.py` | Expose search, lookup, comparison, and dashboard endpoints. |
| Datasheets | `fetch_datasheets.py`, `find_datasheets_multi.py` | Find candidate URLs, download PDFs, and save only validated documents. |
| Enrichment | `finder_extras/llm_parser.py` | Extract recognised datasheet fields through NVIDIA NIM with regex fallback. |
| Maintenance | `audit_datasheets.py`, `repair_database.py`, `populate_datasheet_queue.py` | Audit saved URLs, safely clear confirmed bad ones, and replenish the fetch queue. |

## Required setup

```bash
python -m pip install -r requirements.txt
python -m playwright install msedge
copy .env.example .env
```

Set `NVIDIA_API_KEY` in `.env` only when LLM enrichment is required. Scraping,
matching, audits, and no-enrichment fetch batches do not require that key.

## Supported operating flows

### Ingest catalogue data

```bash
python main.py scrape --category ldo_ic --max-pages 2
python main.py status
```

### Find alternatives

```bash
python finder_cli.py lookup MIC5501-3.0YM5-TR
python finder_cli.py find MIC5501-3.0YM5-TR --same-package
```

### Maintain datasheet URLs

```bash
# Refill the queue without replacing its existing statuses.
python populate_datasheet_queue.py

# One resumable audit; its checkpoint is exports/datasheet_audit.csv.
python audit_datasheets.py --workers 8

# Inspect the repair set, then clear only conclusively bad URLs.
python repair_database.py
python repair_database.py --apply

# Run small batches. These save a URL only after PDF and MPN validation.
python fetch_datasheets.py --limit 5 --no-enrich
python find_datasheets_multi.py --limit 5 --no-enrich
```

`request_error` and HTTP 403 audit results are retained for later retry; they
are not treated as proof that a vendor URL is bad. HTTP 404/410 and documents
proven to be invalid, unrelated, or compliance-only are repair candidates.

## Data locations

- `ic_database.db`: production SQLite data; back it up before bulk operations.
- `datasheets/`: PDFs validated by the fetch workflows.
- `downloads/datasheets/`: parser-managed cached downloads.
- `exports/datasheet_audit.csv`: resumable URL-audit checkpoint and report.

## What is intentionally not automatic

- The audit never modifies the database.
- `repair_database.py` has a dry-run default and creates a backup when applied.
- LLM enrichment is optional and requires both a key and readable document text.
- A compatibility score is an engineering aid, not a replacement for pinout,
  lifecycle, qualification, or supply-chain review.
