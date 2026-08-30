"""Audit every component datasheet URL without changing the database.

Run:
  python audit_datasheets.py
  python audit_datasheets.py --limit 100 --workers 8

The report is written to exports/datasheet_audit.csv.
"""

import argparse
import csv
import os
import re
import sqlite3
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

try:
    import fitz
except ImportError:
    fitz = None

DB_PATH = "ic_database.db"
REPORT_PATH = "exports/datasheet_audit.csv"


def classify_pdf(content, mpn):
    if not fitz:
        return "pdf_unchecked", 0, 0, "PyMuPDF unavailable"
    try:
        doc = fitz.open(stream=content, filetype="pdf")
        text = "\n".join(page.get_text() for page in doc)
        pages = len(doc)
        doc.close()
    except Exception as exc:
        return "invalid_pdf", 0, 0, str(exc)[:120]

    normalized = re.sub(r"[^a-z0-9]+", " ", text.lower())
    compact = re.sub(r"[^a-z0-9]+", "", text.lower())
    mpn_compact = re.sub(r"[^a-z0-9]+", "", (mpn or "").lower())
    # A family document is acceptable only when it names the exact ordering
    # MPN or the core family.  This catches links accidentally assigned from a
    # neighbouring search result while retaining legitimate family datasheets.
    core_match = re.match(r"[a-z]+\d+", mpn_compact)
    core = core_match.group(0) if core_match else mpn_compact
    has_identity = bool(mpn_compact and (mpn_compact in compact or (len(core) >= 5 and core in compact)))
    compliance_only = any(term in normalized for term in (
        "environmental compliance statement",
        "material declaration",
        "rohs declaration",
        "reach declaration",
    )) and not any(term in normalized for term in (
        "electrical characteristics", "absolute maximum", "pin configuration",
        "application circuit", "block diagram", "output voltage",
    ))
    electrical_terms = sum(normalized.count(term) for term in (
        "electrical characteristics", "absolute maximum", "input voltage",
        "output voltage", "operating temperature", "pin configuration",
        "application circuit", "typical characteristics", "ordering information",
    ))
    if not has_identity:
        status = "wrong_mpn_document"
    elif compliance_only:
        status = "wrong_compliance_document"
    elif len(text) < 100:
        status = "no_readable_text"
    elif electrical_terms < 2:
        status = "suspicious_no_electrical_content"
    else:
        status = "ok"
    return status, pages, len(text), "electrical_terms={} identity={}".format(electrical_terms, has_identity)


def audit_one(row):
    url = row["datasheet_url"]
    result = {
        "component_id": row["id"],
        "mpn": row["manufacturer_part_number"],
        "category": row["category"] or "",
        "url": url,
        "http_status": "",
        "content_type": "",
        "status": "",
        "pages": 0,
        "text_chars": 0,
        "details": "",
    }
    try:
        response = requests.get(
            url,
            timeout=20,
            verify=False,
            headers={"User-Agent": "Mozilla/5.0"},
        )
        result["http_status"] = response.status_code
        result["content_type"] = response.headers.get("content-type", "")[:100]
        if response.status_code >= 400:
            result["status"] = "http_error"
            result["details"] = "HTTP {}".format(response.status_code)
            return result
        content = response.content
        if content[:5] == b"%PDF-":
            result["status"], result["pages"], result["text_chars"], result["details"] = classify_pdf(
                content, row["manufacturer_part_number"]
            )
        elif "html" in result["content_type"].lower() or b"<html" in content[:500].lower():
            text = re.sub(r"<[^>]+>", " ", content.decode("utf-8", errors="replace"))
            text = re.sub(r"\s+", " ", text).strip()
            result["text_chars"] = len(text)
            result["status"] = "html_wrapper" if len(text) >= 100 else "html_empty"
        else:
            result["status"] = "not_pdf_or_html"
    except Exception as exc:
        result["status"] = "request_error"
        result["details"] = str(exc).splitlines()[0][:120]
    return result


def main(limit=None, workers=12):
    os.makedirs(os.path.dirname(REPORT_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    query = """
        SELECT id, manufacturer_part_number, category, datasheet_url
        FROM components
        WHERE datasheet_url IS NOT NULL AND TRIM(datasheet_url) <> ''
        ORDER BY id
    """
    rows = conn.execute(query).fetchall()
    conn.close()
    if limit:
        rows = rows[:limit]

    fields = [
        "component_id", "mpn", "category", "url", "http_status",
        "content_type", "status", "pages", "text_chars", "details",
    ]

    # Resume completed rows when the component and URL are unchanged.  A
    # changed URL is audited again instead of trusting stale evidence.
    # Keep only one result per current (component_id, URL) pair. Entries for
    # URLs that have since changed are stale and must not remain in the report.
    current_keys = {(str(row["id"]), row["datasheet_url"]) for row in rows}
    completed = {}
    if os.path.exists(REPORT_PATH):
        with open(REPORT_PATH, newline="", encoding="utf-8") as handle:
            for result in csv.DictReader(handle):
                key = (result.get("component_id"), result.get("url"))
                if key in current_keys:
                    completed[key] = result

    pending_rows = [
        row for row in rows
        if (str(row["id"]), row["datasheet_url"]) not in completed
    ]
    print("Already audited: {}; remaining: {}".format(
        len(rows) - len(pending_rows), len(pending_rows)
    ))

    # Rewrite the checkpoint file only once at startup, then append each
    # finished result so Ctrl+C preserves all completed work.
    with open(REPORT_PATH, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(completed.values())
        handle.flush()

        results = list(completed.values())
        try:
            with ThreadPoolExecutor(max_workers=workers) as pool:
                futures = [pool.submit(audit_one, row) for row in pending_rows]
                for index, future in enumerate(as_completed(futures), 1):
                    result = future.result()
                    writer.writerow(result)
                    handle.flush()
                    results.append(result)
                    if index % 100 == 0:
                        print("Audited {}/{}".format(index, len(pending_rows)), flush=True)
        except KeyboardInterrupt:
            print("Audit stopped safely; completed rows are saved in {}".format(REPORT_PATH))

    counts = {}
    for result in results:
        counts[result["status"]] = counts.get(result["status"], 0) + 1
    print("=== DATASHEET AUDIT ===")
    print("URLs audited: {}".format(len(results)))
    for status, count in sorted(counts.items()):
        print("{:<32} {:>6}".format(status, count))
    print("Report: {}".format(REPORT_PATH))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--workers", type=int, default=12)
    args = parser.parse_args()
    main(limit=args.limit, workers=args.workers)
