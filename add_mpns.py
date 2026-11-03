"""Make new MPNs searchable: find the datasheet, extract specs, update the spec cache.

  python add_mpns.py -c ldo_ic AP2112K-3.3TRG1 TPS7A2018PDBVR
  python add_mpns.py -c dcdc_converter --file new_parts.txt

Per MPN: reuse the stored datasheet URL or search LCSC / Alldatasheet / Datasheet4U (a PDF is only
accepted if it names the MPN), stream the PDF into the LLM + regex extractor, then store the part,
its specs and its specs_cache row. Alternatives can be looked up straight away; no LLM call is
needed at lookup time.
"""
import argparse
import json
import os
import re
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from playwright.sync_api import sync_playwright

import find_datasheets_multi as fdm
import finder_extras.llm_parser as lp
from config import CATEGORIES, DB_PATH
from enrich_local import pdf_text_from_url


def find_datasheet_url(mpn):
    """First source whose PDF names the MPN; returns (url, search_result) or (None, None)."""
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True, channel="msedge")
        page = browser.new_context(user_agent="Mozilla/5.0").new_page()
        try:
            for fn in (fdm.search_lcsc, fdm.search_alldatasheet, fdm.search_datasheet4u):
                try:
                    cand, pdf_path = fdm.validated_candidate(fn(page, mpn), mpn)
                except Exception as exc:
                    print(f"   {fn.__name__} failed: {str(exc)[:80]}")
                    continue
                if cand and pdf_path:
                    if os.path.exists(pdf_path):
                        os.remove(pdf_path)  # only the URL is kept
                    return cand["datasheet_url"], cand
        finally:
            browser.close()
    return None, None


def add_mpn(conn, mpn, category):
    row = conn.execute("SELECT id, datasheet_url, package FROM components WHERE upper(manufacturer_part_number)=upper(?)",
                       (mpn,)).fetchone()
    url = row[1] if row and (row[1] or "").startswith(("http", "//")) else None
    found = {}
    if not url:
        url, found = find_datasheet_url(mpn)
    if not url:
        print(f"{mpn}: datasheet not found")
        return False

    if row:
        comp_id, package = row[0], row[2] or ""
        conn.execute("UPDATE components SET datasheet_url=?, category=? WHERE id=?", (url, category, comp_id))
    else:
        package = found.get("package", "")
        comp_id = conn.execute(
            "INSERT INTO components (manufacturer_part_number, manufacturer, description, category, datasheet_url, package, source) "
            "VALUES (?,?,?,?,?,?, 'admin')",
            (mpn, found.get("manufacturer", ""), found.get("description", ""), category, url, package)).lastrowid

    text = pdf_text_from_url(url)
    if len(text) < 500:
        print(f"{mpn}: datasheet found but no extractable text ({url})")
        conn.commit()
        return False
    specs, _ = lp.extract_with_llm(lp._datasheet_context(text, mpn, category), mpn, category, package)
    specs = lp._fill_missing_specs_with_regex(category, specs, text)

    for name, value in specs.items():
        conn.execute("DELETE FROM specifications WHERE component_id=? AND spec_name=?", (comp_id, name))
        conn.execute("INSERT INTO specifications (component_id, spec_name, spec_value) VALUES (?,?,?)", (comp_id, name, value))
    conn.execute("DELETE FROM specifications WHERE component_id=? AND spec_name='_enriched'", (comp_id,))
    conn.execute("INSERT INTO specifications (component_id, spec_name, spec_value) VALUES (?,?,?)",
                 (comp_id, "_enriched", "1" if specs else "0"))
    all_specs = dict(conn.execute("SELECT spec_name, spec_value FROM specifications "
                                  "WHERE component_id=? AND substr(spec_name,1,1)<>'_'", (comp_id,)))
    conn.execute("INSERT OR REPLACE INTO specs_cache (component_id, specs_json) VALUES (?,?)", (comp_id, json.dumps(all_specs)))
    conn.commit()
    print(f"{mpn}: added to {category} with {len(all_specs)} specs")
    return bool(specs)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mpns", nargs="*")
    ap.add_argument("-c", "--category", required=True, choices=sorted(CATEGORIES))
    ap.add_argument("--file", help="text file with MPNs separated by whitespace or commas")
    args = ap.parse_args()

    mpns = list(args.mpns)
    if args.file:
        mpns += re.split(r"[\s,;]+", open(args.file, encoding="utf-8").read())
    mpns = list(dict.fromkeys(m.strip() for m in mpns if m.strip()))
    if not mpns:
        ap.error("no MPNs given")

    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.execute("CREATE TABLE IF NOT EXISTS specs_cache (component_id INTEGER PRIMARY KEY, specs_json TEXT)")
    ok = sum(add_mpn(conn, m, args.category) for m in mpns)
    print(f"done: {ok}/{len(mpns)} ready for lookup")


if __name__ == "__main__":
    main()
