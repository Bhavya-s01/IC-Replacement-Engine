"""Idempotently queue components that have no datasheet URL.

Supply-chain MPNs are inserted first so both fetchers can process them before
the remaining catalogue records. Existing queue status is preserved.
"""

import sqlite3


DB_PATH = "ic_database.db"


def main():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        INSERT OR IGNORE INTO datasheet_queue
            (mpn, category_slug, package_type, source, status)
        SELECT c.manufacturer_part_number,
               COALESCE(c.category, ''),
               COALESCE(c.package, ''),
               CASE WHEN sc.id IS NOT NULL THEN 'supply_chain_missing_url'
                    ELSE 'component_missing_url' END,
               'pending'
        FROM components c
        LEFT JOIN supply_chain sc
          ON upper(trim(sc.mpn)) = upper(trim(c.manufacturer_part_number))
        WHERE c.manufacturer_part_number IS NOT NULL
          AND trim(c.manufacturer_part_number) <> ''
          AND (c.datasheet_url IS NULL OR trim(c.datasheet_url) = '')
        ORDER BY CASE WHEN sc.id IS NOT NULL THEN 0 ELSE 1 END, c.id
    """)
    inserted = conn.execute("SELECT changes()").fetchone()[0]
    total = conn.execute("SELECT COUNT(*) FROM datasheet_queue").fetchone()[0]
    supply_chain = conn.execute("""
        SELECT COUNT(*) FROM datasheet_queue q
        WHERE EXISTS (
            SELECT 1 FROM supply_chain sc
            WHERE upper(trim(sc.mpn)) = upper(trim(q.mpn))
        )
    """).fetchone()[0]
    pending = conn.execute("SELECT COUNT(*) FROM datasheet_queue WHERE status='pending'").fetchone()[0]
    conn.commit()
    conn.close()
    print("Queued this run: {}".format(inserted))
    print("Queue total: {} (supply-chain: {}, pending: {})".format(total, supply_chain, pending))


if __name__ == "__main__":
    main()
