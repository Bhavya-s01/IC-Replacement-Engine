"""Safely clear datasheet links proven bad by audit_datasheets.py.

Default mode is a report only.  Use --apply only after a fresh audit; a SQLite
backup is created first.  Supply-chain MPNs are listed and processed first.
"""

import argparse
import csv
import json
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path


DB_PATH = Path("ic_database.db")
AUDIT_PATH = Path("exports/datasheet_audit.csv")
BAD_STATUSES = {
    "invalid_pdf", "not_pdf_or_html",
    "html_empty", "wrong_compliance_document", "wrong_mpn_document",
    "no_readable_text", "suspicious_no_electrical_content",
}


def audit_rows(path):
    with path.open(newline="", encoding="utf-8") as handle:
        rows = []
        for row in csv.DictReader(handle):
            status = row.get("status")
            # Connection failures and access-denied responses are environmental
            # outcomes, not proof that a saved manufacturer URL is wrong.
            # Only confirmed-gone URLs are safe to clear automatically.
            confirmed_http_gone = (
                status == "http_error" and row.get("http_status") in {"404", "410"}
            )
            if status in BAD_STATUSES or confirmed_http_gone:
                rows.append(row)
        return rows


def reset_parser_specs(conn, component_id):
    row = conn.execute(
        "SELECT spec_value FROM specifications WHERE component_id=? "
        "AND spec_name='_validation' ORDER BY id DESC LIMIT 1", (component_id,)
    ).fetchone()
    if row:
        try:
            metadata = json.loads(row[0])
            names = metadata.get("stored_specs", metadata.get("specs", []))
            if names:
                conn.execute(
                    "DELETE FROM specifications WHERE component_id=? AND spec_name IN ({})".format(
                        ",".join("?" for _ in names)
                    ), [component_id, *names]
                )
        except (TypeError, ValueError, json.JSONDecodeError):
            pass
    conn.execute(
        "DELETE FROM specifications WHERE component_id=? AND spec_name IN ('_enriched', '_validation')",
        (component_id,),
    )


def main(apply=False, audit_path=AUDIT_PATH):
    if not audit_path.exists():
        raise SystemExit("No audit report found. Run audit_datasheets.py first.")
    bad = audit_rows(audit_path)
    if not bad:
        print("No bad URLs in audit report.")
        return

    conn = sqlite3.connect(DB_PATH)
    ids = [int(row["component_id"]) for row in bad]
    placeholders = ",".join("?" for _ in ids)
    rows = conn.execute(
        "SELECT c.id, c.manufacturer_part_number, c.datasheet_url, "
        "EXISTS(SELECT 1 FROM supply_chain sc WHERE upper(trim(sc.mpn)) = upper(trim(c.manufacturer_part_number))) "
        "FROM components c WHERE c.id IN ({}) ORDER BY 4 DESC, c.manufacturer_part_number".format(placeholders), ids,
    ).fetchall()
    priority = sum(bool(row[3]) for row in rows)
    print("Bad component URLs: {} (supply-chain priority: {})".format(len(rows), priority))
    for row in rows[:20]:
        print("{} {}{}".format(row[0], row[1], " [supply-chain]" if row[3] else ""))
    if not apply:
        print("Dry run only. Re-run with --apply after reviewing the audit.")
        conn.close()
        return

    backup = DB_PATH.with_name("ic_database.before_url_repair_{}.db".format(datetime.now().strftime("%Y%m%d_%H%M%S")))
    conn.close()
    shutil.copy2(DB_PATH, backup)
    conn = sqlite3.connect(DB_PATH)
    for component_id, _, _, _ in rows:
        conn.execute("UPDATE components SET datasheet_url='' WHERE id=?", (component_id,))
        reset_parser_specs(conn, component_id)
    conn.commit()
    conn.close()
    print("Cleared {} bad URLs. Backup: {}".format(len(rows), backup))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--audit", type=Path, default=AUDIT_PATH)
    args = parser.parse_args()
    main(args.apply, args.audit)
