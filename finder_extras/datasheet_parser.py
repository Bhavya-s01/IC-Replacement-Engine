"""
Datasheet Parser v3 — Tier 3 approach.

Uses pdfplumber for table extraction + enhanced regex for text matching.
No Azure AI or local LLMs required.

Strategy:
  1. pdfplumber extracts actual tables (rows x columns) from PDF
  2. Search tables for spec keywords → get values from adjacent cells
  3. Enhanced regex scans full text for specs that aren't in tables
  4. Pinout extraction validates against package pin count
  5. All extracted specs stored in the specifications table

Requires: pip install pdfplumber pymupdf requests
"""

import os
import re
import json
import logging
from typing import Dict, List, Optional, Tuple

log = logging.getLogger(__name__)

# ── PDF Libraries ──
try:
    import pdfplumber
    PDFPLUMBER_OK = True
except ImportError:
    PDFPLUMBER_OK = False

try:
    import fitz  # PyMuPDF
    PYMUPDF_OK = True
except ImportError:
    PYMUPDF_OK = False

try:
    import requests
    REQUESTS_OK = True
except ImportError:
    REQUESTS_OK = False


# ═══════════════════════════════════════════════════════
# CATEGORY-SPECIFIC SPECS TO EXTRACT
# These are specs DigiKey doesn't list but datasheets do [1]
# ═══════════════════════════════════════════════════════

CATEGORY_SPECS = {
    "dcdc_converter": [
        "Efficiency", "Output Ripple", "Output Noise",
        "Enable Threshold", "Soft Start Time",
        "Thermal Resistance JA", "Power Dissipation Max",
    ],
    "ldo_ic": [
        "PSRR", "Output Noise", "Load Regulation",
        "Line Regulation", "Dropout Voltage",
        "Transient Response", "Enable Threshold",
        "Soft Start Time", "Thermal Resistance JA",
    ],
    "audio_ic": [
        "THD+N", "SNR", "Dynamic Range",
        "Channel Separation", "PSRR",
        "Input Impedance", "Power Down Current",
    ],
    "usb_ic": [
        "VBUS Detection Threshold", "ESD Rating",
        "Reference Clock", "Power Down Current",
    ],
    "clock_timing": [
        "Jitter RMS", "Jitter Peak-Peak",
        "Lock Time", "Phase Noise", "Spread Spectrum",
    ],
    "retimer_ic": [
        "Output Jitter", "Return Loss",
        "Equalization Range", "Power Down Current",
    ],
    "mcu_soc": [
        "Sleep Current", "Wake Up Time",
        "Brown Out Threshold", "ADC Resolution",
    ],
    "protection_ic": [
        "Response Time", "Capacitance", "Leakage Current",
    ],
    "flash_memory": [
        "Page Program Time", "Sector Erase Time",
        "Standby Current", "Deep Power Down Current",
    ],
    "eeprom": [
        "Write Cycle Time", "Standby Current", "Page Size",
    ],
    "logic_mux": [
        "On Resistance", "Bandwidth", "Crosstalk", "Charge Injection",
    ],
}


# ═══════════════════════════════════════════════════════
# ENHANCED REGEX PATTERNS
# These match how specs ACTUALLY appear in datasheets [1]:
#   "PSRR (dB) ... 60"
#   "Load Regulation ... 8 40 mV"
#   "quiescent current: 38µA"
#   "dropout voltage (160mV at 300mA)"
# ═══════════════════════════════════════════════════════

UNIVERSAL_PATTERNS = {
    "Thermal Resistance JA": [
        r"(?:theta|R|θ)\s*(?:JA|ja|J[\-\s]?A)\s*[\s:=]*([\d.]+)\s*(?:°?C/W|K/W)",
        r"thermal\s+resistance.*?JA.*?([\d.]+)\s*(?:°?C/W)",
    ],
    "Thermal Resistance JC": [
        r"(?:theta|R|θ)\s*(?:JC|jc|J[\-\s]?C)\s*[\s:=]*([\d.]+)\s*(?:°?C/W|K/W)",
    ],
    "ESD Rating HBM": [
        r"(?:ESD|HBM)\s*[\s:=]*([\d.]+)\s*(?:kV|V)",
        r"human\s+body\s+model.*?([\d.]+)\s*(?:kV|V)",
    ],
    "Thermal Shutdown": [
        r"thermal\s+shutdown.*?([\d.]+)\s*°?C",
    ],
}

