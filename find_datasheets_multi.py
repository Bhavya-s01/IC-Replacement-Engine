"""
find_datasheets_multi.py — Search multiple sources for datasheet URLs
for parts not found on DigiKey. Uses Playwright + Edge.

Sources: LCSC, Alldatasheet, Datasheet4U, Google (manufacturer site)

Run: python find_datasheets_multi.py --limit 30
"""

import sqlite3
import re
import time
import logging
import argparse

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s | %(levelname)-7s | %(message)s")
log = logging.getLogger("find_ds_multi")

try:
    from playwright.sync_api import sync_playwright
    PW_OK = True
except ImportError:
    PW_OK = False
    log.error("Playwright not installed. Run: pip install playwright && python -m playwright install msedge")

DB_PATH = "ic_database.db"


def search_lcsc(page, mpn):
    """Search LCSC.com for a datasheet URL."""
    try:
        url = "https://www.lcsc.com/search?q={}".format(mpn)
        page.goto(url, timeout=20000, wait_until="domcontentloaded")
        time.sleep(3)

        content = page.content()

        # Look for datasheet PDF link
        pdf_matches = re.findall(
            r'href="(https?://[^"]+\.pdf[^"]*)"', content, re.IGNORECASE
        )
        for pdf_url in pdf_matches:
            lower = pdf_url.lower()
            if any(skip in lower for skip in ["privacy", "terms", "cookie", "catalog"]):
                continue
            return {"datasheet_url": pdf_url, "source": "LCSC"}

        # Try clicking on first product result to get datasheet
        try:
            first = page.locator('a[href*="/product-detail/"]').first
            first.wait_for(timeout=5000)
            href = first.get_attribute("href")
            if href:
                if not href.startswith("http"):
                    href = "https://www.lcsc.com" + href
                page.goto(href, timeout=20000, wait_until="domcontentloaded")
                time.sleep(2)
                content2 = page.content()
                pdfs2 = re.findall(r'href="(https?://[^"]+\.pdf[^"]*)"', content2)
                for pdf_url in pdfs2:
                    if "datasheet" in pdf_url.lower() or "pdf" in pdf_url.lower():
                        return {"datasheet_url": pdf_url, "source": "LCSC"}
        except Exception:
            pass

    except Exception as e:
        log.debug("LCSC failed for %s: %s", mpn, str(e)[:60])
    return None


def search_alldatasheet(page, mpn):
    """Search Alldatasheet.com for a datasheet URL."""
    try:
        url = "https://www.alldatasheet.com/view.jsp?Searchword={}".format(mpn)
        page.goto(url, timeout=20000, wait_until="domcontentloaded")
        time.sleep(2)

        content = page.content()

        # Look for datasheet download link
        pdf_matches = re.findall(
            r'href="(https?://[^"]+\.pdf[^"]*)"', content, re.IGNORECASE
        )
        for pdf_url in pdf_matches:
            if "alldatasheet" in pdf_url.lower() or "datasheet" in pdf_url.lower():
                return {"datasheet_url": pdf_url, "source": "Alldatasheet"}

        # Try the direct view link pattern
        view_matches = re.findall(
            r'href="(/view\.jsp\?Searchword=[^"]+)"', content
        )
        if view_matches:
            detail_url = "https://www.alldatasheet.com" + view_matches[0]
            page.goto(detail_url, timeout=20000, wait_until="domcontentloaded")
            time.sleep(2)
            content2 = page.content()
            pdfs2 = re.findall(r'href="(https?://[^"]+\.pdf[^"]*)"', content2)
            for pdf_url in pdfs2:
                return {"datasheet_url": pdf_url, "source": "Alldatasheet"}

    except Exception as e:
        log.debug("Alldatasheet failed for %s: %s", mpn, str(e)[:60])
    return None


def search_datasheet4u(page, mpn):
    """Search Datasheet4U.com."""
    try:
        url = "https://www.datasheet4u.com/share_search.php?sWord={}".format(mpn)
        page.goto(url, timeout=15000, wait_until="domcontentloaded")
        time.sleep(2)

        content = page.content()
        pdf_matches = re.findall(
            r'href="(https?://[^"]+\.pdf[^"]*)"', content, re.IGNORECASE
        )
        for pdf_url in pdf_matches:
            if any(skip in pdf_url.lower() for skip in ["privacy", "terms", "ad"]):
                continue
            return {"datasheet_url": pdf_url, "source": "Datasheet4U"}

    except Exception as e:
        log.debug("Datasheet4U failed for %s: %s", mpn, str(e)[:60])
    return None


