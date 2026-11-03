"""
Datasheet Parser v3 — Patterns tuned to actual PDF text formats.

PyMuPDF extracts text with table structure preserved as spaces/newlines.
The patterns below match the ACTUAL text found in datasheets like MIC5501,
AP2112K, TPS51200, etc. — not idealized "spec: value" format.

Requires: pip install pymupdf requests
"""

import os
import re
import json
import logging

log = logging.getLogger(__name__)

try:
    import fitz
    PYMUPDF_OK = True
except ImportError:
    PYMUPDF_OK = False

try:
    REQUESTS_OK = True
except ImportError:
    REQUESTS_OK = False


def _max_pins_from_package(package_str):
    if not package_str:
        return None
    m = re.search(r"(\d+)\s*$", package_str.strip())
    if m:
        return int(m.group(1))
    pkg = package_str.lower()
    for k, v in {"sot-23": 3, "sot23": 3, "sc-59": 3, "sot-89": 3,
                  "to-92": 3, "to-252": 3, "to-263": 3}.items():
        if k in pkg:
            return v
    return None


PIN_FUNCTIONS = {
    "VIN": "power_input", "VCC": "power_input", "VDD": "power_input",
    "VOUT": "power_output", "OUT": "power_output", "SW": "power_output",
    "GND": "ground", "VSS": "ground", "AGND": "ground", "PGND": "ground",
    "PAD": "ground", "EPAD": "ground", "EP": "ground",
    "EN": "enable", "ENABLE": "enable", "CE": "enable", "SHDN": "enable",
    "FB": "feedback", "ADJ": "feedback",
    "NC": "no_connect", "N/C": "no_connect",
}

PIN_TABLE_HEADINGS = [
    r"pin\s+(?:configuration|description|function|assignment|definition)",
    r"terminal\s+(?:function|description|assignment)",
    r"pin\s*out", r"pinout",
    r"pin\s+(?:table|list|map|names?)",
]


def _classify_pin(name):
    if not name:
        return "indeterminate"
    clean = re.sub(r"[_\-\s\d]+$", "", name.strip().upper())
    if clean in PIN_FUNCTIONS:
        return PIN_FUNCTIONS[clean]
    for k, v in PIN_FUNCTIONS.items():
        if k in clean or clean in k:
            return v
    return "indeterminate"


class PinoutInfo:
    def __init__(self, mpn="", package=""):
        self.mpn = mpn
        self.package = package
        self.pins = {}
        self.total_pins = 0
        self.confidence = 0.0
        self.source = ""
        self.expected_pins = _max_pins_from_package(package)

    def add_pin(self, num, name, desc=""):
        self.pins[str(num)] = {"name": name, "function": _classify_pin(name), "description": desc}
        self.total_pins = len(self.pins)

    def is_valid(self):
        if self.total_pins < 2:
            return False
        if (
            self.expected_pins is not None
            and self.expected_pins < 100
            and self.total_pins != self.expected_pins
        ):
            return False
        pin_nums = set()
        for pn in self.pins:
            try:
                pin_nums.add(int(pn))
            except ValueError:
                pass
        if not pin_nums:
            return False
        return len(pin_nums) >= max(pin_nums) - 1

    def to_dict(self):
        return {"mpn": self.mpn, "package": self.package, "total_pins": self.total_pins,
                "expected_pins": self.expected_pins, "confidence": round(self.confidence, 2),
                "source": self.source, "valid": self.is_valid(), "pins": self.pins}

    def to_json(self):
        return json.dumps(self.to_dict(), indent=2)


def compare_pinouts(target, candidate):
    """Strict pin comparison. Indeterminate = incompatible, not assumed ok."""
    if target.total_pins < 2 or candidate.total_pins < 2:
        return 0.0, {"status": "invalid_pinout_data",
                      "target_valid": target.is_valid(), "candidate_valid": candidate.is_valid(),
                      "target_pins": target.total_pins, "target_expected": target.expected_pins,
                      "candidate_pins": candidate.total_pins, "candidate_expected": candidate.expected_pins}

    if target.total_pins != candidate.total_pins:
        return 0.0, {"status": "pin_count_mismatch",
                      "target_pins": target.total_pins, "candidate_pins": candidate.total_pins}

    matches = 0
    mismatches = []
    total = 0
    for pn, tp in target.pins.items():
        cp = candidate.pins.get(pn)
        total += 1
        if not cp:
            mismatches.append({"pin": pn, "target": tp["name"], "candidate": "MISSING", "severity": "critical"})
            continue
        tn, cn = tp["name"].strip().upper(), cp["name"].strip().upper()
        tf, cf = tp["function"], cp["function"]
        if tn == cn:
            matches += 1
        elif tf == "indeterminate" or cf == "indeterminate":
            mismatches.append({"pin": pn, "target": tp["name"], "candidate": cp["name"],
                               "severity": "indeterminate"})
        elif tf == "no_connect" or cf == "no_connect":
            matches += 0.5
        elif tf == cf:
            matches += 0.8
        else:
            sev = "critical" if tf in ("power_input", "ground", "power_output") else "warning"
            mismatches.append({"pin": pn, "target": tp["name"], "candidate": cp["name"],
                               "target_function": tf, "candidate_function": cf, "severity": sev})

    score = matches / total if total > 0 else 0
    return score, {"status": "compared", "total_pins": total, "matches": matches,
                   "mismatches": mismatches,
                   "critical_mismatches": sum(1 for m in mismatches if m.get("severity") == "critical")}


# ═══════════════════════════════════════════════════════
# MAIN PARSER
# ═══════════════════════════════════════════════════════

