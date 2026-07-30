"""
enrich_all.py — Enrich supply chain parts using LLM only (no regex).
Validates extracted specs against expected ranges.

Run:
  $env:NVIDIA_API_KEY = "nvapi-YOUR-KEY"
  python enrich_all.py --phase supply_chain
  python enrich_all.py --phase category --cat ldo_ic
"""

import sqlite3
import os
import time
import logging
import argparse
import json

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s | %(levelname)-7s | %(message)s")
log = logging.getLogger("enrich_all")

import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

DB_PATH = "ic_database.db"

# ════════════════════════════════════════════
# SPEC VALIDATION — catches garbage values
# ════════════════════════════════════════════

VALIDATION_RULES = {
    "Input Voltage Max":        {"min": 0.5,   "max": 200,    "unit": "V"},
    "Input Voltage Min":        {"min": 0.1,   "max": 100,    "unit": "V"},
    "Output Voltage":           {"min": 0.1,   "max": 100,    "unit": "V"},
    "Output Current Max":       {"min": 0.001, "max": 50000,  "unit": "mA"},
    "Dropout Voltage":          {"min": 1,     "max": 5000,   "unit": "mV"},
    "PSRR":                     {"min": 10,    "max": 120,    "unit": "dB"},
    "Quiescent Current / Ground Current": {"min": 0.01, "max": 100000, "unit": "µA"},
    "Load Regulation":          {"min": 0.001, "max": 500,    "unit": "mV"},
    "Line Regulation":          {"min": 0.001, "max": 50,     "unit": "%/V"},
    "Output Noise RMS":         {"min": 0.1,   "max": 10000,  "unit": "µV"},
    "Current Limit":            {"min": 1,     "max": 50000,  "unit": "mA"},
    "Enable Threshold Voltage": {"min": 0.1,   "max": 10,     "unit": "V"},
    "Soft Start Time":          {"min": 0.01,  "max": 10000,  "unit": "ms"},
    "Thermal Shutdown Temperature": {"min": 80, "max": 200,   "unit": "°C"},
    "Thermal Resistance JA":    {"min": 1,     "max": 1000,   "unit": "°C/W"},
    "ESD Rating HBM":           {"min": 0.1,   "max": 30,     "unit": "kV"},
    "Switching Frequency":      {"min": 10,    "max": 10000,  "unit": "kHz"},
    "Efficiency Peak":          {"min": 50,    "max": 99.9,   "unit": "%"},
    "THD+N":                    {"min": 0.0001,"max": 10,     "unit": "%"},
    "SNR":                      {"min": 30,    "max": 140,    "unit": "dB"},
}


def validate_spec(name, value):
    """Check if a spec value is within reasonable range. Returns True if valid."""
    try:
        num = float(str(value).replace(",", ""))
    except (ValueError, TypeError):
        return True  # non-numeric specs are OK (e.g., "Fixed", "Positive")

    rule = VALIDATION_RULES.get(name)
    if not rule:
        return True  # no rule = accept

    if num < rule["min"] or num > rule["max"]:
        log.warning("  INVALID %s = %s (expected %s-%s %s)",
                     name, value, rule["min"], rule["max"], rule["unit"])
        return False
    return True


def get_llm_parser():
    """Load LLM parser only — no regex fallback."""
    api_key = os.environ.get("NVIDIA_API_KEY", "")
    if not api_key:
        log.error("Set NVIDIA_API_KEY: $env:NVIDIA_API_KEY = 'nvapi-YOUR-KEY'")
        return None

    try:
        from finder_extras.llm_parser import LLMDatasheetParser
        parser = LLMDatasheetParser()
        log.info("LLM parser loaded (NVIDIA NIM)")
        return parser
    except ImportError as e:
        log.error("Cannot import LLMDatasheetParser: %s", e)
        return None


