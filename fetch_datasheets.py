"""
fetch_datasheets.py — Uses Playwright + Edge to search DigiKey for
template parts, extract datasheet PDF URLs, and add parts to the
components table for LLM enrichment.

Run: python fetch_datasheets.py --limit 30
"""

import sqlite3
import os
import re
import time
import logging
import argparse

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s | %(levelname)-7s | %(message)s")
log = logging.getLogger("fetch_ds")

DB_PATH = "ic_database.db"
DATASHEET_DIR = "datasheets"

try:
    from playwright.sync_api import sync_playwright
    PW_OK = True
except ImportError:
    PW_OK = False
    log.error("Playwright not installed. Run: pip install playwright && python -m playwright install msedge")


def search_digikey(page, mpn):
    """Search DigiKey for an MPN using Playwright + Edge."""
    url = "https://www.digikey.com/en/products/result?keywords={}".format(mpn)
    try:
        page.goto(url, timeout=30000, wait_until="domcontentloaded")
        time.sleep(3)

        # Check if we landed on a product detail page directly
        if "/en/products/detail/" in page.url:
            return extract_from_page(page, mpn)

        # Otherwise on search results — click first result
        try:
            link = page.locator('a[href*="/en/products/detail/"]').first
            link.wait_for(timeout=8000)
            href = link.get_attribute("href")
            if href:
                if not href.startswith("http"):
                    href = "https://www.digikey.com" + href
                page.goto(href, timeout=30000, wait_until="domcontentloaded")
                time.sleep(3)
                return extract_from_page(page, mpn)
        except Exception:
            log.debug("No search results for %s", mpn)
            return None

    except Exception as e:
        log.debug("Search failed for %s: %s", mpn, e)
        return None


def extract_from_page(page, mpn):
    """Extract datasheet URL and part info from a DigiKey product page."""
    result = {
        "datasheet_url": None,
        "manufacturer": "",
        "description": "",
        "package": "",
    }

    content = page.content()

    # Extract datasheet URL — look for PDF links
    pdf_patterns = [
        r'href="(https?://[^"]+\.pdf[^"]*)"',
        r'"datasheetUrl"\s*:\s*"(https?://[^"]+)"',
    ]
    for pattern in pdf_patterns:
        match = re.search(pattern, content, re.IGNORECASE)
        if match:
            url = match.group(1)
            # Skip DigiKey's own PDFs (drawings, not datasheets)
            if "digikey" not in url.lower():
                result["datasheet_url"] = url
                break

    # If no external PDF found, try any PDF
    if not result["datasheet_url"]:
        match = re.search(r'href="(https?://[^"]+\.pdf[^"]*)"', content)
        if match:
            result["datasheet_url"] = match.group(1)

    # Extract manufacturer
    try:
        mfr_el = page.locator('[data-testid="manufacturer-name"]').first
        result["manufacturer"] = mfr_el.inner_text(timeout=3000).strip()
    except Exception:
        mfr_match = re.search(r'"manufacturer"\s*:\s*"([^"]+)"', content)
        if mfr_match:
            result["manufacturer"] = mfr_match.group(1)

    # Extract description
    try:
        desc_el = page.locator('[data-testid="product-description"], h1').first
        result["description"] = desc_el.inner_text(timeout=3000).strip()[:200]
    except Exception:
        pass

    # Extract package
    pkg_match = re.search(
        r'(?:Package|Supplier Device Package)[^<]*</th>\s*<td[^>]*>([^<]+)',
        content, re.IGNORECASE
    )
    if pkg_match:
        result["package"] = pkg_match.group(1).strip()

    return result if result["datasheet_url"] else None


def download_datasheet(url, mpn):
    """Download a datasheet PDF."""
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


def enrich_with_llm(conn, comp_id, mpn, pdf_path, package, category):
    """Parse datasheet with LLM and store extracted specs."""
    parser = None
    try:
        from finder_extras.llm_parser import LLMDatasheetParser
        parser = LLMDatasheetParser()
    except ImportError:
        try:
            from finder_extras.datasheet_parser import DatasheetParser
            parser = DatasheetParser()
        except ImportError:
            log.warning("  No parser available for %s", mpn)
            return 0

    try:
        specs, pinout = parser.parse_datasheet(
            pdf_path, mpn, package=package, category=category
        )
        if not specs:
            return 0

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
        return count
    except Exception as e:
        log.warning("  LLM parse failed for %s: %s", mpn, e)
        return 0


