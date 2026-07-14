"""Gap 16: Incremental/delta updates — only re-scrape stale categories."""

import logging
from datetime import datetime, timedelta

log = logging.getLogger(__name__)


def get_stale_categories(db, max_age_hours=168):
    """Return categories not scraped in the last max_age_hours (default 7 days)."""
    conn = db._get_conn()
    cutoff = (datetime.utcnow() - timedelta(hours=max_age_hours)).isoformat()

    rows = conn.execute("""
        SELECT category, MAX(scraped_at) as last_scraped, COUNT(*) as part_count
        FROM components
        GROUP BY category
    """).fetchall()

    stale = []
    for row in rows:
        last = row[1] or "1970-01-01T00:00:00"
        if last < cutoff:
            try:
                age = (datetime.utcnow() - datetime.fromisoformat(last)).total_seconds() / 3600
            except Exception:
                age = 9999
            stale.append({
                "category": row[0],
                "last_scraped": last,
                "part_count": row[2],
                "age_hours": round(age, 1),
            })

    stale.sort(key=lambda s: s["age_hours"], reverse=True)
    return stale


def show_scrape_status(db):
    """Print the scrape freshness of every category."""
    conn = db._get_conn()
    rows = conn.execute("""
        SELECT category, COUNT(*) as cnt,
               MIN(scraped_at) as oldest,
               MAX(scraped_at) as newest
        FROM components
        GROUP BY category
        ORDER BY MAX(scraped_at) ASC
    """).fetchall()

    print("\n{:<30} {:>6}  {:<20}  {:<20}".format(
        "Category", "Parts", "Oldest Scrape", "Newest Scrape"))
    print("-" * 82)

    for row in rows:
        cat = row[0] or "(none)"
        cnt = row[1]
        oldest = (row[2] or "never")[:19]
        newest = (row[3] or "never")[:19]
        print("{:<30} {:>6}  {:<20}  {:<20}".format(cat, cnt, oldest, newest))


def scrape_only_stale(engine, max_age_hours=168, max_pages=None, plugin_name=None):
    """Only scrape categories not updated recently. Returns {category: parts_scraped}."""
    stale = get_stale_categories(engine.db, max_age_hours)
    if not stale:
        log.info("All categories are fresh (within %d hours).", max_age_hours)
        return {}

    log.info("Found %d stale categories:", len(stale))
    for s in stale:
        log.info("  %s: last scraped %.0f hours ago (%d parts)",
                 s["category"], s["age_hours"], s["part_count"])

    results = {}
    for s in stale:
        cat = s["category"]
        log.info("Re-scraping %s...", cat)
        try:
            count = engine.scrape_category(cat, plugin_name=plugin_name, max_pages=max_pages)
            results[cat] = count
        except Exception as exc:
            log.error("Failed to scrape %s: %s", cat, exc)
            results[cat] = -1
    return results