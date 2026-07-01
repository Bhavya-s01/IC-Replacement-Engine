# IC Database & Ingestion Engine

Automated scraper that collects IC component data from DigiKey across **11 IC categories** and stores it in a local SQLite database for parametric comparison and substitute finding.

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Install Playwright browsers (uses your system's Edge)
playwright install

# 3. List available categories
python main.py categories

# 4. Scrape Power ICs (first 2 pages per sub-category as a test)
python main.py scrape --category power_ic --max-pages 2

# 5. Scrape ALL 11 categories (full run)
python main.py scrape --all

# 6. Check database status
python main.py status

# 7. Search
python main.py search --category power_ic --keyword "LDO" --limit 10

# 8. Compare two parts
python main.py compare LM1117 AMS1117

# 9. Search by specification
python main.py search -c power_ic -s "Voltage - Output (Min/Fixed)=3.3V"
```

## Fallback: curl_cffi

If Playwright doesn't work (e.g. no Edge, no display server):

```bash
pip install curl_cffi
python main.py scrape --category power_ic --plugin digikey_curl
```

## Fallback: Manual CSV Import

1. Download table data manually from DigiKey
2. Save as `imports/power_ic_export.csv`
3. Run:

```bash
python main.py import-csv --category power_ic --directory imports
```

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                    main.py (CLI)                     │
├─────────────────────────────────────────────────────┤
│                 engine.py (Orchestrator)              │
├────────────┬────────────┬────────────┬──────────────┤
│ Playwright │  curl_cffi │ CSV Import │  (future…)   │
│   Plugin   │   Plugin   │   Plugin   │  Mouser/LCSC │
├────────────┴────────────┴────────────┴──────────────┤
│              database.py  →  ic_database.db          │
│         components | specifications | substitutes    │
└─────────────────────────────────────────────────────┘
```

## 11 IC Categories

| Slug            | Name           | Description                                |
|-----------------|----------------|--------------------------------------------|
| `power_ic`      | Power IC       | LDOs, DC-DC, PMICs, gate/LED drivers       |
| `memory_ic`     | Memory IC      | SRAM, DRAM, SDRAM, FIFO                    |
| `flash_ic`      | Flash IC       | NOR, NAND, EEPROM, serial flash            |
| `scalar_ic`     | Scalar IC      | MCUs, MPUs, DSPs, FPGAs                    |
| `audio_ic`      | Audio IC       | Codecs, amplifiers, Class-D                |
| `usb_ic`        | USB IC         | Controllers, hubs, Type-C PD               |
| `sensor_ic`     | Sensor IC      | Temp, pressure, IMU, hall, current          |
| `protection_ic` | Protection IC  | ESD, TVS, supervisors, eFuses              |
| `mux_logic_ic`  | MUX/Logic IC   | MUXes, gates, buffers, level shifters       |
| `ethernet_ic`   | Ethernet IC    | PHYs, MACs, controllers, switches           |
| `opto_ic`       | Opto IC        | Optocouplers (transistor/triac/logic/gate)   |

## Database Schema

- **`components`** — common fields (MPN, manufacturer, price, stock, package…)
- **`specifications`** — flexible key-value parametric data per component
- **`substitutes`** — cross-reference table for substitute parts

All parametric columns from DigiKey are preserved in the `specifications` table,
enabling queries like: *"Find all LDOs with Vout = 3.3V and Iq < 10µA"*.