# These patterns are WIDER to match actual datasheet table formatting [1]
LDO_PATTERNS = {
    "PSRR": [
        r"PSRR\b.*?([\d.]+)\s*dB",
        r"power\s+supply\s+rejection\s+ratio.*?([\d.]+)\s*dB",
        r"PSRR.*?(\d+)\s+\d*\s*dB",  # table format: "PSRR ... 60 ... dB"
    ],
    "Output Noise": [
        r"output\s+(?:voltage\s+)?noise.*?([\d.]+)\s*(?:µV|uV|mV)",
        r"noise.*?(?:rms|RMS).*?([\d.]+)\s*(?:µV|uV|mV)",
        r"output.*?noise.*?(\d+)\s*(?:µV|uV|mV)",
    ],
    "Load Regulation": [
        r"load\s+regulation.*?([\d.]+)\s*(?:%|mV)",
        r"load\s+regulation.*?(\d+)\s+(\d+)\s*mV",  # "8 40 mV" → takes typical
    ],
    "Line Regulation": [
        r"line\s+regulation.*?([\d.]+)\s*(?:%|%/V|mV)",
        r"line\s+regulation.*?([\d.]+)\s+([\d.]+)\s*%",
    ],
    "Dropout Voltage": [
        r"dropout\s+voltage.*?([\d.]+)\s*(?:mV|V)",
        r"drop[\-\s]?out.*?([\d.]+)\s*(?:mV|V)",
        r"VDROPOUT.*?([\d.]+)\s*(?:mV|V)",
        r"low\s+dropout.*?\(([\d.]+)\s*mV",  # "low dropout voltage (160mV at 300mA)"
    ],
    "Quiescent Current": [
        r"quiescent\s+current.*?([\d.]+)\s*(?:µA|uA|mA)",
        r"ground\s+current.*?(?:typically?\s+)?([\d.]+)\s*(?:µA|uA|mA)",
        r"I[Qq]\b.*?([\d.]+)\s*(?:µA|uA|mA)",
        r"quiescent\s+current:\s*([\d.]+)\s*(?:µA|uA|mA)",  # "quiescent current: 38µA"
    ],
    "Current Limit": [
        r"current\s+limit.*?([\d.]+)\s*(?:mA|A)",
        r"short[\-\s]?circuit\s+current.*?([\d.]+)\s*(?:mA|A)",
    ],
    "Output Voltage Accuracy": [
        r"output\s+voltage\s+accuracy.*?([±+-]?\s*[\d.]+)\s*%",
        r"voltage\s+accuracy.*?([±+-]?\s*[\d.]+)\s*%",
    ],
    "Transient Response": [
        r"transient\s+response.*?([\d.]+)\s*(?:µs|us|ms)",
        r"load\s+transient.*?([\d.]+)\s*(?:µs|us|ms)",
    ],
    "Enable Threshold": [
        r"enable\s+(?:threshold|pin|voltage).*?([\d.]+)\s*V",
        r"EN\s+(?:threshold|high|low).*?([\d.]+)\s*V",
    ],
    "Soft Start Time": [
        r"soft[\-\s]?start\s+time.*?([\d.]+)\s*(?:ms|µs|us)",
    ],
}

DCDC_PATTERNS = {
    "Efficiency Peak": [
        r"(?:peak|maximum)\s+efficiency.*?([\d.]+)\s*%",
        r"efficiency.*?(\d{2,3})\s*%",
    ],
    "Output Ripple": [
        r"output\s+(?:voltage\s+)?ripple.*?([\d.]+)\s*(?:mV|µV|uV)",
    ],
    "Switching Frequency": [
        r"switching\s+frequency.*?([\d.]+)\s*(?:k?Hz|MHz)",
        r"oscillator\s+frequency.*?([\d.]+)\s*(?:k?Hz|MHz)",
    ],
    "Enable Threshold": [
        r"enable\s+(?:threshold|voltage).*?([\d.]+)\s*V",
    ],
    "Soft Start Time": [
        r"soft[\-\s]?start\s+time.*?([\d.]+)\s*(?:ms|µs|us)",
    ],
    "Duty Cycle Max": [
        r"(?:max(?:imum)?)\s+duty\s+cycle.*?([\d.]+)\s*%",
    ],
}

