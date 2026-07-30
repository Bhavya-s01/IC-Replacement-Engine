"""
enrich_template_parts.py — Extract specs from datasheets using LLM parser.
Passes datasheet URL (not file path) to the parser so it can download + parse.

Run:
  $env:NVIDIA_API_KEY = "nvapi-YOUR-KEY"
  python enrich_template_parts.py --limit 20
"""

import sqlite3
import os
import logging
import argparse

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s | %(levelname)-7s | %(message)s")
log = logging.getLogger("enrich")

import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

DB_PATH = "ic_database.db"


def enrich_parts(limit=20):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    # Find parts with datasheet URLs but not yet enriched
    parts = conn.execute("""
        SELECT c.id, c.manufacturer_part_number, c.datasheet_url,
               c.package, c.category
        FROM components c
        WHERE c.datasheet_url IS NOT NULL
          AND c.datasheet_url != ''
          AND c.id NOT IN (
              SELECT component_id FROM specifications
              WHERE spec_name = '_enriched'
          )
        ORDER BY c.id DESC
        LIMIT ?
    """, (limit,)).fetchall()

    log.info("Found %d parts to enrich", len(parts))

    if not parts:
        log.info("All parts already enriched or no datasheet URLs available")
        conn.close()
        return

    # Load parser — prefer LLM, fall back to regex
    parser = None
    parser_type = "unknown"

    try:
        from finder_extras.llm_parser import LLMDatasheetParser
        parser = LLMDatasheetParser()
        parser_type = "LLM (NVIDIA NIM)"
        log.info("Using LLM parser (NVIDIA NIM)")
    except ImportError:
        pass

    if parser is None:
        try:
            from finder_extras.datasheet_parser import DatasheetParser
            parser = DatasheetParser()
            parser_type = "Regex"
            log.info("Using regex parser (set NVIDIA_API_KEY for LLM)")
        except ImportError:
            log.error("No parser available")
            conn.close()
            return

    enriched = 0

    for part in parts:
        mpn = part["manufacturer_part_number"]
        url = part["datasheet_url"]
        pkg = part["package"] or ""
        cat = part["category"] or ""
        comp_id = part["id"]

        log.info("Enriching: %s", mpn)
        log.info("  URL: %s", url[:80] if url else "None")

        try:
            # Pass the DATASHEET URL — not a file path
            # The parser downloads the PDF itself
            specs, pinout = parser.parse_datasheet(
                url, mpn, package=pkg, category=cat
            )

            if specs:
                count = 0
                for name, value in specs.items():
                    existing = conn.execute(
                        "SELECT 1 FROM specifications "
                        "WHERE component_id = ? AND spec_name = ?",
                        (comp_id, name)
                    ).fetchone()
                    if not existing:
                        conn.execute(
                            "INSERT INTO specifications "
                            "(component_id, spec_name, spec_value) "
                            "VALUES (?, ?, ?)",
                            (comp_id, name, str(value))
                        )
                        count += 1

                conn.execute(
                    "INSERT OR REPLACE INTO specifications "
                    "(component_id, spec_name, spec_value) "
                    "VALUES (?, '_enriched', '1')",
                    (comp_id,)
                )
                conn.commit()
                enriched += 1
                log.info("  Extracted %d specs for %s", count, mpn)
                for k, v in specs.items():
                    log.info("    %s: %s", k, v)
            else:
                # Mark as enriched (attempted) so we don't retry
                conn.execute(
                    "INSERT OR REPLACE INTO specifications "
                    "(component_id, spec_name, spec_value) "
                    "VALUES (?, '_enriched', '0')",
                    (comp_id,)
                )
                conn.commit()
                log.info("  No specs extracted for %s", mpn)

        except Exception as e:
            log.warning("  Failed for %s: %s", mpn, e)
            conn.execute(
                "INSERT OR REPLACE INTO specifications "
                "(component_id, spec_name, spec_value) "
                "VALUES (?, '_enriched', 'error')",
                (comp_id,)
            )
            conn.commit()

    log.info("=== RESULTS ===")
    log.info("Parser: %s", parser_type)
    log.info("Processed: %d parts", len(parts))
    log.info("Enriched with specs: %d", enriched)

    overlap = conn.execute(
        "SELECT COUNT(DISTINCT sc.mpn) FROM supply_chain sc "
        "INNER JOIN components c ON c.manufacturer_part_number = sc.mpn"
    ).fetchone()[0]
    log.info("Overlap with supply chain: %d parts", overlap)

    conn.close()


if __name__ == "__main__":
    p = argparse.ArgumentParser(
        description="Extract specs from datasheets using LLM parser"
    )
    p.add_argument("--limit", type=int, default=20)
    args = p.parse_args()
    enrich_parts(limit=args.limit)