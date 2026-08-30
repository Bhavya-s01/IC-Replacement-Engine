"""
enrich_all.py — Enrich supply chain parts using LLM only (no regex).
Validates extracted specs against expected ranges.

Run:
  $env:GROQ_API_KEY = "gsk_YOUR-KEY"        (fastest, tried first)
  $env:GEMINI_API_KEY = "AIza-YOUR-KEY"     (accuracy fallback)
  $env:NVIDIA_API_KEY = "nvapi-YOUR-KEY"    (last resort)
  python enrich_all.py --phase supply_chain
  python enrich_all.py --phase category --cat ldo_ic
"""

import sqlite3
import os
import time
import logging
import argparse
import json
import requests

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s | %(levelname)-7s | %(message)s")
log = logging.getLogger("enrich_all")

import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

DB_PATH = "ic_database.db"

# ════════════════════════════════════════════
# SPEC VALIDATION — catches garbage values
# ════════════════════════════════════════════
# These names must match the canonical names used by match_rules and the
# active LLM validation layer; keep the keys in sync with the current data model.

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
        from finder_extras.llm_parser import _validate_spec
        valid, error = _validate_spec(name, str(value))
        if not valid:
            log.warning("  INVALID %s = %s (%s)", name, value, error)
        return valid
    except ImportError:
        rule = VALIDATION_RULES.get(name)
        if not rule:
            return True
        try:
            num = float(str(value).replace(",", ""))
        except (ValueError, TypeError):
            return True
        return rule["min"] <= num <= rule["max"]


def _rule_spec_names(category):
    from match_rules import get_rules
    names = []
    for rule in get_rules(category or "").rules:
        names.append((rule.spec_name, [rule.spec_name] + list(rule.aliases), rule.required))
    return names


def _missing_required_specs(conn, component_id, category):
    rows = conn.execute(
        "SELECT spec_name, spec_value FROM specifications "
        "WHERE component_id = ? AND spec_name NOT LIKE '\\_%' ESCAPE '\\'",
        (component_id,),
    ).fetchall()
    specs = {row[0]: str(row[1] or "").strip() for row in rows}
    missing = []
    for canonical, names, required in _rule_spec_names(category):
        if required and not any(specs.get(name) not in (None, "", "-", "N/A") for name in names):
            missing.append(canonical)
    return missing


def _verify_datasheet_url(url):
    """Return (ok, reason) for a reachable PDF/HTML datasheet URL."""
    try:
        response = requests.get(
            url,
            timeout=20,
            verify=False,
            headers={"User-Agent": "Mozilla/5.0"},
            stream=True,
        )
        content_type = response.headers.get("content-type", "").lower()
        is_pdf = response.content[:5] == b"%PDF-"
        is_html = "html" in content_type or response.text[:100].lower().find("<html") >= 0
        if response.status_code >= 400:
            return False, "HTTP {}".format(response.status_code)
        if not (is_pdf or is_html):
            return False, "unexpected content type {}".format(content_type or "unknown")
        return True, "{} {}".format(response.status_code, "pdf" if is_pdf else "html")
    except Exception as exc:
        return False, str(exc).splitlines()[0][:120]


def _reset_component_enrichment(conn, component_id):
    """Remove parser-owned rows when metadata identifies exactly what it wrote."""
    metadata = conn.execute(
        "SELECT spec_value FROM specifications "
        "WHERE component_id = ? AND spec_name = '_validation' "
        "ORDER BY id DESC LIMIT 1",
        (component_id,),
    ).fetchone()
    if metadata:
        try:
            names = json.loads(metadata[0]).get("stored_specs", [])
            if names:
                placeholders = ",".join("?" for _ in names)
                conn.execute(
                    "DELETE FROM specifications WHERE component_id = ? "
                    "AND spec_name IN ({})".format(placeholders),
                    [component_id] + names,
                )
        except (TypeError, ValueError, json.JSONDecodeError):
            log.warning("Could not read validation metadata for component %s", component_id)
    conn.execute(
        "DELETE FROM specifications WHERE component_id = ? "
        "AND spec_name IN ('_enriched', '_validation')",
        (component_id,),
    )


