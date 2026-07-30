"""
build_specs_cache.py — Build a fast spec lookup cache.
Run after enrichment: python build_specs_cache.py
"""

import sqlite3
import json
import time

DB = "ic_database.db"
conn = sqlite3.connect(DB)

start = time.time()

# Build a JSON blob per component with ALL its specs
print("Building specs cache...")

conn.execute("DROP TABLE IF EXISTS specs_cache")
conn.execute("""
    CREATE TABLE specs_cache (
        component_id INTEGER PRIMARY KEY,
        specs_json TEXT
    )
""")

# Batch insert: for each component, collect all specs into a JSON dict
rows = conn.execute("""
    SELECT component_id, spec_name, spec_value
    FROM specifications
    WHERE substr(spec_name, 1, 1) != '_'
    ORDER BY component_id
""").fetchall()

cache = {}
for comp_id, name, value in rows:
    if comp_id not in cache:
        cache[comp_id] = {}
    cache[comp_id][name] = value

print("  {} components with specs".format(len(cache)))

# Insert in batch
batch = [(cid, json.dumps(specs)) for cid, specs in cache.items()]
conn.executemany(
    "INSERT INTO specs_cache (component_id, specs_json) VALUES (?, ?)",
    batch
)
conn.commit()

# Also build composite index on components for fast category lookup
conn.execute("""
    CREATE INDEX IF NOT EXISTS idx_comp_cat_id
    ON components(category, id)
""")
conn.commit()

elapsed = time.time() - start
print("  Built in {:.1f}s".format(elapsed))
print("  {} rows in specs_cache".format(len(batch)))
print("")
print("Finder will use specs_cache for instant spec lookups")
print("Re-run after every enrichment batch: python build_specs_cache.py")

conn.close()