"""SQLite database manager for the IC database."""

import sqlite3
import logging
import sys
import os
from contextlib import contextmanager

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import DB_PATH

log = logging.getLogger(__name__)

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS components (
    id                        INTEGER PRIMARY KEY,
    manufacturer_part_number  TEXT NOT NULL UNIQUE,
    manufacturer              TEXT,
    description               TEXT,
    category                  TEXT,
    subcategory               TEXT,
    datasheet_url             TEXT,
    product_url               TEXT,
    package                   TEXT,
    mounting_type             TEXT,
    source                    TEXT DEFAULT 'digikey',
    scraped_at                TEXT
);

CREATE TABLE IF NOT EXISTS specifications (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    component_id  INTEGER NOT NULL,
    spec_name     TEXT    NOT NULL,
    spec_value    TEXT,
    FOREIGN KEY (component_id) REFERENCES components(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS substitutes (
    id                         INTEGER PRIMARY KEY AUTOINCREMENT,
    component_id               INTEGER NOT NULL,
    substitute_part_number     TEXT,
    substitute_manufacturer    TEXT,
    compatibility_notes        TEXT,
    FOREIGN KEY (component_id) REFERENCES components(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_comp_category    ON components(category);
CREATE INDEX IF NOT EXISTS idx_comp_mfr         ON components(manufacturer);
CREATE INDEX IF NOT EXISTS idx_comp_mpn         ON components(manufacturer_part_number);
CREATE INDEX IF NOT EXISTS idx_comp_source      ON components(source);
CREATE INDEX IF NOT EXISTS idx_spec_comp        ON specifications(component_id);
CREATE INDEX IF NOT EXISTS idx_spec_name        ON specifications(spec_name);
CREATE INDEX IF NOT EXISTS idx_spec_name_value  ON specifications(spec_name, spec_value);
CREATE INDEX IF NOT EXISTS idx_sub_comp         ON substitutes(component_id);
"""


class Database:
    def __init__(self, db_path=DB_PATH):
        self.db_path = db_path
        self._conn = None
        self._init_db()

    def _get_conn(self):
        if self._conn is None:
            self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA foreign_keys=ON")
            self._conn.execute("PRAGMA synchronous=NORMAL")
            self._conn.row_factory = sqlite3.Row
        return self._conn

    def _init_db(self):
        conn = self._get_conn()
        conn.executescript(SCHEMA_SQL)
        from import_template import create_tables  # supply_chain + datasheet_queue
        create_tables(conn)
        conn.commit()
        log.info("Database initialised at %s", self.db_path)

    @contextmanager
    def transaction(self):
        conn = self._get_conn()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
    
    def checkpoint(self):
        """Force WAL data into main database file to prevent data loss."""
        conn = self._get_conn()
        try:
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        except Exception as exc:
            logging.getLogger(__name__).warning("WAL checkpoint failed: %s", exc)

    def bulk_upsert_safe(self, components):
        """Upsert with WAL checkpoint - data guaranteed in .db file."""
        count = self.bulk_upsert(components)
        self.checkpoint()
        return count

    def close(self):
        if self._conn:
            self._conn.close()
            self._conn = None

    def upsert_component(self, comp, commit=True):
        conn = self._get_conn()
        conn.execute(
            """
            INSERT INTO components (
                manufacturer_part_number, manufacturer, description, category,
                subcategory, datasheet_url, product_url, package, mounting_type,
                source, scraped_at
            ) VALUES (:mpn, :mfr, :desc, :cat, :subcat, :ds, :url, :pkg, :mount, :src, :ts)
            ON CONFLICT(manufacturer_part_number) DO UPDATE SET
                manufacturer  = excluded.manufacturer,
                description   = excluded.description,
                category      = CASE WHEN EXISTS (SELECT 1 FROM supply_chain s
                                      WHERE upper(s.mpn) = upper(components.manufacturer_part_number))
                                     THEN components.category ELSE excluded.category END,
                subcategory   = excluded.subcategory,
                datasheet_url = COALESCE(NULLIF(excluded.datasheet_url, ''), components.datasheet_url),
                product_url   = excluded.product_url,
                package       = excluded.package,
                mounting_type = excluded.mounting_type,
                scraped_at    = excluded.scraped_at
            """,
            {
                "mpn": comp.manufacturer_part_number,
                "mfr": comp.manufacturer,
                "desc": comp.description,
                "cat": comp.category,
                "subcat": comp.subcategory,
                "ds": comp.datasheet_url,
                "url": comp.product_url,
                "pkg": comp.package,
                "mount": comp.mounting_type,
                "src": comp.source,
                "ts": comp.scraped_at,
            },
        )
        row = conn.execute(
            "SELECT id FROM components WHERE manufacturer_part_number=?",
            (comp.manufacturer_part_number,),
        ).fetchone()
        comp_id = row["id"]

        conn.execute("DELETE FROM specifications WHERE component_id=?", (comp_id,))
        for name, value in comp.raw_specs.items():
            conn.execute(
                "INSERT INTO specifications (component_id, spec_name, spec_value) VALUES (?, ?, ?)",
                (comp_id, name, value),
            )
        if commit:
            conn.commit()
        return comp_id

    def bulk_upsert(self, components):
        count = 0
        with self.transaction():
            for comp in components:
                self.upsert_component(comp, commit=False)
                count += 1
        log.info("Bulk upserted %d components", count)
        return count

    def count_by_category(self):
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT category, COUNT(*) as cnt FROM components GROUP BY category"
        ).fetchall()
        return {r["category"]: r["cnt"] for r in rows}

    def search(self, *, category=None, manufacturer=None, keyword=None,
               spec_filters=None, limit=100):
        conn = self._get_conn()
        conditions = []
        params = []

        if category:
            conditions.append("c.category = ?")
            params.append(category)
        if manufacturer:
            conditions.append("c.manufacturer LIKE ?")
            params.append(f"%{manufacturer}%")
        if keyword:
            conditions.append(
                "(c.description LIKE ? OR c.manufacturer_part_number LIKE ?)"
            )
            params.extend([f"%{keyword}%", f"%{keyword}%"])

        where = " AND ".join(conditions) if conditions else "1=1"
        sql = f"SELECT DISTINCT c.* FROM components c"

        if spec_filters:
            for i, (sname, sval) in enumerate(spec_filters.items()):
                alias = f"s{i}"
                sql += (
                    f" JOIN specifications {alias} "
                    f"ON {alias}.component_id = c.id "
                    f"AND {alias}.spec_name = ? "
                    f"AND {alias}.spec_value LIKE ? "
                )
                params = [sname, f"%{sval}%"] + params

        sql += f" WHERE {where} ORDER BY c.manufacturer_part_number LIMIT ?"
        params.append(limit)

        rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]

    def get_specifications(self, component_id):
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT spec_name, spec_value FROM specifications WHERE component_id=?",
            (component_id,),
        ).fetchall()
        return {r["spec_name"]: r["spec_value"] for r in rows}

    def total_components(self):
        conn = self._get_conn()
        row = conn.execute("SELECT COUNT(*) as cnt FROM components").fetchone()
        return row["cnt"]
