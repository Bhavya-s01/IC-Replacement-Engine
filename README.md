# IC Alternative Finder

A technical IC replaceability engine for flat-panel monitor components. Scrapes parametric data from DigiKey, stores it in SQLite, and finds electrically compatible replacement ICs using weighted multi-criteria scoring across 22 component categories.

## What It Does

1. **Scrapes** 33,000+ IC components from DigiKey using Playwright + Edge
2. **Stores** all parametric specs in a local SQLite database
3. **Finds alternatives** by comparing 8–13 electrical specs per category
4. **Parses datasheets** (PDF) to extract specs not in DigiKey's table (PSRR, dropout, noise, etc.)
5. **Serves an HTTP API** via FastAPI for a separate client application

```
User enters: MIC5501-3.0YM5-TR
      ↓
  1. Lookup in database → Category: LDO, 3.0V, 300mA, SOT-23-5
  2. Load 13 LDO-specific matching rules
  3. Score 1,700 LDO candidates on ALL electrical specs
  4. Return ranked alternatives with per-spec breakdown
      ↓
  #1  TLV73330PDBVR  80.8% compatible [DROP-IN]
  #2  TLV74330PDBVR  80.8% compatible [DROP-IN]
  #3  TPS73630DBVR   72.0% compatible
```

## Quick Start

```bash
# 1. Install Python dependencies
python -m pip install -r requirements.txt

# 2. Install Playwright browser
python -m playwright install msedge

# 3. Scrape one category (test)
python main.py scrape --category ldo_ic --max-pages 2

# 4. Check what was collected
python main.py status

# 5. Find alternatives for a part
python finder_cli.py find MIC5501-3.0YM5-TR

# 6. Export to Excel
python export_csv.py

# 7. Start the API
python -m uvicorn api:app --reload --port 8000
```

For deployment roles, supported maintenance workflows, and data locations, see
[DEPLOYMENT.md](DEPLOYMENT.md).

## Scraping

```bash
# Scrape one category
python main.py scrape --category ldo_ic --max-pages 20

# Scrape all 22 categories
python main.py scrape --all --max-pages 20

# Check progress
python main.py status

# Export to CSV (Excel)
python export_csv.py

# List all categories
python main.py categories
```

**Tips:**
- Ctrl+C stops gracefully (saves what it has)
- Data saves after each subcategory — no progress lost on crash
- Re-running the same category adds new parts without duplicates
- Always run `python export_csv.py` after scraping as a CSV backup

## Finding Alternatives

```bash
# Look up a part and see all specs
python finder_cli.py lookup MIC5501-3.0YM5-TR

# Find compatible alternatives ranked by compatibility %
python finder_cli.py find MIC5501-3.0YM5-TR

# Same-package only (drop-in replacements)
python finder_cli.py find MIC5501-3.0YM5-TR --same-package

# Compare two parts side-by-side
python finder_cli.py compare MIC5501-3.0YM5-TR AP2112K-3.3TRG1

# Compare pinouts (downloads datasheets)
python finder_cli.py pinout MIC5501-3.0YM5-TR AP2112K-3.3TRG1

# Search by keyword
python finder_cli.py search LDO 3.3V

# Interactive mode
python finder_cli.py interactive
```

## API

```bash
# Start FastAPI backend
python -m uvicorn api:app --reload --port 8000

# API docs
http://localhost:8000/docs

# Key endpoints
GET /api/search?q=MIC5501
GET /api/lookup/MIC5501-3.0YM5-TR
GET /api/alternatives/MIC5501-3.0YM5-TR
GET /api/compare?mpn1=MIC5501-3.0YM5-TR&mpn2=AP2112K-3.3TRG1
GET /api/dashboard
GET /api/categories
```

This repository does not include a React frontend. Connect a separate client
to the API endpoints above if a browser UI is required.

## LLM Datasheet Enrichment

The enrichment path uses NVIDIA NIM with
`meta/llama-3.1-8b-instruct` through the OpenAI-compatible endpoint. Copy
`.env.example` to `.env` and set `NVIDIA_API_KEY`; do not commit `.env`.

The LLM output is limited to specs recognised by `match_rules.py`, then checked
against unit-aware sanity ranges. The regex parser fills recognised fields that
the LLM did not return. This is a safeguard, not an accuracy guarantee; see
`SCRAPER_ACCURACY_REPORT.md` for the current measured coverage and limitations.

## Component Categories (22)

| Category | Description | Specs Compared |
|---|---|---|
| DC-DC Converter | Buck, boost, buck-boost regulators | Vin, Vout, Iout, efficiency, fSW, topology |
| LDO Regulator | Linear low-dropout regulators | Vout, Iout, dropout, Iq, PSRR, output type |
| Gate Driver | MOSFET/IGBT gate drivers | Vsupply, peak current, rise/fall time |
| Power Sequencer | Voltage supervisors, power management | Threshold, outputs, reset type |
| Battery Management | Battery charger/BMS ICs | Chemistry, cells, charge current |
| USB IC | USB Type-C, PD controllers | Protocol, data rate, ports, ESD |
| Video Interface | HDMI/DP/LVDS transceivers | Protocol, data rate, channels |
| Serial Interface | UART/SPI/I2C controllers | Protocol, data rate, channels |
| Display Driver | LED/LCD/OLED backlight drivers | Topology, current, dimming |
| TCON / Video Processor | Timing controllers, scalers | Type, interface, resolution |
| Flash Memory | NOR/NAND flash | Size, interface, speed, endurance |
| EEPROM | Serial EEPROM | Size, interface, write cycle time |
| FRAM / MRAM / SRAM | Non-volatile RAM | Size, type, interface, endurance |
| Audio IC | Codecs, amplifiers, Class-D | THD+N, SNR, channels, output power |
| Ambient Light Sensor | ALS and proximity sensors | Range, interface, PSRR |
| Temperature Sensor | Digital/analog temp sensors | Accuracy, resolution, interface |
| Hall Effect Sensor | Magnetic sensors | Sensitivity, output type |
| Protection IC | TVS/ESD, OVP, current limiters | Clamping V, breakdown V, IPP |
| Clock & Timing | PLLs, oscillators, clock generators | Frequency, jitter, outputs |
| Logic / MUX | Level shifters, muxes, switches | RON, bandwidth, propagation delay |
| MCU / SoC | ARM Cortex-M, RISC-V MCUs | Core, speed, flash, RAM, I/O |
| Retimer / Redriver | HDMI/DP/USB retimers | Protocol, data rate, jitter |
| Opto IC | Optocouplers, optoisolators | CTR, isolation voltage, timing |

