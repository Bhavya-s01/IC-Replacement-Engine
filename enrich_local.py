"""Extract specs from datasheet PDFs with the LLM (+ regex fallback). Resumable and throttled.

  python enrich_local.py                   # all PDFs in datasheets/ -> exports/enrich_results.json
  python enrich_local.py --limit 5
  python enrich_local.py --write           # also store specs in ic_database.db

Results are cached per MPN in the JSON file, so re-runs skip finished parts and retry failures.
"""
import argparse
import json
import os
import re
import sqlite3
import sys
import time

import fitz
import requests
import urllib3

urllib3.disable_warnings()

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import finder_extras.llm_parser as lp

DB_PATH = "ic_database.db"
OUT = "exports/enrich_results.json"
norm = lambda s: re.sub(r"[^a-z0-9]", "", (s or "").lower())


def pdf_text_from_url(url, max_pages=80):
    """Download a PDF into memory (nothing is written to disk) and return its text."""
    url = ("https:" + url) if url.startswith("//") else url
    resp = requests.get(url, timeout=40, verify=False, headers={"User-Agent": "Mozilla/5.0"})
    if resp.status_code != 200 or resp.content[:5] != b"%PDF-":
        return ""
    with fitz.open(stream=resp.content, filetype="pdf") as doc:
        return "\n\n".join(doc[i].get_text() for i in range(min(max_pages, len(doc))))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default="datasheets")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--delay", type=float, default=4.0, help="seconds between LLM calls (free-tier rate limit)")
    ap.add_argument("--supply-chain", action="store_true",
                    help="process supply-chain parts that have a datasheet URL (PDF streamed in memory)")
    ap.add_argument("--write", action="store_true", help="store specs in the database")
    args = ap.parse_args()

    conn = sqlite3.connect(DB_PATH)
    comps = {norm(m): (i, m, c, p or "") for i, m, c, p in conn.execute(
        "SELECT id, manufacturer_part_number, category, package FROM components")}
    results = json.load(open(OUT, encoding="utf-8")) if os.path.exists(OUT) else {}
    if args.supply_chain:
        rows = conn.execute("""SELECT DISTINCT c.manufacturer_part_number, c.datasheet_url FROM components c
                               JOIN supply_chain s ON upper(s.mpn)=upper(c.manufacturer_part_number)
                               WHERE c.datasheet_url LIKE 'http%' OR c.datasheet_url LIKE '//%'""").fetchall()
        urls = {m: u for m, u in rows}
        files = [m + ".pdf" for m in sorted(urls)]
    else:
        urls = {}
        files = sorted(f for f in os.listdir(args.dir) if f.lower().endswith(".pdf"))
    todo = [f for f in files if not results.get(f[:-4], {}).get("specs")]
    if args.limit:
        todo = todo[:args.limit]
    print(f"{len(files)} PDFs, {len(todo)} to process")

    for n, f in enumerate(todo, 1):
        mpn = f[:-4]
        cid, db_mpn, cat, pkg = comps.get(norm(mpn), (None, mpn, "", ""))
        try:
            text = pdf_text_from_url(urls[mpn]) if args.supply_chain else lp.extract_pdf_text(os.path.join(args.dir, f))
        except Exception as exc:
            text = ""
            print(f"   download/parse failed: {exc}"[:150])
        if len(text) < 500:
            results[mpn] = {"category": cat, "error": "no extractable text / download failed"}
        else:
            specs, pins = lp.extract_with_llm(lp._datasheet_context(text, mpn, cat), mpn, cat, pkg)
            llm_n = len(specs)
            specs = lp._fill_missing_specs_with_regex(cat, specs, text)
            results[mpn] = {"category": cat, "url": urls.get(mpn), "specs": specs, "llm_specs": llm_n, "pins": len(pins),
                            "error": None if specs else "llm+regex found nothing"}
        r = results[mpn]
        print(f"[{n}/{len(todo)}] {mpn:28} {cat:16} specs={len(r.get('specs', {}))} llm={r.get('llm_specs', 0)} {r['error'] or ''}", flush=True)
        os.makedirs("exports", exist_ok=True)
        json.dump(results, open(OUT, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
        time.sleep(args.delay)

    if args.write:  # store every cached result, including ones extracted in earlier runs
        stored = 0
        for mpn, r in results.items():
            hit = comps.get(norm(mpn))
            if not hit or not r.get("specs"):
                continue
            for k, v in r["specs"].items():
                conn.execute("DELETE FROM specifications WHERE component_id=? AND spec_name=?", (hit[0], k))
                conn.execute("INSERT INTO specifications (component_id, spec_name, spec_value) VALUES (?,?,?)", (hit[0], k, v))
            conn.execute("DELETE FROM specifications WHERE component_id=? AND spec_name='_enriched'", (hit[0],))
            conn.execute("INSERT INTO specifications (component_id, spec_name, spec_value) VALUES (?,?,?)", (hit[0], "_enriched", "1"))
            stored += 1
        conn.commit()
        print(f"stored specs for {stored} parts")


if __name__ == "__main__":
    main()