def enrich_part(conn, parser, comp_id, mpn, url, package, category):
    """Enrich one part: download → LLM extract → validate → store."""

    if not url:
        log.info("  %s: no datasheet URL, skipping", mpn)
        return 0

    log.info("  Enriching: %s (%s)", mpn, category)

    try:
        specs, pinout = parser.parse_datasheet(url, mpn, package=package, category=category)
    except Exception as e:
        log.warning("  %s: LLM failed: %s", mpn, str(e)[:60])
        conn.execute(
            "INSERT OR REPLACE INTO specifications "
            "(component_id, spec_name, spec_value) VALUES (?, '_enriched', 'error')",
            (comp_id,)
        )
        conn.commit()
        return 0

    if not specs:
        conn.execute(
            "INSERT OR REPLACE INTO specifications "
            "(component_id, spec_name, spec_value) VALUES (?, '_enriched', '0')",
            (comp_id,)
        )
        conn.commit()
        log.info("  %s: no specs extracted", mpn)
        return 0

    # Validate and store
    stored = 0
    rejected = 0
    for name, value in specs.items():
        if not validate_spec(name, value):
            rejected += 1
            continue

        existing = conn.execute(
            "SELECT 1 FROM specifications WHERE component_id = ? AND spec_name = ?",
            (comp_id, name)
        ).fetchone()
        if not existing:
            conn.execute(
                "INSERT INTO specifications (component_id, spec_name, spec_value) VALUES (?, ?, ?)",
                (comp_id, name, str(value))
            )
            stored += 1

    # Mark as enriched
    conn.execute(
        "INSERT OR REPLACE INTO specifications "
        "(component_id, spec_name, spec_value) VALUES (?, '_enriched', '1')",
        (comp_id,)
    )

    # Store validation metadata
    conn.execute(
        "INSERT OR REPLACE INTO specifications "
        "(component_id, spec_name, spec_value) VALUES (?, '_validation', ?)",
        (comp_id, json.dumps({
            "extracted": len(specs),
            "stored": stored,
            "rejected": rejected,
            "specs": list(specs.keys())
        }))
    )

    conn.commit()
    log.info("  %s: stored %d specs, rejected %d", mpn, stored, rejected)
    return stored


def enrich_supply_chain(limit=999):
    """Enrich all supply chain parts that have datasheet URLs."""
    parser = get_llm_parser()
    if not parser:
        return

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    parts = conn.execute("""
        SELECT c.id, c.manufacturer_part_number, c.datasheet_url,
               c.package, c.category
        FROM components c
        INNER JOIN supply_chain sc ON sc.mpn = c.manufacturer_part_number
        WHERE c.datasheet_url IS NOT NULL
          AND c.datasheet_url != ''
          AND c.id NOT IN (
              SELECT component_id FROM specifications
              WHERE spec_name = '_enriched' AND spec_value = '1'
          )
        LIMIT ?
    """, (limit,)).fetchall()

    log.info("Supply chain parts to enrich: %d", len(parts))

    enriched = 0
    total_specs = 0
    start = time.time()

    for i, part in enumerate(parts):
        n = enrich_part(
            conn, parser, part["id"],
            part["manufacturer_part_number"],
            part["datasheet_url"],
            part["package"] or "",
            part["category"] or ""
        )
        if n > 0:
            enriched += 1
            total_specs += n

        # Progress
        elapsed = time.time() - start
        rate = (i + 1) / elapsed if elapsed > 0 else 0
        remaining = (len(parts) - i - 1) / rate if rate > 0 else 0
        if (i + 1) % 5 == 0:
            log.info("Progress: %d/%d (%.0f%%) — %d enriched, ~%.0f min remaining",
                     i + 1, len(parts), (i + 1) * 100 / len(parts),
                     enriched, remaining / 60)

    log.info("=== SUPPLY CHAIN ENRICHMENT COMPLETE ===")
    log.info("Processed: %d parts", len(parts))
    log.info("Enriched: %d parts with %d total specs", enriched, total_specs)
    log.info("Time: %.1f minutes", (time.time() - start) / 60)

    conn.close()