## How Scoring Works

```
Target: MIC5501-3.0YM5-TR (LDO 3.0V 300mA)

For each candidate in the same category:
  ┌─────────────────────────────────┬────────┬──────────────┐
  │ Spec                            │ Weight │ Match Type   │
  ├─────────────────────────────────┼────────┼──────────────┤
  │ *Voltage Output (required)      │  10    │ ±3%          │
  │ *Current Output (required)      │   9    │ ≥ target     │
  │  Voltage Input Max              │   8    │ ≥ target     │
  │  Dropout Voltage                │   7    │ ±30%         │
  │  Quiescent Current              │   5    │ ±50%         │
  │  PSRR                           │   4    │ ≥ target     │
  │  Output Type                    │   6    │ exact        │
  │  Number of Regulators           │   6    │ exact        │
  │  Package match                  │   8    │ exact/family │
  │  Temperature range              │   4    │ covers       │
  │  Lifecycle (Active)             │   3    │ exact        │
  └─────────────────────────────────┴────────┴──────────────┘

  * = required. If a required spec fails → candidate disqualified.

  Score = sum(matched_spec_points) / sum(max_possible) × 100%
  Missing specs score 0 (not inflated).
  Stock and price do NOT affect scoring — purely technical.
```

## Project Structure

```
AutoScraper1/
├── config.py                  # Categories, DigiKey URLs, settings
├── database.py                # SQLite manager (components, specs, substitutes)
├── engine.py                  # Scrape orchestrator with Ctrl+C handling
├── main.py                    # CLI entry point (scrape, status, search)
├── models.py                  # Component dataclass
├── finder.py                  # Alternative finder engine
├── finder_cli.py              # Finder CLI (lookup, find, compare, pinout)
├── match_rules.py             # Category-specific weighted matching rules
├── spec_parser.py             # Numeric value extraction from spec strings
├── api.py                     # FastAPI backend
├── export_csv.py              # Export database to Excel CSV
├── requirements.txt           # Python dependencies
├── README.md                  # This file
├── ic_database.db             # SQLite database (generated by scraper)
│
├── plugins/                   # Scraper data sources
│   ├── __init__.py
│   ├── base.py                # Abstract plugin interface
│   ├── digikey_playwright.py  # Playwright + Edge scraper (primary)
│   ├── digikey_curl.py        # curl_cffi fallback scraper
│   └── csv_import.py          # Manual CSV import
│
├── finder_extras/             # Finder enhancements
│   ├── __init__.py
│   ├── datasheet_parser.py    # PDF datasheet spec + pinout extraction
│   ├── cross_category.py      # Cross-category alternative search
│   ├── pin_compat.py          # Pin compatibility checking
│   ├── spec_normalizer.py     # Spec name normalization
│   ├── protocol_matcher.py    # Protocol version matching
│   └── lifecycle_filter.py    # Lifecycle status filtering
│
├── utils/                     # Scraper utilities
│   ├── __init__.py
│   ├── rate_limiter.py        # Adaptive request rate limiting
│   ├── memory_classifier.py   # Memory IC sub-classification
│   ├── deduplicator.py        # Cross-category deduplication
│   ├── price_parser.py        # Price break parsing
│   ├── incremental.py         # Stale category detection
│   └── substitutes_scraper.py # DigiKey suggested alternatives
│
├── downloads/                 # Datasheet PDFs (auto-downloaded)
└── exports/                   # CSV exports for Excel
```

## Database Schema

```sql
-- Main component table
components (
    id, manufacturer_part_number, manufacturer, description,
    category, subcategory, datasheet_url, product_url,
    stock, unit_price, package, mounting_type,
    lifecycle_status, source, scraped_at
)

-- Flexible key-value parametric specs
specifications (
    id, component_id, spec_name, spec_value
)

-- Cross-reference substitute parts
substitutes (
    id, component_id, substitute_part_number, compatibility_notes
)
```

## Configuration

Edit `config.py` to change:
- `HEADLESS_MODE` — `True` for background, `False` to see the browser
- `REQUEST_DELAY_SECONDS` — delay between page loads (default 1.0s)
- `MAX_RETRIES` — retries per page on error (default 3)
- `DB_PATH` — database file location

## Notes

- **No stock/price in scoring** — compatibility is purely technical
- **Datasheet enrichment** extracts PSRR, dropout, noise, etc. from PDFs
- **NVIDIA NIM** uses `meta/llama-3.1-8b-instruct`; set `NVIDIA_API_KEY` in `.env`
- **Pin comparison** validates against package pin count (SOT-23-5 → max 5 pins)
- **Ctrl+C** stops gracefully — data saves after each subcategory
- **Re-running** the same category adds new parts without duplicates
- The `ic_database.db` file is ~60 MB — add to `.gitignore` for GitHub
