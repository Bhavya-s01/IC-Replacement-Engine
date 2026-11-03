"""Fill sparse supply-chain targets from the Excel part description (one LLM call per batch).

Only values stated in the description are accepted (no recall from memory), so this adds
rough but safe specs for parts that have no datasheet and are not on DigiKey.

  python enrich_from_description.py            # extract -> exports/desc_results.json
  python enrich_from_description.py --write    # also store in ic_database.db
"""
import argparse
import json
import os
import sqlite3
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import finder_extras.llm_parser as lp
from match_rules import get_rules

DB_PATH, OUT, BATCH, MIN_SPECS = "ic_database.db", "exports/desc_results.json", 15, 3


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()
    conn = sqlite3.connect(DB_PATH)
    clients = lp._get_clients()
    if not clients:
        sys.exit("No LLM configured (.env)")
    _, client, model = clients[0]

    rows = conn.execute("""SELECT c.id, c.manufacturer_part_number, c.category, s.parts_description, s.package_type, s.pin_count
        FROM components c JOIN supply_chain s ON upper(s.mpn)=upper(c.manufacturer_part_number)
        GROUP BY c.id""").fetchall()
    todo = defaultdict(list)
    for cid, mpn, cat, desc, pkg, pins in rows:
        n = conn.execute("SELECT COUNT(*) FROM specifications WHERE component_id=? AND substr(spec_name,1,1)<>'_'", (cid,)).fetchone()[0]
        if n < MIN_SPECS and desc and cat not in ("other", "unknown"):
            todo[cat].append((cid, mpn, desc, pkg, pins))

    results = json.load(open(OUT, encoding="utf-8")) if os.path.exists(OUT) else {}
    for cat, items in todo.items():
        names = sorted({r.spec_name for r in get_rules(cat).rules})
        items = [i for i in items if i[1] not in results]
        for k in range(0, len(items), BATCH):
            chunk = items[k:k + BATCH]
            listing = "\n".join(f"{m} | {d} | package {p} | {n} pins" for _, m, d, p, n in chunk)
            prompt = (f"IC category: {cat}. For each part below, extract specs that are EXPLICITLY stated in its "
                      f"description (e.g. '18V 3.5A', 'Buck', '2A'). Use only these spec names: {', '.join(names)}. "
                      "Include units in values (e.g. '3.5 A'). Never guess from the part number. Omit unknown specs. "
                      'Return JSON only: {"<part number>": {"<spec name>": "<value>"}}.\n\n' + listing)
            try:
                resp = client.chat.completions.create(model=model, temperature=0, max_tokens=4096,
                                                      response_format={"type": "json_object"},
                                                      messages=[{"role": "user", "content": prompt}])
                data = json.loads(resp.choices[0].message.content)
            except Exception as exc:
                print(f"{cat}: batch failed: {exc}"[:150])
                continue
            for _, mpn, *_ in chunk:
                good = {}
                for name, val in (data.get(mpn) or {}).items():
                    canon = lp._canonical_spec_name(name, cat) or (name if name in names else None)
                    if canon and val and lp._validate_spec(canon, str(val))[0]:
                        good[canon] = lp._normalize_value(str(val))
                results[mpn] = good
            print(f"{cat}: {k + len(chunk)}/{len(items)} done", flush=True)
            json.dump(results, open(OUT, "w", encoding="utf-8"), indent=1, ensure_ascii=False)

    if args.write:
        ids = {m: i for i, m, *_ in rows}
        stored = 0
        for mpn, specs in results.items():
            for k, v in specs.items():
                if conn.execute("SELECT 1 FROM specifications WHERE component_id=? AND spec_name=?", (ids[mpn], k)).fetchone():
                    continue
                conn.execute("INSERT INTO specifications (component_id, spec_name, spec_value) VALUES (?,?,?)", (ids[mpn], k, v))
                stored += 1
        conn.commit()
        print("stored", stored, "specs")


if __name__ == "__main__":
    main()
