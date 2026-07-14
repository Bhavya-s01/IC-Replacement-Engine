"""Gap 14: Scrape DigiKey 'Suggested Alternatives' from product pages."""

import time
import logging
import sqlite3

log = logging.getLogger(__name__)


def scrape_substitutes(page, db, category=None, max_parts=50, delay=3.0):
    """
    Visit individual DigiKey product pages and extract suggested alternatives.
    Use sparingly to avoid blocking.
    """
    conn = db._get_conn()

    query = "SELECT id, manufacturer_part_number, product_url FROM components WHERE product_url != ''"
    params = []
    if category:
        query += " AND category = ?"
        params.append(category)
    query += " LIMIT ?"
    params.append(max_parts)

    parts = conn.execute(query, params).fetchall()
    total_subs = 0

    for i, part in enumerate(parts):
        comp_id = part[0]
        mpn = part[1]
        url = part[2]

        if not url or not url.startswith("http"):
            continue

        existing = conn.execute(
            "SELECT COUNT(*) FROM substitutes WHERE component_id = ?", (comp_id,)
        ).fetchone()[0]
        if existing > 0:
            continue

        try:
            log.info("[%d/%d] Visiting %s", i + 1, len(parts), mpn)
            page.goto(url, wait_until="domcontentloaded", timeout=60000)
            time.sleep(delay)

            subs = page.evaluate("""
                () => {
                    const results = [];
                    const selectors = [
                        '[data-testid*="alternative"]',
                        '[class*="alternative"]',
                        '[class*="substitute"]',
                        '[class*="also-viewed"]',
                        '[class*="similar-product"]',
                    ];
                    for (const sel of selectors) {
                        const section = document.querySelector(sel);
                        if (section) {
                            const links = section.querySelectorAll('a[href*="/en/products/detail/"]');
                            links.forEach(a => {
                                const text = a.innerText.trim().split('\\n')[0].trim();
                                if (text && text.length > 3 && text.length < 60) {
                                    results.push({mpn: text, url: a.getAttribute('href')});
                                }
                            });
                        }
                    }
                    return results;
                }
            """)

            if subs:
                for sub in subs:
                    conn.execute(
                        "INSERT OR IGNORE INTO substitutes "
                        "(component_id, substitute_part_number, compatibility_notes) "
                        "VALUES (?, ?, ?)",
                        (comp_id, sub["mpn"], "DigiKey Suggested Alternative")
                    )
                    total_subs += 1
                log.info("  Found %d alternatives for %s", len(subs), mpn)

        except Exception as exc:
            log.debug("Failed for %s: %s", mpn, str(exc)[:60])

        if (i + 1) % 10 == 0:
            conn.commit()

    conn.commit()
    log.info("Populated %d substitute entries from %d product pages.", total_subs, len(parts))
    return total_subs