def run(limit=30, enrich=True):
    """Main pipeline: find datasheets via Edge + optionally extract specs."""
    if not PW_OK:
        return

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    pending = conn.execute(
        "SELECT * FROM datasheet_queue WHERE status = 'pending' LIMIT ?",
        (limit,)
    ).fetchall()

    log.info("Processing %d parts from datasheet queue", len(pending))

    if not pending:
        log.info("No pending parts. Queue is empty.")
        conn.close()
        return

    found = 0
    enriched = 0

    with sync_playwright() as pw:
        # USE EDGE instead of Chromium
        browser = pw.chromium.launch(
            headless=True,
            channel="msedge",
        )
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0"
        )
        page = context.new_page()

        for item in pending:
            mpn = item["mpn"]
            category = item["category_slug"] or "unknown"
            package = item["package_type"] or ""

            log.info("Searching DigiKey for: %s", mpn)

            # Check if already in components table
            existing = conn.execute(
                "SELECT id FROM components WHERE manufacturer_part_number = ?",
                (mpn,)
            ).fetchone()
            if existing:
                conn.execute(
                    "UPDATE datasheet_queue SET status = 'already_exists' WHERE id = ?",
                    (item["id"],)
                )
                conn.commit()
                continue

            # Search DigiKey via Edge
            result = search_digikey(page, mpn)

            if result and result.get("datasheet_url"):
                # Add to components table
                conn.execute("""
                    INSERT OR IGNORE INTO components (
                        manufacturer_part_number, manufacturer, description,
                        category, datasheet_url, source,
                        package, lifecycle_status, stock, unit_price
                    ) VALUES (?, ?, ?, ?, ?, 'template', ?, 'Unknown', 0, 0.0)
                """, (
                    mpn,
                    result.get("manufacturer", ""),
                    result.get("description", ""),
                    category,
                    result["datasheet_url"],
                    result.get("package", package),
                ))
                conn.commit()

                conn.execute(
                    "UPDATE datasheet_queue SET status = 'found' WHERE id = ?",
                    (item["id"],)
                )
                conn.commit()
                found += 1
                log.info("  Found: %s", result["datasheet_url"][:70])

                # Download + LLM enrich
                if enrich:
                    pdf_path = download_datasheet(result["datasheet_url"], mpn)
                    if pdf_path:
                        comp = conn.execute(
                            "SELECT id FROM components "
                            "WHERE manufacturer_part_number = ?",
                            (mpn,)
                        ).fetchone()
                        if comp:
                            n = enrich_with_llm(
                                conn, comp["id"], mpn, pdf_path,
                                package, category
                            )
                            if n > 0:
                                enriched += 1
                                log.info("  Extracted %d specs", n)
            else:
                conn.execute(
                    "UPDATE datasheet_queue SET status = 'not_found' WHERE id = ?",
                    (item["id"],)
                )
                conn.commit()
                log.info("  Not found on DigiKey")

            time.sleep(2.5)  # rate limit

        browser.close()

    log.info("=== RESULTS ===")
    log.info("Searched: %d parts", len(pending))
    log.info("Found datasheets: %d", found)
    log.info("Enriched with specs: %d", enriched)

    total_pending = conn.execute(
        "SELECT COUNT(*) FROM datasheet_queue WHERE status = 'pending'"
    ).fetchone()[0]
    total_found = conn.execute(
        "SELECT COUNT(*) FROM datasheet_queue WHERE status = 'found'"
    ).fetchone()[0]

    log.info("Queue: %d pending, %d found", total_pending, total_found)
    conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Fetch datasheets from DigiKey using Playwright + Edge"
    )
    parser.add_argument("--limit", type=int, default=30)
    parser.add_argument("--no-enrich", action="store_true",
                        help="Skip LLM spec extraction")
    args = parser.parse_args()
    run(limit=args.limit, enrich=not args.no_enrich)