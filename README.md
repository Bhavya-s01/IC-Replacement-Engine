# IC Alternative Finder

Finds technically compatible replacement ICs for parts in an internal supply-chain list.

- **Candidate pool:** ~76K ICs scraped from DigiKey (parametric specs) in 24 categories.
- **Supply-chain parts:** imported from the ODM Excel template, categories taken from the Excel, specs enriched from datasheets (LLM + regex) or Excel descriptions. Parts without a datasheet show "Datasheet not found" and the Excel-listed replacement.
- **Matching:** per-category weighted rules in `match_rules.py`, scored in `finder.py`. Search needs no LLM.
- **Admin portal:** `/api/admin` runs scraping, datasheet search, enrichment and new-MPN onboarding as background jobs.

## Quick start

```bash
python -m pip install -r requirements.txt
python -m playwright install msedge
cp .env.example .env
python -m uvicorn api:app --port 8000        # http://localhost:8000/docs
python finder_cli.py find MIC5501-3.0YM5-TR  # CLI alternative
python db_status.py                          # database report
```

Details (endpoints, admin tasks, operations): [DEPLOYMENT.md](DEPLOYMENT.md).

## Layout

| Path | Purpose |
|---|---|
| `api.py`, `admin_api.py` | FastAPI app and admin job runner |
| `finder.py`, `match_rules.py`, `spec_parser.py` | Matching engine |
| `database.py`, `models.py`, `config.py` | Schema and categories |
| `main.py`, `engine.py`, `plugins/` | DigiKey scraping (Playwright) |
| `fetch_datasheets.py`, `find_datasheets_multi.py`, `retry_datasheets.py`, `audit_datasheets.py`, `repair_database.py` | Datasheet discovery and URL maintenance |
| `finder_extras/` | Regex extractor (`spec_extractor.py`), LLM parser, pinout comparison |
| `add_mpns.py`, `enrich_local.py`, `enrich_from_description.py`, `enrich_all.py` | Onboarding and enrichment |
| `import_template.py`, `reclassify.py`, `clean_specs.py`, `build_specs_cache.py` | Data preparation |
