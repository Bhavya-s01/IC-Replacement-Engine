# Quick Reference

## Configure LLM enrichment

```bash
copy .env.example .env
# Set NVIDIA_API_KEY in .env
```

The default model is `meta/llama-3.1-8b-instruct`. To use a compatible
self-hosted NIM model, set `NVIDIA_MODEL` in `.env`.

## Useful commands

```bash
python finder_cli.py lookup MIC5501-3.0YM5-TR
python finder_cli.py find MIC5501-3.0YM5-TR
python db_status.py
```

## Local validation check

```bash
python -c "from finder_extras.llm_parser import _validate_spec; print(_validate_spec('Dropout Voltage (Max)', '160 mV'))"
```

Expected result: `(True, None)`.

See `LLM_PARSER_UPDATES.md` for the extraction flow and
`SCRAPER_ACCURACY_REPORT.md` for measured coverage and limitations.
