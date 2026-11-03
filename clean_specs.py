"""Remove spec rows that do not belong to a component's category.

DigiKey spec tables differ per product type, so a part scraped into the wrong
category carries foreign specs (e.g. connector fields on an opto IC). Only
specs listed in ALLOWED for the category are kept; everything else is deleted
so it can be repopulated from DigiKey / datasheets later.

Run:  python clean_specs.py          (dry run)
      python clean_specs.py --apply  (back up DB, delete, rebuild cache)
"""
import shutil
import sqlite3
import sys
from collections import Counter

DB_PATH = "ic_database.db"

# Variants of the same spec -> canonical name used by match_rules.
RENAME = {"Supply Voltage": "Voltage - Supply", "Voltage - Supply (Vcc/Vdd)": "Voltage - Supply",
          "Current - Output (Max)": "Current - Output"}

JUNK = {"Series", "Grade", "Qualification", "DigiKey Programmable", "Applications", "Test Condition",
        "For Use With/Related Products", "Includes", "Contents", "Packaging", "Part Status"}


def main(apply):
    conn = sqlite3.connect(DB_PATH)
    if apply:
        conn.close()
        shutil.copy(DB_PATH, DB_PATH + ".bak")
        conn = sqlite3.connect(DB_PATH)
        for old, new in RENAME.items():  # keep an existing canonical row, else rename
            conn.execute("""UPDATE specifications SET spec_name=? WHERE spec_name=? AND NOT EXISTS (
                SELECT 1 FROM specifications s2 WHERE s2.component_id=specifications.component_id
                AND s2.spec_name=?)""", (new, old, new))
    rows = conn.execute("""SELECT s.id, c.category, s.spec_name FROM specifications s
                           JOIN components c ON c.id = s.component_id""").fetchall()
    bad, kept = [], Counter()
    for sid, cat, name in rows:
        # DigiKey tables are now scraped from the correct pages, so keep every field except
        # non-technical junk; parts in 'other' (non-IC leftovers) keep nothing.
        ok = name.startswith("_") or name == "Pin Count" or (cat not in ("other", "unknown") and name not in JUNK)
        (kept.update([cat]) if ok else bad.append((sid, cat)))
    print(f"{len(rows)} spec rows: keeping {sum(kept.values())}, removing {len(bad)}")
    print("removed by category:", dict(Counter(c for _, c in bad)))
    if apply:
        conn.executemany("DELETE FROM specifications WHERE id=?", [(i,) for i, _ in bad])
        conn.execute("DROP TABLE IF EXISTS specs_wide")  # stale, unused derived table
        conn.commit()
        conn.execute("VACUUM")
        conn.close()
        import build_specs_cache  # noqa: F401  (rebuilds specs_cache on import)


if __name__ == "__main__":
    main("--apply" in sys.argv)
