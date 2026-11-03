"""Retry datasheet search for supply-chain parts with simplified part numbers (no LLM credits).

Many MPNs carry packaging/ordering suffixes (-TR, TRG1, -7, #PBF...) that datasheet sites do not index.
For each supply-chain part still lacking a datasheet URL we search the base part number instead,
validate that the PDF names that base part, and store the URL (the PDF itself is not kept).

  python retry_datasheets.py [--limit N]
"""
import argparse
import logging
import os
import re
import sqlite3
import time

from playwright.sync_api import sync_playwright

import find_datasheets_multi as fdm

log = logging.getLogger("retry_ds")
DB_PATH = "ic_database.db"
SUFFIX = re.compile(r"[-_/#.]?(TR[A-Z0-9]*|TAPE|REEL|T&R|PBF|G\d|-?\d{1,2}[A-Z]?|[A-Z]{1,2})$", re.I)


def variants(mpn):
    """Simplified search names, most specific first, excluding the original (already tried)."""
    out, cur = [], re.sub(r"\(.*?\)", "", mpn).strip()
    for _ in range(3):
        nxt = SUFFIX.sub("", cur)
        if nxt == cur or len(nxt) < 6:
            break
        out.append(nxt)
        cur = nxt
    core = re.match(r"[A-Za-z]+\d+[A-Za-z]?\d*", mpn)
    if core and len(core.group(0)) >= 6:
        out.append(core.group(0))
    seen, res = {mpn.upper()}, []
    for v in out:
        if v.upper() not in seen:
            seen.add(v.upper())
            res.append(v)
    return res[:3]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(message)s")
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute("""SELECT DISTINCT c.id, c.manufacturer_part_number FROM components c
        JOIN supply_chain s ON upper(s.mpn)=upper(c.manufacturer_part_number)
        WHERE c.category NOT IN ('other','unknown') AND (c.datasheet_url IS NULL OR c.datasheet_url NOT LIKE 'http%')""").fetchall()
    if args.limit:
        rows = rows[:args.limit]
    log.info("%d parts to retry", len(rows))
    sources = [("LCSC", fdm.search_lcsc), ("Alldatasheet", fdm.search_alldatasheet), ("Datasheet4U", fdm.search_datasheet4u)]
    found = 0
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True, channel="msedge")
        page = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120 Safari/537.36 Edg/120").new_page()
        for cid, mpn in rows:
            hit = None
            for v in variants(mpn):
                for name, fn in sources:
                    try:
                        res, pdf = fdm.validated_candidate(fn(page, v), v)
                    except Exception as exc:
                        log.info("  %s failed for %s: %s", name, v, str(exc)[:60])
                        continue
                    if res:
                        hit = (res["datasheet_url"], v, name)
                        if pdf and os.path.exists(pdf):
                            os.remove(pdf)
                        break
                    time.sleep(1)
                if hit:
                    break
            if hit:
                conn.execute("UPDATE components SET datasheet_url=? WHERE id=?", (hit[0], cid))
                conn.commit()
                found += 1
                log.info("FOUND %s via %s (%s): %s", mpn, hit[2], hit[1], hit[0][:70])
            else:
                log.info("none  %s", mpn)
        browser.close()
    log.info("done: %d/%d found", found, len(rows))


if __name__ == "__main__":
    main()
