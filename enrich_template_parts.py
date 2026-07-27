"""
enrich_template_parts.py — Download datasheets for template parts
and extract specs using the LLM parser, storing in specifications table.

Run: python enrich_template_parts.py --limit 20
"""

import sqlite3
import os
import re
import logging
import argparse

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s | %(levelname)-7s | %(message)s")
log = logging.getLogger("enrich")

DB_PATH = "ic_database.db"
DATASHEET_DIR = "datasheets"


def download_pdf(url, mpn):
    """Download a datasheet PDF to datasheets/ folder."""
    import requests
    os.makedirs(DATASHEET_DIR, exist_ok=True)
    safe_name = re.sub(r'[^\w\-.]', '_', mpn)
    filepath = os.path.join(DATASHEET_DIR, "{}.pdf".format(safe_name))

    if os.path.exists(filepath) and os.path.getsize(filepath) > 10000:
        log.info("  Already downloaded: %s", filepath)
        return filepath

    try:
        resp = requests.get(url, timeout=30, verify=False,
                            headers={"User-Agent": "Mozilla/5.0"},
                            stream=True)
        if resp.status_code == 200:
            with open(filepath, "wb") as f:
                for chunk in resp.iter_content(8192):
                    f.write(chunk)
            size = os.path.getsize(filepath)
            if size > 10000:
                log.info("  Downloaded %s (%d KB)", filepath, size // 1024)
                return filepath
            else:
                os.remove(filepath)
        return None
    except Exception as e:
        log.debug("  Download failed: %s", e)
        return None


def enrich_parts(limit=20):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    # Find parts with datasheet URLs but no extracted specs
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

    # Load LLM parser first, fall back to regex
    parser = None
    try:
        from finder_extras.llm_parser import LLMDatasheetParser
        parser = LLMDatasheetParser()
        log.info("Using LLM parser (NVIDIA NIM)")
    except ImportError:
        try:
            from finder_extras.datasheet_parser import DatasheetParser
            parser = DatasheetParser()
            log.info("Using regex parser")
        except ImportError:
            log.error("No parser available. Install finder_extras.")
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

        # Download PDF
        pdf_path = download_pdf(url, mpn)
        if not pdf_path:
            log.info("  Could not download PDF, skipping")
            conn.execute(
                "INSERT OR REPLACE INTO specifications "
                "(component_id, spec_name, spec_value) VALUES (?, '_enriched', 'no_pdf')",
                (comp_id,)
            )
            conn.commit()
            continue

        try:
            specs, pinout = parser.parse_datasheet(
                pdf_path, mpn, package=pkg, category=cat
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
                            "(component_id, spec_name, spec_value) VALUES (?, ?, ?)",
                            (comp_id, name, str(value))
                        )
                        count += 1

                conn.execute(
                    "INSERT OR REPLACE INTO specifications "
                    "(component_id, spec_name, spec_value) VALUES (?, '_enriched', '1')",
                    (comp_id,)
                )
                conn.commit()
                enriched += 1
                log.info("  Extracted %d specs for %s", count, mpn)
            else:
                conn.execute(
                    "INSERT OR REPLACE INTO specifications "
                    "(component_id, spec_name, spec_value) VALUES (?, '_enriched', '0')",
                    (comp_id,)
                )
                conn.commit()
                log.info("  No specs extracted for %s", mpn)

        except Exception as e:
            log.warning("  Failed for %s: %s", mpn, e)
            conn.execute(
                "INSERT OR REPLACE INTO specifications "
                "(component_id, spec_name, spec_value) VALUES (?, '_enriched', 'error')",
                (comp_id,)
            )
            conn.commit()

    log.info("=== RESULTS ===")
    log.info("Processed: %d parts", len(parts))
    log.info("Enriched with specs: %d", enriched)

    # Show updated overlap
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