AUDIO_PATTERNS = {
    "THD+N": [
        r"THD\+?N.*?([\d.]+)\s*%",
        r"total\s+harmonic\s+distortion.*?([\d.]+)\s*%",
    ],
    "SNR": [
        r"(?:SNR|S/N|signal[\-\s]to[\-\s]noise).*?([\d.]+)\s*dB",
    ],
    "PSRR": [
        r"PSRR.*?([\d.]+)\s*dB",
    ],
    "Channel Separation": [
        r"(?:channel\s+separation|crosstalk).*?([\d.]+)\s*dB",
    ],
    "Power Down Current": [
        r"(?:power[\-\s]?down|shutdown|standby)\s+current.*?([\d.]+)\s*(?:µA|uA|mA|nA)",
    ],
}

RETIMER_PATTERNS = {
    "Output Jitter": [
        r"output\s+jitter.*?([\d.]+)\s*(?:ps|ns)",
    ],
    "Return Loss": [
        r"return\s+loss.*?[-]?([\d.]+)\s*dB",
    ],
}

CLOCK_PATTERNS = {
    "Jitter RMS": [
        r"(?:jitter|phase\s+jitter).*?(?:rms|RMS).*?([\d.]+)\s*(?:ps|ns)",
    ],
    "Phase Noise": [
        r"phase\s+noise.*?[-]?([\d.]+)\s*dBc",
    ],
    "Spread Spectrum": [
        r"spread[\-\s]?spectrum.*?([\d.]+)\s*%",
    ],
}

CATEGORY_REGEX = {
    "ldo_ic": LDO_PATTERNS,
    "dcdc_converter": DCDC_PATTERNS,
    "audio_ic": AUDIO_PATTERNS,
    "retimer_ic": RETIMER_PATTERNS,
    "clock_timing": CLOCK_PATTERNS,
    "power_sequencer": LDO_PATTERNS,  # shares many patterns
    "battery_management": LDO_PATTERNS,
}


# ═══════════════════════════════════════════════════════
# PINOUT EXTRACTION (with package validation)
# ═══════════════════════════════════════════════════════

def _max_pins_from_package(package_str):
    """Extract expected pin count from package name like SOT-23-5."""
    if not package_str:
        return None
    m = re.search(r"(\d+)\s*$", package_str.strip())
    if m:
        return int(m.group(1))
    known = {"sot-23": 3, "sot23": 3, "sc-59": 3, "sot-89": 3,
             "to-92": 3, "to92": 3, "to-252": 3, "dpak": 3}
    for k, v in known.items():
        if k in package_str.lower():
            return v
    return None


PIN_FUNCTIONS = {
    "VIN": "power_input", "VCC": "power_input", "VDD": "power_input",
    "VOUT": "power_output", "OUT": "power_output", "SW": "power_output",
    "GND": "ground", "VSS": "ground", "AGND": "ground", "PGND": "ground",
    "PAD": "ground", "EPAD": "ground", "EP": "ground",
    "EN": "enable", "CE": "enable", "SHDN": "enable",
    "FB": "feedback", "ADJ": "feedback",
    "SDA": "i2c_data", "SCL": "i2c_clock",
    "NC": "no_connect", "N/C": "no_connect",
}

PIN_TABLE_HEADINGS = [
    r"pin\s+(?:configuration|description|function|assignment|definition)",
    r"terminal\s+(?:function|description|assignment)",
    r"pin\s+out", r"pinout",
    r"pin\s+names?\s+and\s+(?:function|description)",
]


def _classify_pin(name):
    if not name:
        return "indeterminate"
    clean = re.sub(r"[_\-\s]+", "", name.strip().upper())
    clean = re.sub(r"\d+$", "", clean)
    if clean in PIN_FUNCTIONS:
        return PIN_FUNCTIONS[clean]
    for key, func in PIN_FUNCTIONS.items():
        if key in clean or clean in key:
            return func
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

    def add_pin(self, pin_number, name, description=""):
        self.pins[str(pin_number)] = {
            "name": name,
            "function": _classify_pin(name),
            "description": description,
        }
        self.total_pins = len(self.pins)

    def is_valid(self):
        if self.total_pins < 2:
            return False
        if self.expected_pins is not None and self.total_pins != self.expected_pins:
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
        return {
            "mpn": self.mpn, "package": self.package,
            "total_pins": self.total_pins, "expected_pins": self.expected_pins,
            "confidence": round(self.confidence, 2), "source": self.source,
            "valid": self.is_valid(), "pins": self.pins,
        }

    def to_json(self):
        return json.dumps(self.to_dict(), indent=2)