def reset_invalid_enrichment():
    """Reset successful markers that fail required rules or URL verification."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("""
        SELECT DISTINCT c.id, c.manufacturer_part_number, c.category, c.datasheet_url
        FROM components c
        JOIN specifications s ON s.component_id = c.id
        WHERE s.spec_name = '_enriched' AND s.spec_value = '1'
    """).fetchall()
    reset = []
    for row in rows:
        missing = _missing_required_specs(conn, row["id"], row["category"])
        url_ok, url_reason = _verify_datasheet_url(row["datasheet_url"] or "") if row["datasheet_url"] else (False, "no URL")
        real_specs = conn.execute(
            "SELECT COUNT(*) FROM specifications WHERE component_id = ? "
            "AND spec_name NOT LIKE '\\_%' ESCAPE '\\'",
            (row["id"],),
        ).fetchone()[0]
        reasons = []
        if missing:
            reasons.append("missing required: " + ", ".join(missing))
        if real_specs == 0:
            reasons.append("no extracted specs")
        if not url_ok:
            reasons.append("datasheet URL: " + url_reason)
        if reasons:
            _reset_component_enrichment(conn, row["id"])
            reset.append((row["id"], row["manufacturer_part_number"], "; ".join(reasons)))
    conn.commit()
    conn.close()
    print("Reset {} components".format(len(reset)))
    for component_id, mpn, reason in reset:
        print("{} {}: {}".format(component_id, mpn, reason))


def get_llm_parser():
    """Load the parser, allowing its deterministic fallback when no LLM exists."""
    try:
        # Import first: llm_parser loads the project-local .env file.
        from finder_extras.llm_parser import (
            LLMDatasheetParser, GROQ_API_KEY, GEMINI_API_KEY, NVIDIA_API_KEY,
        )
        parser = LLMDatasheetParser()
        if GROQ_API_KEY:
            provider = "Groq"
        elif GEMINI_API_KEY:
            provider = "Gemini"
        elif NVIDIA_API_KEY:
            provider = "NVIDIA NIM"
        else:
            provider = None

        if provider:
            log.info("LLM parser loaded (%s)", provider)
        else:
            log.warning(
                "No LLM credentials configured; using deterministic datasheet parser. "
                "Incomplete parts remain queued for later LLM enrichment."
            )
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
    stored_names = []
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
            stored_names.append(name)

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
            "stored_specs": stored_names
        }))
    )

    missing_required = _missing_required_specs(conn, comp_id, category)
    if missing_required:
        conn.execute(
            "INSERT OR REPLACE INTO specifications "
            "(component_id, spec_name, spec_value) VALUES (?, '_enriched', '0')",
            (comp_id,),
        )
        log.warning(
            "  %s: incomplete enrichment; missing required specs: %s",
            mpn, ", ".join(missing_required),
        )
        conn.commit()
        return 0

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
        SELECT DISTINCT c.id, c.manufacturer_part_number, c.datasheet_url,
               c.package, c.category
        FROM components c
        INNER JOIN supply_chain sc ON upper(trim(sc.mpn)) = upper(trim(c.manufacturer_part_number))
        WHERE c.datasheet_url IS NOT NULL
          AND c.datasheet_url != ''
          AND c.id NOT IN (
              SELECT component_id FROM specifications
              WHERE spec_name = '_enriched'
                AND spec_value IN ('1', '0', 'error')
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
              WHERE spec_name = '_enriched'
                AND spec_value IN ('1', '0', 'error')
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
    p.add_argument("--phase", choices=["supply_chain", "category", "reset_invalid", "stats"],
                   default="stats")
    p.add_argument("--cat", type=str, default="ldo_ic",
                   help="Category to enrich (for --phase category)")
    p.add_argument("--limit", type=int, default=999)
    args = p.parse_args()

    if args.phase == "supply_chain":
        enrich_supply_chain(limit=args.limit)
    elif args.phase == "category":
        enrich_category(args.cat, limit=args.limit)
    elif args.phase == "reset_invalid":
        reset_invalid_enrichment()
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
            INNER JOIN supply_chain sc ON upper(trim(sc.mpn)) = upper(trim(c.manufacturer_part_number))
            INNER JOIN specifications s ON s.component_id = c.id
            WHERE s.spec_name = '_enriched' AND s.spec_value = '1'
        """).fetchone()[0]
        sc_total = conn.execute("""
            SELECT COUNT(DISTINCT sc.mpn) FROM supply_chain sc
            INNER JOIN components c ON upper(trim(c.manufacturer_part_number)) = upper(trim(sc.mpn))
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
