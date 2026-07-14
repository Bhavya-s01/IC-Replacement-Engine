"""Gap 5: Remove duplicate parts across categories sharing the same URL."""

import logging

log = logging.getLogger(__name__)

PRIORITY = {
    "eeprom": 10,
    "flash_memory": 10,
    "fram_mram_sram": 10,
}


def deduplicate_across_categories(db):
    conn = db._get_conn()

    dupes = conn.execute("""
        SELECT manufacturer_part_number, COUNT(DISTINCT category) as cat_count
        FROM components
        WHERE source = 'digikey'
        GROUP BY manufacturer_part_number
        HAVING cat_count > 1
    """).fetchall()

    removed = 0
    for row in dupes:
        mpn = row["manufacturer_part_number"]
        entries = conn.execute(
            "SELECT id, category FROM components WHERE manufacturer_part_number = ? AND source = 'digikey'",
            (mpn,)
        ).fetchall()

        best = max(entries, key=lambda e: PRIORITY.get(e["category"], 5))
        for entry in entries:
            if entry["id"] != best["id"]:
                conn.execute("DELETE FROM specifications WHERE component_id = ?", (entry["id"],))
                conn.execute("DELETE FROM components WHERE id = ?", (entry["id"],))
                removed += 1

    conn.commit()
    log.info("Removed %d cross-category duplicates.", removed)
    return removed