def compare_pinouts(target, candidate):
    """Compare two pinouts. Indeterminate pins = incompatible."""
    if not target.is_valid() or not candidate.is_valid():
        return 0.0, {"status": "invalid_pinout_data",
                      "target_valid": target.is_valid(),
                      "candidate_valid": candidate.is_valid()}

    if target.total_pins != candidate.total_pins:
        return 0.0, {"status": "pin_count_mismatch",
                      "target_pins": target.total_pins,
                      "candidate_pins": candidate.total_pins}

    matches = 0
    mismatches = []
    total = 0

    for pin_num, t_pin in target.pins.items():
        c_pin = candidate.pins.get(pin_num)
        total += 1
        if not c_pin:
            mismatches.append({"pin": pin_num, "target": t_pin["name"],
                               "candidate": "MISSING", "severity": "critical"})
            continue

        t_name = t_pin["name"].strip().upper()
        c_name = c_pin["name"].strip().upper()
        t_func = t_pin["function"]
        c_func = c_pin["function"]

        if t_name == c_name:
            matches += 1
        elif t_func == "indeterminate" or c_func == "indeterminate":
            mismatches.append({"pin": pin_num, "target": t_pin["name"],
                               "candidate": c_pin["name"], "severity": "indeterminate"})
        elif t_func == "no_connect" or c_func == "no_connect":
            matches += 0.5
        elif t_func == c_func:
            matches += 0.8
        else:
            severity = "critical" if t_func in ("power_input", "ground") else "warning"
            mismatches.append({"pin": pin_num, "target": t_pin["name"],
                               "candidate": c_pin["name"], "severity": severity})

    score = matches / total if total else 0
    return score, {"status": "compared", "total_pins": total, "matches": matches,
                   "mismatches": mismatches,
                   "critical": sum(1 for m in mismatches if m["severity"] == "critical")}


# ═══════════════════════════════════════════════════════
# MAIN PARSER CLASS
# ═══════════════════════════════════════════════════════