def search_google_datasheet(page, mpn):
    """Search Google for '<mpn> datasheet pdf'."""
    try:
        query = "{} datasheet pdf filetype:pdf".format(mpn)
        url = "https://www.google.com/search?q={}".format(query.replace(" ", "+"))
        page.goto(url, timeout=15000, wait_until="domcontentloaded")
        time.sleep(2)

        content = page.content()

        # Extract PDF links from Google results
        pdf_matches = re.findall(
            r'href="(https?://[^"]+\.pdf[^"]*)"', content, re.IGNORECASE
        )
        for pdf_url in pdf_matches:
            lower = pdf_url.lower()
            # Skip Google's own URLs and ad URLs
            if any(skip in lower for skip in [
                "google.com", "gstatic", "youtube", "accounts.google",
                "privacy", "terms", "support.google"
            ]):
                continue
            # Prefer manufacturer domains
            if any(mfr in lower for mfr in [
                "ti.com", "microchip.com", "diodes.com", "onsemi.com",
                "nxp.com", "st.com", "infineon.com", "analog.com",
                "renesas.com", "toshiba", "rohm.com", "richtek",
                "silergy", "chipown", "fitipower", "realtek",
                "ene.com", "himax", "novatek"
            ]):
                return {"datasheet_url": pdf_url, "source": "Google (manufacturer)"}
            return {"datasheet_url": pdf_url, "source": "Google"}

    except Exception as e:
        log.debug("Google failed for %s: %s", mpn, str(e)[:60])
    return None