def enrich_category(category, limit=999):
    """Enrich all parts in a specific category."""
    parser = get_llm_parser()
    if not parser:
        return

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    parts = conn.execute("""
        SELECT c.id, c.manufacturer_part_number, c.datasheet_url,
               c.package, c.category
        FROM components c
        WHERE c.category = ?
          AND c.datasheet_url IS NOT NULL
          AND c.datasheet_url != ''
          AND c.id NOT IN (
              SELECT component_id FROM specifications
              WHERE spec_name = '_enriched' AND spec_value = '1'
          )
        LIMIT ?
    """, (category, limit)).fetchall()

    log.info("Category '%s' parts to enrich: %d", category, len(parts))

    enriched = 0
    total_specs = 0
    start = time.time()

    for i, part in enumerate(parts):
        n = enrich_part(
            conn, parser, part["id"],
            part["manufacturer_part_number"],
            part["datasheet_url"],
            part["package"] or "",
            part["category"] or ""
        )
        if n > 0:
            enriched += 1
            total_specs += n

        if (i + 1) % 10 == 0:
            elapsed = time.time() - start
            rate = (i + 1) / elapsed if elapsed > 0 else 0
            remaining = (len(parts) - i - 1) / rate if rate > 0 else 0
            log.info("Progress: %d/%d — %d enriched, ~%.0f min remaining",
                     i + 1, len(parts), enriched, remaining / 60)

    log.info("=== CATEGORY ENRICHMENT COMPLETE ===")
    log.info("Category: %s", category)
    log.info("Processed: %d, Enriched: %d, Specs: %d", len(parts), enriched, total_specs)
    log.info("Time: %.1f minutes", (time.time() - start) / 60)

    conn.close()


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--phase", choices=["supply_chain", "category", "stats"],
                   default="stats")
    p.add_argument("--cat", type=str, default="ldo_ic",
                   help="Category to enrich (for --phase category)")
    p.add_argument("--limit", type=int, default=999)
    args = p.parse_args()

    if args.phase == "supply_chain":
        enrich_supply_chain(limit=args.limit)
    elif args.phase == "category":
        enrich_category(args.cat, limit=args.limit)
    elif args.phase == "stats":
        conn = sqlite3.connect(DB_PATH)
        total = conn.execute("SELECT COUNT(*) FROM components").fetchone()[0]
        has_ds = conn.execute(
            "SELECT COUNT(*) FROM components WHERE datasheet_url IS NOT NULL AND datasheet_url != ''"
        ).fetchone()[0]
        enriched = conn.execute(
            "SELECT COUNT(DISTINCT component_id) FROM specifications WHERE spec_name = '_enriched' AND spec_value = '1'"
        ).fetchone()[0]
        failed = conn.execute(
            "SELECT COUNT(DISTINCT component_id) FROM specifications WHERE spec_name = '_enriched' AND spec_value IN ('0', 'error')"
        ).fetchone()[0]
        sc_enriched = conn.execute("""
            SELECT COUNT(DISTINCT c.id) FROM components c
            INNER JOIN supply_chain sc ON sc.mpn = c.manufacturer_part_number
            INNER JOIN specifications s ON s.component_id = c.id
            WHERE s.spec_name = '_enriched' AND s.spec_value = '1'
        """).fetchone()[0]
        sc_total = conn.execute("""
            SELECT COUNT(DISTINCT sc.mpn) FROM supply_chain sc
            INNER JOIN components c ON c.manufacturer_part_number = sc.mpn
        """).fetchone()[0]

        cats = conn.execute("""
            SELECT c.category, COUNT(*) as total,
                   SUM(CASE WHEN s.spec_value = '1' THEN 1 ELSE 0 END) as enriched
            FROM components c
            LEFT JOIN specifications s ON s.component_id = c.id AND s.spec_name = '_enriched'
            GROUP BY c.category
            ORDER BY total DESC
        """).fetchall()

        print("=== ENRICHMENT STATUS ===")
        print("Total components:     {:>6}".format(total))
        print("Have datasheet URL:   {:>6}".format(has_ds))
        print("LLM enriched:         {:>6}".format(enriched))
        print("Failed/no specs:      {:>6}".format(failed))
        print("Not attempted:        {:>6}".format(total - enriched - failed))
        print("Supply chain enriched: {}/{} ({:.0f}%)".format(
            sc_enriched, sc_total, sc_enriched * 100 / sc_total if sc_total else 0))
        print("")
        print("{:<25} {:>6} {:>8} {:>6}".format("Category", "Total", "Enriched", "%"))
        print("-" * 50)
        for cat, t, e in cats:
            e = e or 0
            pct = e * 100 // t if t else 0
            print("{:<25} {:>6} {:>8} {:>5}%".format(cat or "(none)", t, e, pct))

        conn.close()