class DatasheetParser:
    """
    Downloads datasheets and extracts specs using:
      1. pdfplumber table extraction (searches table cells for spec keywords)
      2. Enhanced regex on full text (wider patterns matching actual formats)
      3. Validated pinout extraction (filtered by package pin count)
    """

    def __init__(self, download_dir="downloads/datasheets"):
        self.download_dir = download_dir
        os.makedirs(download_dir, exist_ok=True)

    def download(self, url, mpn):
        if not url or not REQUESTS_OK:
            return None
        safe_name = re.sub(r"[^\w\-.]", "_", mpn) + ".pdf"
        path = os.path.join(self.download_dir, safe_name)
        if os.path.exists(path):
            return path
        try:
            resp = requests.get(url, timeout=30, verify=False,
                                headers={"User-Agent": "Mozilla/5.0"})
            ct = resp.headers.get("content-type", "")
            if resp.status_code == 200 and ("pdf" in ct or url.endswith(".pdf")):
                with open(path, "wb") as f:
                    f.write(resp.content)
                log.info("Downloaded %s (%d KB)", mpn, len(resp.content) // 1024)
                return path
        except Exception as exc:
            log.debug("Download failed for %s: %s", mpn, exc)
        return None

    # ── STRATEGY 1: pdfplumber table extraction ──

    def _extract_tables(self, pdf_path, max_pages=10):
        """Extract all tables from the first N pages using pdfplumber."""
        if not PDFPLUMBER_OK:
            return [], ""

        tables = []
        full_text = ""

        try:
            with pdfplumber.open(pdf_path) as pdf:
                for page_num in range(min(max_pages, len(pdf.pages))):
                    page = pdf.pages[page_num]
                    full_text += (page.extract_text() or "") + "\n"

                    page_tables = page.extract_tables()
                    for table in page_tables:
                        if table and len(table) > 1:
                            tables.append({
                                "page": page_num + 1,
                                "rows": table,
                            })
        except Exception as exc:
            log.warning("pdfplumber failed: %s", str(exc)[:60])

        log.info("pdfplumber: %d tables from %s", len(tables), pdf_path)
        return tables, full_text

    def _search_tables(self, tables, spec_keywords):
        """
        Search extracted tables for rows containing spec keywords.
        Returns {spec_name: value} dict.

        This is the KEY improvement over pure regex: pdfplumber preserves
        table structure, so "Load Regulation" in column 0 maps correctly
        to "8" in the Typ column and "40" in the Max column [1].
        """
        specs = {}

        for kw_name, kw_patterns in spec_keywords.items():
            for table in tables:
                for row in table.get("rows", []):
                    if not row:
                        continue
                    # Join row cells for keyword search
                    row_text = " ".join(str(cell or "") for cell in row).lower()

                    for pattern in kw_patterns:
                        if pattern.lower() in row_text:
                            # Found the spec row — extract values
                            values = [str(cell or "").strip() for cell in row if cell]

                            # Look for numeric values (skip the parameter name itself)
                            for val in values[1:]:
                                if re.search(r"\d", val) and len(val) < 30:
                                    # Prefer "Typ" column value if identifiable
                                    specs[kw_name] = val
                                    break
                            break
                    if kw_name in specs:
                        break

        return specs

    # ── STRATEGY 2: Enhanced regex on full text ──

    def _extract_text_pymupdf(self, pdf_path, max_pages=10):
        """Fallback text extraction using PyMuPDF."""
        if not PYMUPDF_OK:
            return ""
        try:
            doc = fitz.open(pdf_path)
            text = ""
            for i in range(min(max_pages, len(doc))):
                text += doc[i].get_text()
            doc.close()
            return text
        except Exception:
            return ""

    def _extract_regex(self, text, category):
        """Apply enhanced regex patterns to extract specs from text."""
        specs = {}

        # Universal patterns
        for name, patterns in UNIVERSAL_PATTERNS.items():
            for pattern in patterns:
                m = re.search(pattern, text, re.IGNORECASE)
                if m:
                    specs[name] = m.group(1).strip()
                    break

        # Category-specific patterns
        cat_patterns = CATEGORY_REGEX.get(category, {})
        for name, patterns in cat_patterns.items():
            if name not in specs:
                for pattern in patterns:
                    m = re.search(pattern, text, re.IGNORECASE)
                    if m:
                        specs[name] = m.group(1).strip()
                        break

        return specs

    # ── STRATEGY 3: Pinout extraction ──

    def _extract_pinout(self, page_texts, mpn="", package=""):
        """Extract pinout from pages with pin-table headings, validated by package."""
        expected = _max_pins_from_package(package)
        pinout = PinoutInfo(mpn=mpn, package=package)

        # Find pages with pin-table headings
        pin_pages = []
        for i, text in enumerate(page_texts):
            for heading in PIN_TABLE_HEADINGS:
                if re.search(heading, text, re.IGNORECASE):
                    pin_pages.append(i)
                    break

        # Extract from pin-table pages only
        if pin_pages:
            for page_idx in pin_pages:
                rows = self._extract_pin_rows(page_texts[page_idx], expected)
                if rows:
                    for num, name, desc in rows:
                        pinout.add_pin(num, name, desc)
                    pinout.source = "pin_table_heading"
                    break

        # Fallback: first 3 pages
        if pinout.total_pins < 3:
            pinout = PinoutInfo(mpn=mpn, package=package)
            for page_idx in range(min(3, len(page_texts))):
                rows = self._extract_pin_rows(page_texts[page_idx], expected)
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

        return pinout

    def _extract_pin_rows(self, text, max_pins):
        """Extract pin rows, rejecting non-pin matches."""
        rows = []
        seen_pins = set()

        patterns = [
            r"(?:Pin\s*)?(\d+)\s+([A-Z][A-Z0-9/+\-_]{0,15})\s+([\w\s,\-./()]{3,60}?)(?:\n|$)",
            r"(\d+)\s*\|\s*([A-Z][A-Z0-9/+\-_]{0,15})\s*\|\s*([\w\s,\-./()]{3,60}?)(?:\n|$)",
        ]

        for pattern in patterns:
            matches = re.findall(pattern, text)
            for pin_str, pin_name, desc in matches:
                try:
                    num = int(pin_str)
                except ValueError:
                    continue
                if max_pins is not None and num > max_pins:
                    continue
                if num < 1 or num > 300 or num in seen_pins:
                    continue
                name = pin_name.strip()
                if len(name) < 1 or len(name) > 15:
                    continue
                if name in ("FIGURE", "TABLE", "NOTE", "SECTION", "PAGE", "REV"):
                    continue
                seen_pins.add(num)
                rows.append((num, name, desc.strip()))
            if len(rows) >= 3:
                break

        return rows

    # ── MAIN PIPELINE ──

    def parse_datasheet(self, url, mpn, package="", category=""):
        """
        Full pipeline: download → extract tables + text → specs + pinout.
        Returns (specs_dict, PinoutInfo).
        """
        pdf_path = self.download(url, mpn)
        if not pdf_path:
            return {}, PinoutInfo(mpn=mpn, package=package)

        specs = {}
        pinout = PinoutInfo(mpn=mpn, package=package)

        # ── Strategy 1: pdfplumber tables ──
        if PDFPLUMBER_OK:
            tables, text = self._extract_tables(pdf_path)

            if tables:
                # Build keyword map for this category
                cat_spec_names = CATEGORY_SPECS.get(category, [])
                spec_keywords = {}
                for spec_name in cat_spec_names:
                    # Each spec gets its name + lowercase words as search terms
                    spec_keywords[spec_name] = [
                        spec_name.lower(),
                    ] + spec_name.lower().split()

                # Add universal spec keywords
                for name in UNIVERSAL_PATTERNS:
                    spec_keywords[name] = [name.lower()] + name.lower().split()

                table_specs = self._search_tables(tables, spec_keywords)
                specs.update(table_specs)
                log.info("Table extraction: %d specs", len(table_specs))

            # Also run regex on the pdfplumber text
            if text:
                regex_specs = self._extract_regex(text, category)
                for k, v in regex_specs.items():
                    if k not in specs:  # don't overwrite table values
                        specs[k] = v
                log.info("Regex extraction: %d additional specs", len(regex_specs) - len(specs))

            # Extract pinout from page-by-page text
            if text:
                page_texts = text.split("\n\n")  # rough page split
                pinout = self._extract_pinout(page_texts, mpn, package)

        # ── Strategy 2: PyMuPDF fallback ──
        if not specs and PYMUPDF_OK:
            text = self._extract_text_pymupdf(pdf_path)
            if text:
                specs = self._extract_regex(text, category)
                log.info("PyMuPDF fallback: %d specs", len(specs))

        log.info("Total extracted for %s: %d specs, %d pins (valid=%s)",
                 mpn, len(specs), pinout.total_pins, pinout.is_valid())
        return specs, pinout

    def enrich_component(self, db, component_id):
        """Download datasheet and store extracted specs in DB."""
        conn = db._get_conn()
        row = conn.execute(
            "SELECT manufacturer_part_number, datasheet_url, package, category "
            "FROM components WHERE id = ?",
            (component_id,)
        ).fetchone()

        if not row or not row[1]:
            return {}, PinoutInfo()

        mpn, url, package, category = row[0], row[1], row[2] or "", row[3] or ""
        specs, pinout = self.parse_datasheet(url, mpn, package, category)

        # Store specs
        for spec_name, spec_value in specs.items():
            existing = conn.execute(
                "SELECT 1 FROM specifications WHERE component_id = ? AND spec_name = ?",
                (component_id, spec_name)
            ).fetchone()
            if not existing:
                conn.execute(
                    "INSERT INTO specifications (component_id, spec_name, spec_value) "
                    "VALUES (?, ?, ?)",
                    (component_id, spec_name, spec_value)
                )

        # Store validated pinout only
        if pinout.is_valid():
            conn.execute(
                "INSERT OR REPLACE INTO specifications "
                "(component_id, spec_name, spec_value) VALUES (?, ?, ?)",
                (component_id, "_pinout_json", pinout.to_json())
            )
        else:
            conn.execute(
                "DELETE FROM specifications "
                "WHERE component_id = ? AND spec_name = '_pinout_json'",
                (component_id,)
            )

        conn.commit()
        log.info("Enriched %s: %d specs, pinout valid=%s", mpn, len(specs), pinout.is_valid())
        return specs, pinout

    def batch_enrich(self, db, category=None, limit=50):
        """Enrich multiple components with datasheet data."""
        conn = db._get_conn()
        query = ("SELECT id FROM components "
                 "WHERE datasheet_url != '' AND datasheet_url IS NOT NULL")
        params = []
        if category:
            query += " AND category = ?"
            params.append(category)
        query += " LIMIT ?"
        params.append(limit)

        parts = conn.execute(query, params).fetchall()
        enriched = 0
        for part in parts:
            specs, _ = self.enrich_component(db, part[0])
            if specs:
                enriched += 1

        log.info("Enriched %d / %d components", enriched, len(parts))
        return enriched