def download_datasheet(url, mpn):
    """Download a datasheet PDF to datasheets/ folder."""
    import requests
    import os

    os.makedirs("datasheets", exist_ok=True)
    safe_name = re.sub(r'[^\w\-.]', '_', mpn)
    filepath = "datasheets/{}.pdf".format(safe_name)

    if os.path.exists(filepath) and os.path.getsize(filepath) > 10000:
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
                log.info("  Downloaded datasheets\\%s (%d KB)",
                         os.path.basename(filepath), size // 1024)
                return filepath
            else:
                os.remove(filepath)
        return None
    except Exception as e:
        log.debug("  Download failed: %s", e)
        return None


def enrich_with_parser(conn, comp_id, mpn, pdf_path, package, category):
    """Extract specs from downloaded PDF and store in database."""
    try:
        from finder_extras.datasheet_parser import DatasheetParser
        parser = DatasheetParser()
        page_texts = parser._get_page_texts(pdf_path)
        if not page_texts:
            return 0

        specs = parser.extract_specs(page_texts, category=category)
        if not specs:
            return 0

        count = 0
        for name, value in specs.items():
            existing = conn.execute(
                "SELECT 1 FROM specifications WHERE component_id = ? AND spec_name = ?",
                (comp_id, name)
            ).fetchone()
            if not existing:
                conn.execute(
                    "INSERT INTO specifications (component_id, spec_name, spec_value) VALUES (?, ?, ?)",
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
        log.debug("  Parser failed for %s: %s", mpn, e)
        return 0


def process_not_found(limit=30, enrich=True):
    """Search multiple sources for parts DigiKey couldn't find."""
    if not PW_OK:
        log.error("Playwright not installed")
        return

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    # Get parts that DigiKey couldn't find
    pending = conn.execute("""
        SELECT * FROM datasheet_queue
        WHERE status IN ('not_found', 'pending')
        LIMIT ?
    """, (limit,)).fetchall()

    log.info("Processing %d parts from multiple sources", len(pending))

    if not pending:
        log.info("No pending parts")
        conn.close()
        return

    found = 0
    enriched = 0

    # Search functions in priority order
    search_functions = [
        ("LCSC", search_lcsc),
        ("Alldatasheet", search_alldatasheet),
        ("Datasheet4U", search_datasheet4u),
        ("Google", search_google_datasheet),
    ]

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True, channel="msedge")
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                       "AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0"
        )
        page = context.new_page()

        for item in pending:
            mpn = item["mpn"]
            category = item["category_slug"] or "unknown"
            package = item["package_type"] or ""

            log.info("Searching for: %s", mpn)

            # Check if already in components table
            existing = conn.execute(
                "SELECT id FROM components WHERE manufacturer_part_number = ?",
                (mpn,)
            ).fetchone()
            if existing:
                # Part already in DB — just check if it has a datasheet
                has_ds = conn.execute(
                    "SELECT datasheet_url FROM components WHERE id = ?",
                    (existing["id"],)
                ).fetchone()
                if has_ds and has_ds["datasheet_url"]:
                    conn.execute(
                        "UPDATE datasheet_queue SET status = 'already_exists' WHERE id = ?",
                        (item["id"],)
                    )
                    conn.commit()
                    continue

            # Try each source
            result = None
            for source_name, search_fn in search_functions:
                log.info("  Trying %s...", source_name)
                result = search_fn(page, mpn)
                if result:
                    log.info("  Found via %s: %s",
                             result.get("source"), result["datasheet_url"][:70])
                    break
                time.sleep(1)  # brief pause between sources

            if result and result.get("datasheet_url"):
                if existing:
                    # Update existing component with datasheet URL
                    conn.execute(
                        "UPDATE components SET datasheet_url = ? WHERE id = ?",
                        (result["datasheet_url"], existing["id"])
                    )
                    comp_id = existing["id"]
                else:
                    # Insert new component
                    conn.execute("""
                        INSERT OR IGNORE INTO components (
                            manufacturer_part_number, manufacturer, description,
                            category, datasheet_url, source,
                            package, mounting_type, scraped_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, 'Surface Mount', datetime('now'))
                    """, (
                        mpn, "", "",
                        category,
                        result["datasheet_url"],
                        result.get("source", "multi"),
                        package,
                    ))
                    comp = conn.execute(
                        "SELECT id FROM components WHERE manufacturer_part_number = ?",
                        (mpn,)
                    ).fetchone()
                    comp_id = comp["id"] if comp else None

                conn.execute(
                    "UPDATE datasheet_queue SET status = 'found' WHERE id = ?",
                    (item["id"],)
                )
                conn.commit()
                found += 1

                # Download and extract specs
                if enrich and comp_id:
                    pdf_path = download_datasheet(result["datasheet_url"], mpn)
                    if pdf_path:
                        n = enrich_with_parser(conn, comp_id, mpn,
                                               pdf_path, package, category)
                        if n > 0:
                            enriched += 1
                            log.info("  Extracted %d specs", n)
            else:
                conn.execute(
                    "UPDATE datasheet_queue SET status = 'not_found_multi' WHERE id = ?",
                    (item["id"],)
                )
                conn.commit()
                log.info("  Not found on any source")

            time.sleep(2)  # rate limit between parts

        browser.close()

    # Stats
    log.info("=== RESULTS ===")
    log.info("Searched: %d parts", len(pending))
    log.info("Found datasheets: %d", found)
    log.info("Enriched with specs: %d", enriched)

    total_pending = conn.execute(
        "SELECT COUNT(*) FROM datasheet_queue WHERE status IN ('pending', 'not_found')"
    ).fetchone()[0]
    total_found = conn.execute(
        "SELECT COUNT(*) FROM datasheet_queue WHERE status = 'found'"
    ).fetchone()[0]
    total_not = conn.execute(
        "SELECT COUNT(*) FROM datasheet_queue WHERE status = 'not_found_multi'"
    ).fetchone()[0]
    overlap = conn.execute(
        "SELECT COUNT(DISTINCT sc.mpn) FROM supply_chain sc "
        "INNER JOIN components c ON c.manufacturer_part_number = sc.mpn"
    ).fetchone()[0]

    log.info("Queue: %d pending, %d found, %d exhausted", total_pending, total_found, total_not)
    log.info("Overlap with supply chain: %d parts", overlap)

    conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Search LCSC, Alldatasheet, Datasheet4U, Google for datasheets"
    )
    parser.add_argument("--limit", type=int, default=30)
    parser.add_argument("--no-enrich", action="store_true",
                        help="Skip spec extraction after download")
    args = parser.parse_args()
    process_not_found(limit=args.limit, enrich=not args.no_enrich)