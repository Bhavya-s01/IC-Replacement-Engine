"""
verify_integration.py — Check all layers are connected.
Run: python verify_integration.py
"""

import sqlite3
import os

DB = "ic_database.db"

print("=" * 60)
print("INTEGRATION VERIFICATION")
print("=" * 60)

# 1. Check supply_chain table exists
conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row

print("\n1. SUPPLY CHAIN TABLE")
try:
    total = conn.execute("SELECT COUNT(*) FROM supply_chain").fetchone()[0]
    print("   Total entries: {}".format(total))

    by_odm = conn.execute(
        "SELECT odm_name, COUNT(*) as cnt FROM supply_chain "
        "GROUP BY odm_name ORDER BY cnt DESC"
    ).fetchall()
    for r in by_odm:
        print("   {}: {}".format(r[0], r[1]))
except Exception as e:
    print("   ERROR: {}".format(e))
    print("   Run: python import_template.py")

# 2. Check overlap with components
print("\n2. OVERLAP WITH SCRAPED DATABASE")
try:
    overlap = conn.execute(
        "SELECT DISTINCT sc.mpn, sc.odm_name, sc.mpn_category "
        "FROM supply_chain sc "
        "INNER JOIN components c ON c.manufacturer_part_number = sc.mpn "
        "ORDER BY sc.mpn"
    ).fetchall()
    print("   Parts with BOTH technical + supply chain data: {}".format(len(overlap)))
    for r in overlap[:10]:
        print("     {} | {} | {}".format(r[0], r[1], r[2]))
    if len(overlap) > 10:
        print("     ... and {} more".format(len(overlap) - 10))
except Exception as e:
    print("   ERROR: {}".format(e))

# 3. Check P2P solutions
print("\n3. P2P SOLUTIONS")
try:
    p2p = conn.execute(
        "SELECT mpn, p2p_supplier, p2p_mpn FROM supply_chain "
        "WHERE p2p_mpn IS NOT NULL LIMIT 5"
    ).fetchall()
    print("   Parts with P2P solutions: {}".format(
        conn.execute("SELECT COUNT(*) FROM supply_chain WHERE p2p_mpn IS NOT NULL").fetchone()[0]
    ))
    for r in p2p:
        print("     {} -> {}: {}".format(r[0], r[1], r[2]))
except Exception as e:
    print("   ERROR: {}".format(e))

# 4. Check api.py has supply chain endpoints
print("\n4. API ENDPOINTS")
try:
    with open("api.py", "r") as f:
        api_code = f.read()
    has_sc_stats = "supply-chain-stats" in api_code
    has_sc_mpn = "supply-chain/{mpn" in api_code or "supply-chain/" in api_code
    print("   /api/supply-chain-stats endpoint: {}".format(
        "FOUND" if has_sc_stats else "MISSING"))
    print("   /api/supply-chain/{{mpn}} endpoint: {}".format(
        "FOUND" if has_sc_mpn else "MISSING"))
except Exception as e:
    print("   ERROR reading api.py: {}".format(e))

# 5. Check api.ts has supply chain calls
print("\n5. FRONTEND API CLIENT")
api_ts_paths = [
    os.path.join("..", "ic-finder-ui", "src", "api.ts"),
    os.path.join("ic-finder-ui", "src", "api.ts"),
]
found_ts = False
for path in api_ts_paths:
    if os.path.exists(path):
        with open(path, "r") as f:
            ts_code = f.read()
        has_sc = "supplyChain" in ts_code or "supply-chain" in ts_code
        has_sc_stats = "supplyChainStats" in ts_code or "supply-chain-stats" in ts_code
        print("   File: {}".format(path))
        print("   supplyChain() call: {}".format("FOUND" if has_sc else "MISSING"))
        print("   supplyChainStats() call: {}".format("FOUND" if has_sc_stats else "MISSING"))
        found_ts = True
        break
if not found_ts:
    print("   api.ts NOT FOUND - check path")

# 6. Check App.tsx has supply chain display
print("\n6. FRONTEND UI COMPONENTS")
app_tsx_paths = [
    os.path.join("..", "ic-finder-ui", "src", "App.tsx"),
    os.path.join("ic-finder-ui", "src", "App.tsx"),
]
found_tsx = False
for path in app_tsx_paths:
    if os.path.exists(path):
        with open(path, "r") as f:
            tsx_code = f.read()
        has_sc_state = "supplyChainData" in tsx_code or "supplyChainStats" in tsx_code
        has_sc_button = "Supply Chain" in tsx_code
        has_sc_display = "sourcing" in tsx_code and "lead_time" in tsx_code
        print("   File: {}".format(path))
        print("   Supply chain state variables: {}".format("FOUND" if has_sc_state else "MISSING"))
        print("   Supply Chain button/label: {}".format("FOUND" if has_sc_button else "MISSING"))
        print("   Sourcing/lead time display: {}".format("FOUND" if has_sc_display else "MISSING"))
        found_tsx = True
        break
if not found_tsx:
    print("   App.tsx NOT FOUND - check path")

# 7. Summary
print("\n" + "=" * 60)
print("WHAT TO SEARCH FOR IN THE UI")
print("=" * 60)
try:
    searchable = conn.execute(
        "SELECT DISTINCT sc.mpn FROM supply_chain sc "
        "INNER JOIN components c ON c.manufacturer_part_number = sc.mpn "
        "LIMIT 5"
    ).fetchall()
    if searchable:
        print("\nSearch for these MPNs to see supply chain data:")
        for r in searchable:
            print("  -> {}".format(r[0]))
    else:
        print("\nNo overlapping parts found between supply chain and scraped DB.")
        print("The supply chain data exists but those MPNs aren't in DigiKey DB.")
        print("\nYou can still see supply chain stats on the dashboard.")
        print("Search for any of these template MPNs:")
        some = conn.execute("SELECT mpn FROM supply_chain LIMIT 5").fetchall()
        for r in some:
            print("  -> {} (supply chain only, no technical data)".format(r[0]))
except Exception:
    pass

conn.close()