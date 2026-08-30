import sqlite3, os

conn = sqlite3.connect("ic_database.db")

print("=" * 60)
print("DATABASE STATUS REPORT")
print("=" * 60)

total = conn.execute("SELECT COUNT(*) FROM components").fetchone()[0]
print("")
print("COMPONENTS")
print("  Total ICs in database:       {:>8,}".format(total))

has_ds = conn.execute(
    "SELECT COUNT(*) FROM components WHERE datasheet_url IS NOT NULL AND datasheet_url != ''"
).fetchone()[0]
print("  With datasheet URL:          {:>8,} ({:.0f}%)".format(has_ds, has_ds*100/total))

has_pkg = conn.execute(
    "SELECT COUNT(*) FROM components WHERE package IS NOT NULL AND package != ''"
).fetchone()[0]
print("  With package info:           {:>8,} ({:.0f}%)".format(has_pkg, has_pkg*100/total))

print("")
print("CATEGORIES")
cats = conn.execute(
    "SELECT category, COUNT(*) as cnt FROM components GROUP BY category ORDER BY cnt DESC"
).fetchall()
print("  Total categories:            {:>8}".format(len(cats)))
for cat, cnt in cats:
    print("    {:<30s} {:>6,}".format(cat or "(none)", cnt))

print("")
print("SPECIFICATIONS")
total_specs = conn.execute("SELECT COUNT(*) FROM specifications").fetchone()[0]
internal = conn.execute(
    "SELECT COUNT(*) FROM specifications WHERE substr(spec_name, 1, 1) = '_'"
).fetchone()[0]
real_specs = total_specs - internal
print("  Total spec rows:             {:>8,}".format(total_specs))
print("  Real specs:                  {:>8,}".format(real_specs))
print("  Internal (_enriched etc):    {:>8,}".format(internal))

unique_names = conn.execute(
    "SELECT COUNT(DISTINCT spec_name) FROM specifications WHERE substr(spec_name, 1, 1) != '_'"
).fetchone()[0]
print("  Unique spec names:           {:>8,}".format(unique_names))

parts_with_specs = conn.execute(
    "SELECT COUNT(DISTINCT component_id) FROM specifications WHERE substr(spec_name, 1, 1) != '_'"
).fetchone()[0]
print("  Parts with specs:            {:>8,}".format(parts_with_specs))
if parts_with_specs > 0:
    print("  Avg specs per part:          {:>8.1f}".format(real_specs / parts_with_specs))

print("")
print("LLM ENRICHMENT")
enriched_ok = conn.execute(
    "SELECT COUNT(DISTINCT component_id) FROM specifications WHERE spec_name = '_enriched' AND spec_value = '1'"
).fetchone()[0]
enriched_fail = conn.execute(
    "SELECT COUNT(DISTINCT component_id) FROM specifications WHERE spec_name = '_enriched' AND spec_value IN ('0', 'error')"
).fetchone()[0]
print("  Successfully enriched:       {:>8,}".format(enriched_ok))
print("  Failed/no specs:             {:>8,}".format(enriched_fail))
print("  Not attempted:               {:>8,}".format(total - enriched_ok - enriched_fail))

print("")
print("SUPPLY CHAIN")
sc_total = conn.execute("SELECT COUNT(*) FROM supply_chain").fetchone()[0]
print("  Supply chain entries:        {:>8,}".format(sc_total))

sc_unique = conn.execute("SELECT COUNT(DISTINCT mpn) FROM supply_chain").fetchone()[0]
print("  Unique supply chain MPNs:    {:>8,}".format(sc_unique))

overlap = conn.execute(
    "SELECT COUNT(DISTINCT sc.mpn) FROM supply_chain sc INNER JOIN components c ON upper(trim(c.manufacturer_part_number)) = upper(trim(sc.mpn))"
).fetchone()[0]
print("  Overlap with components:     {:>8,} / {} ({:.0f}%)".format(
    overlap, sc_unique, overlap*100/sc_unique if sc_unique else 0))

sc_enriched = conn.execute(
    "SELECT COUNT(DISTINCT c.id) FROM components c "
    "INNER JOIN supply_chain sc ON upper(trim(sc.mpn)) = upper(trim(c.manufacturer_part_number)) "
    "INNER JOIN specifications s ON s.component_id = c.id "
    "WHERE s.spec_name = '_enriched' AND s.spec_value = '1'"
).fetchone()[0]
print("  Supply chain LLM enriched:   {:>8,} / {} ({:.0f}%)".format(
    sc_enriched, overlap, sc_enriched*100/overlap if overlap else 0))

has_p2p = conn.execute(
    "SELECT COUNT(*) FROM supply_chain WHERE p2p_mpn IS NOT NULL AND p2p_mpn != ''"
).fetchone()[0]
print("  With P2P alternative:        {:>8,} / {} ({:.0f}%)".format(
    has_p2p, sc_total, has_p2p*100/sc_total if sc_total else 0))

print("")
print("SPECS CACHE")
try:
    cache_rows = conn.execute("SELECT COUNT(*) FROM specs_cache").fetchone()[0]
    print("  Cache rows:                  {:>8,}".format(cache_rows))
except:
    print("  Cache table:                 MISSING")

print("")
print("DATASHEET QUEUE")
try:
    q_found = conn.execute("SELECT COUNT(*) FROM datasheet_queue WHERE status = 'found'").fetchone()[0]
    q_pending = conn.execute("SELECT COUNT(*) FROM datasheet_queue WHERE status IN ('pending', 'not_found')").fetchone()[0]
    q_exhausted = conn.execute("SELECT COUNT(*) FROM datasheet_queue WHERE status = 'not_found_multi'").fetchone()[0]
    print("  Found:                       {:>8,}".format(q_found))
    print("  Pending:                     {:>8,}".format(q_pending))
    print("  Exhausted (all sources):     {:>8,}".format(q_exhausted))
except:
    print("  Queue table:                 MISSING")

print("")
print("DATABASE FILE")
size_mb = os.path.getsize("ic_database.db") / (1024*1024)
print("  File size:                   {:>7.1f} MB".format(size_mb))

tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()
print("  Tables:                      {:>8}".format(len(tables)))
for t in tables:
    cnt = conn.execute("SELECT COUNT(*) FROM [{}]".format(t[0])).fetchone()[0]
    print("    {:<30s} {:>8,} rows".format(t[0], cnt))

conn.close()
print("")
print("=" * 60)
