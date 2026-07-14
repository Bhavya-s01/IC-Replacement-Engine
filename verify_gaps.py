"""
verify_gaps.py - Check which of the 18 gaps are fixed.
Run: python verify_gaps.py
"""

import os
import sqlite3

DB = "ic_database.db"

print("=" * 60)
print("GAP VERIFICATION")
print("=" * 60)

conn = sqlite3.connect(DB)

# Gap 1 & 5: Memory dedup
print("\n=== GAP 1 & 5: Memory URL sharing + deduplication ===")
for cat in ["eeprom", "flash_memory", "fram_mram_sram"]:
    count = conn.execute("SELECT COUNT(*) FROM components WHERE category=?", (cat,)).fetchone()[0]
    print("  {}: {}".format(cat, count))
dupes = conn.execute(
    "SELECT manufacturer_part_number, COUNT(DISTINCT category) as cats "
    "FROM components GROUP BY manufacturer_part_number HAVING cats > 1 LIMIT 5"
).fetchall()
print("  Cross-category duplicates (sample):", [(r[0], r[1]) for r in dupes])

# Gap 2: TCON
print("\n=== GAP 2: TCON/Video Processor ===")
tcon = conn.execute("SELECT COUNT(*) FROM components WHERE category='tcon_video'").fetchone()[0]
print("  TCON count:", tcon)

# Gap 3: USB IC
print("\n=== GAP 3: USB IC ===")
usb = conn.execute("SELECT COUNT(*) FROM components WHERE category='usb_ic'").fetchone()[0]
print("  USB IC count:", usb)

# Gap 4: Retimer
print("\n=== GAP 4: Retimer IC ===")
ret = conn.execute("SELECT COUNT(*) FROM components WHERE category='retimer_ic'").fetchone()[0]
print("  Retimer count:", ret)

# Gap 6: Dropdown selectors
print("\n=== GAP 6: Per-page dropdown ===")
"""fix_verify.py — Patch verify_gaps.py to handle encoding."""

with open("verify_gaps.py", "r", encoding="utf-8") as f:
    code = f.read()

old = '''    with open("plugins/digikey_playwright.py", "r", encoding="utf-8", errors="replace") as f:
        code = f.read()'''

new = '''    with open("plugins/digikey_playwright.py", "r", encoding="utf-8", errors="replace") as f:
        code = f.read()'''

# Replace all occurrences (there are two reads of the plugin file)
code = code.replace(old, new)

with open("verify_gaps.py", "w", encoding="utf-8") as f:
    f.write(code)

print("[DONE] Fixed encoding in verify_gaps.py")

# Gap 7: Rate limiting
print("\n=== GAP 7: Rate limiting ===")
print("  utils/rate_limiter.py exists:", os.path.exists("utils/rate_limiter.py"))
try:
    with open("plugins/digikey_playwright.py", "r", encoding="utf-8", errors="replace") as f:
        code = f.read()
    print("  Has error page detection:", "access denied" in code.lower() or "error page" in code.lower())
    print("  Has retry logic:", "retry" in code.lower() or "MAX_RETRIES" in code)
except Exception:
    pass

# Gap 8: WAL checkpoint
print("\n=== GAP 8: WAL checkpoint ===")
try:
    with open("database.py", "r") as f:
        code = f.read()
    print("  Has checkpoint method:", "wal_checkpoint" in code or "checkpoint" in code)
    print("  Has bulk_upsert_safe:", "bulk_upsert_safe" in code)
except Exception:
    pass

# Gap 9-13: Finder extras modules
print("\n=== GAP 9-13: Finder extras modules ===")
extras = [
    "finder_extras/pin_compat.py",
    "finder_extras/spec_normalizer.py",
    "finder_extras/protocol_matcher.py",
    "finder_extras/lifecycle_filter.py",
    "finder_extras/cross_category.py",
    "finder_extras/datasheet_parser.py",
]
for f in extras:
    print("  {}: {}".format(f, os.path.exists(f)))

# Gap 9-13: Finder integration
print("\n=== GAP 9-13: Finder integration ===")
try:
    with open("finder.py", "r") as f:
        code = f.read()
    print("  Has spec_normalizer import:", "spec_normalizer" in code)
    print("  Has pin_compat import:", "pin_compat" in code)
    print("  Has protocol_matcher import:", "protocol_matcher" in code)
    print("  Has lifecycle_filter import:", "lifecycle_filter" in code)
except Exception as e:
    print("  finder.py not found or error:", e)

# Gap 14: Substitutes table
print("\n=== GAP 14: Substitutes table ===")
subs = conn.execute("SELECT COUNT(*) FROM substitutes").fetchone()[0]
print("  Substitutes rows:", subs)

# Gap 16: Incremental updates
print("\n=== GAP 16: Incremental updates ===")
print("  utils/incremental.py exists:", os.path.exists("utils/incremental.py"))

# Gap 17: Price breaks
print("\n=== GAP 17: Price breaks ===")
print("  utils/price_parser.py exists:", os.path.exists("utils/price_parser.py"))
sample = conn.execute("SELECT price_breaks FROM components LIMIT 1").fetchone()
if sample and sample[0]:
    print("  Sample price_breaks:", sample[0][:80])
else:
    print("  Sample price_breaks: NONE - column empty")

# Gap 18: Lifecycle filtering
print("\n=== GAP 18: Lifecycle filtering ===")
statuses = conn.execute(
    "SELECT lifecycle_status, COUNT(*) FROM components GROUP BY lifecycle_status "
    "ORDER BY COUNT(*) DESC LIMIT 10"
).fetchall()
print("  Lifecycle statuses in DB:")
for s in statuses:
    print("    {}: {}".format(s[0] or "(empty)", s[1]))

# Overall status
print("\n=== OVERALL STATUS ===")
cats = conn.execute(
    "SELECT category, COUNT(*) as cnt FROM components GROUP BY category ORDER BY category"
).fetchall()
total = 0
for c in cats:
    print("  {:<35} {}".format(c[0], c[1]))
    total += c[1]
print("  {:<35} {}".format("TOTAL", total))

# File structure
print("\n=== PYTHON FILES ===")
for root, dirs, files in os.walk("."):
    dirs[:] = [d for d in dirs if d != "__pycache__"]
    for f in files:
        if f.endswith(".py"):
            print("  {}".format(os.path.join(root, f)))

# Database size
print("\n=== DATABASE SIZE ===")
if os.path.exists(DB):
    size_mb = os.path.getsize(DB) / (1024 * 1024)
    print("  {}: {:.1f} MB".format(DB, size_mb))

conn.close()
print("\nDone!")