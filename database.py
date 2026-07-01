"""SQLite database manager for the IC database."""

import sqlite3
import json
import logging
import sys
import os
from typing import Dict, List, Optional
from contextlib import contextmanager

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from models import Component
from config import DB_PATH

log = logging.getLogger(__name__)

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS components (
    id                        INTEGER PRIMARY KEY AUTOINCREMENT,
    digikey_part_number       TEXT,
    manufacturer_part_number  TEXT,
    manufacturer              TEXT,
    description               TEXT,
    category                  TEXT,
    subcategory               TEXT,
    datasheet_url             TEXT,
    product_url               TEXT,
    stock                     INTEGER DEFAULT 0,
    unit_price                REAL    DEFAULT 0.0,
    price_breaks              TEXT    DEFAULT '[]',
    package                   TEXT,
    mounting_type             TEXT,
    lifecycle_status          TEXT,
    source                    TEXT    DEFAULT 'digikey',
    scraped_at                TEXT,
    raw_data                  TEXT    DEFAULT '{}',
    UNIQUE(manufacturer_part_number, source)
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
            self._conn = sqlite3.connect(self.db_path)
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA foreign_keys=ON")
            self._conn.execute("PRAGMA synchronous=NORMAL")
            self._conn.row_factory = sqlite3.Row
        return self._conn

    def _init_db(self):
        conn = self._get_conn()
        conn.executescript(SCHEMA_SQL)
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

    def close(self):
        if self._conn:
            self._conn.close()
            self._conn = None

    def upsert_component(self, comp):
        conn = self._get_conn()
        conn.execute(
            """
            INSERT INTO components (
                digikey_part_number, manufacturer_part_number,
                manufacturer, description, category, subcategory,
                datasheet_url, product_url, stock, unit_price,
                price_breaks, package, mounting_type,
                lifecycle_status, source, scraped_at, raw_data
            ) VALUES (
                :dk, :mpn, :mfr, :desc, :cat, :subcat,
                :ds, :url, :stock, :price, :pb, :pkg,
                :mount, :lc, :src, :ts, :raw
            )
            ON CONFLICT(manufacturer_part_number, source) DO UPDATE SET
                digikey_part_number = excluded.digikey_part_number,
                manufacturer        = excluded.manufacturer,
                description         = excluded.description,
                category            = excluded.category,
                subcategory         = excluded.subcategory,
                datasheet_url       = excluded.datasheet_url,
                product_url         = excluded.product_url,
                stock               = excluded.stock,
                unit_price          = excluded.unit_price,
                price_breaks        = excluded.price_breaks,
                package             = excluded.package,
                mounting_type       = excluded.mounting_type,
                lifecycle_status    = excluded.lifecycle_status,
                scraped_at          = excluded.scraped_at,
                raw_data            = excluded.raw_data
            """,
            {
                "dk": comp.digikey_part_number,
                "mpn": comp.manufacturer_part_number,
                "mfr": comp.manufacturer,
                "desc": comp.description,
                "cat": comp.category,
                "subcat": comp.subcategory,
                "ds": comp.datasheet_url,
                "url": comp.product_url,
                "stock": comp.stock,
                "price": comp.unit_price,
                "pb": comp.price_breaks_json(),
                "pkg": comp.package,
                "mount": comp.mounting_type,
                "lc": comp.lifecycle_status,
                "src": comp.source,
                "ts": comp.scraped_at,
                "raw": comp.raw_specs_json(),
            },
        )
        row = conn.execute(
            "SELECT id FROM components WHERE manufacturer_part_number=? AND source=?",
            (comp.manufacturer_part_number, comp.source),
        ).fetchone()
        comp_id = row["id"]

        conn.execute("DELETE FROM specifications WHERE component_id=?", (comp_id,))
        for name, value in comp.raw_specs.items():
            conn.execute(
                "INSERT INTO specifications (component_id, spec_name, spec_value) VALUES (?, ?, ?)",
                (comp_id, name, value),
            )
        conn.commit()
        return comp_id

    def bulk_upsert(self, components):
        count = 0
        with self.transaction():
            for comp in components:
                self.upsert_component(comp)
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