class DatasheetParser:
    def __init__(self, download_dir="downloads/datasheets"):
        self.download_dir = download_dir
        os.makedirs(download_dir, exist_ok=True)

    def download(self, url, mpn):
        if not url:
            return None
        try:
            from finder_extras.llm_parser import download_pdf
            path, file_type = download_pdf(url, mpn, download_dir=self.download_dir)
            return path if file_type == "pdf" else None
        except Exception as exc:
            log.debug("Download/validation failed %s: %s", mpn, exc)
            return None

    def _get_page_texts(self, pdf_path, max_pages=10):
        if not PYMUPDF_OK:
            return []
        try:
            doc = fitz.open(pdf_path)
            pages = [doc[i].get_text() for i in range(min(max_pages, len(doc)))]
            doc.close()
            return pages
        except Exception:
            return []

    def extract_specs(self, page_texts, category=""):
        """Unit-aware extraction; see finder_extras/spec_extractor.py."""
        from finder_extras.spec_extractor import extract_specs
        return extract_specs(page_texts, category)

    def _find_pin_pages(self, page_texts):
        pages = []
        for i, text in enumerate(page_texts):
            for heading in PIN_TABLE_HEADINGS:
                if re.search(heading, text, re.IGNORECASE):
                    pages.append(i)
                    break
        return pages

    def _extract_pin_rows(self, text, max_pins):
        rows = []
        seen = set()
        patterns = [
            r"(?:Pin\s*)?(\d+)\s+([A-Z][A-Z0-9/+\-_]{0,15})\s+([\w\s,\-./()]{3,60}?)(?:\n|$)",
            r"(\d+)\s*\|\s*([A-Z][A-Z0-9/+\-_]{0,15})\s*\|\s*([\w\s,\-./()]{3,60}?)(?:\n|$)",
        ]
        for pat in patterns:
            for num_s, name, desc in re.findall(pat, text, re.IGNORECASE):
                try:
                    num = int(num_s)
                except ValueError:
                    continue
                if max_pins is not None and num > max_pins:
                    continue
                if num < 1 or num > 300 or num in seen:
                    continue
                name = name.strip()
                if len(name) < 1 or name in ("FIGURE", "TABLE", "NOTE", "SECTION", "PAGE"):
                    continue
                seen.add(num)
                rows.append((num, name, desc.strip()))
            if len(rows) >= 3:
                break
        return rows

    def extract_pinout(self, page_texts, mpn="", package=""):
        expected = _max_pins_from_package(package)
        pinout = PinoutInfo(mpn=mpn, package=package)

        # Search pin-table pages first
        pin_pages = self._find_pin_pages(page_texts)
        if pin_pages:
            for idx in pin_pages:
                rows = self._extract_pin_rows(page_texts[idx], expected)
                if rows:
                    for num, name, desc in rows:
                        pinout.add_pin(num, name, desc)
                    pinout.source = "pin_table_heading"
                    break

        # Fallback: first 3 pages
        if pinout.total_pins < 3:
            pinout = PinoutInfo(mpn=mpn, package=package)
            for idx in range(min(3, len(page_texts))):
                rows = self._extract_pin_rows(page_texts[idx], expected)
                if len(rows) >= 3:
                    for num, name, desc in rows:
                        pinout.add_pin(num, name, desc)
                    pinout.source = "fallback_first_pages"
                    break

        # Set confidence
        if pinout.is_valid():
            pinout.confidence = 0.85 if pinout.source == "pin_table_heading" else 0.5
        elif pinout.total_pins >= 3:
            pinout.confidence = 0.2
        else:
            pinout.confidence = 0.0

        if pinout.total_pins >= 3:
            log.info("Extracted %d pins for %s (confidence=%.0f%%, valid=%s, expected=%s)",
                     pinout.total_pins, mpn, pinout.confidence * 100,
                     pinout.is_valid(), expected)
        return pinout

    def parse_datasheet(self, url, mpn, package="", category=""):
        pdf = self.download(url, mpn)
        if not pdf:
            return {}, PinoutInfo(mpn=mpn, package=package)
        pages = self._get_page_texts(pdf)
        if not pages:
            return {}, PinoutInfo(mpn=mpn, package=package)
        specs = self.extract_specs(pages, category=category)
        pinout = self.extract_pinout(pages, mpn=mpn, package=package)
        return specs, pinout

    def enrich_component(self, db, component_id):
        conn = db._get_conn()
        row = conn.execute(
            "SELECT manufacturer_part_number, datasheet_url, package, category FROM components WHERE id = ?",
            (component_id,)
        ).fetchone()
        if not row or not row[1]:
            return {}, PinoutInfo()

        mpn, url, pkg, cat = row[0], row[1], row[2] or "", row[3] or ""
        specs, pinout = self.parse_datasheet(url, mpn, pkg, cat)

        for name, val in specs.items():
            ex = conn.execute("SELECT 1 FROM specifications WHERE component_id=? AND spec_name=?",
                              (component_id, name)).fetchone()
            if not ex:
                conn.execute("INSERT INTO specifications (component_id, spec_name, spec_value) VALUES (?,?,?)",
                             (component_id, name, val))

            # Always persist extracted pinout
            if pinout.total_pins > 0:
                conn.execute(
                    "INSERT OR REPLACE INTO specifications (component_id, spec_name, spec_value) VALUES (?,?,?)",
                    (component_id, "_pinout_json", pinout.to_json())
                )

        conn.commit()
        log.info("Enriched %s: %d specs, %d pins (valid=%s)", mpn, len(specs), pinout.total_pins, pinout.is_valid())
        return specs, pinout
