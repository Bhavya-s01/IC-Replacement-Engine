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
from typing import Dict, List, Optional, Tuple

log = logging.getLogger(__name__)

try:
    import fitz
    PYMUPDF_OK = True
except ImportError:
    PYMUPDF_OK = False

try:
    import requests
    REQUESTS_OK = True
except ImportError:
    REQUESTS_OK = False


# ═══════════════════════════════════════════════════════
# PATTERNS TUNED TO REAL PDF TEXT [2]
#
# Key insight: PyMuPDF text from tables looks like:
#   "Dropout Voltage(11)  IOUT = 300mA    160    mV"
#   "PSRR\n(dB)\nFREQUENCY" (chart label)
#   "quiescent current: 38µA"
#   "Line Regulation  VIN = VOUT +1V to 5.5V  0.02  0.3  %/V"
#
# Patterns use looser matching with .*? bridges and
# multiple unit alternatives.
# ═══════════════════════════════════════════════════════

UNIVERSAL_PATTERNS = {
    "Thermal Resistance JA": [
        r"(?:theta|R|θ)\s*J\s*A\s*[\s:=]+(\d+\.?\d*)\s*(?:°?C/W|K/W)",
        r"(?:thermal\s+resistance).*?JA.*?(\d+\.?\d*)\s*(?:°?C/W|K/W)",
    ],
    "ESD Rating HBM": [
        r"(?:ESD|HBM).*?(\d+\.?\d*)\s*kV",
    ],
}

CATEGORY_PATTERNS = {
    "ldo_ic": {
        "PSRR": [
            # "PSRR ... 60 ... dB" (table row)
            r"PSRR.*?(\d+)\s*dB",
            # "60dB (1kHz)" or "60 dB"
            r"(\d+)\s*dB.*?(?:1\s*kHz|PSRR)",
            # "power supply rejection ratio ... 60"
            r"power\s+supply\s+rejection.*?(\d+)\s*dB",
            # In electrical characteristics table: "PSRR ... COUT = 1µF ... 60 ... dB"
            r"PSRR.*?(?:COUT|CIN|1µF|1uF).*?(\d+)\s+dB",
        ],
        "Dropout Voltage": [
            # "dropout voltage (160mV at 300mA)" - from description text
            r"dropout\s+voltage\s*\(?(\d+\.?\d*)\s*mV",
            # "low dropout voltage (160mV" 
            r"low\s+dropout.*?(\d+\.?\d*)\s*mV",
            # Table: "Dropout Voltage(11)  IOUT = 300mA  160  mV"
            r"[Dd]ropout\s+[Vv]oltage.*?(\d+)\s+mV",
            # "VDROPOUT ... 160 ... mV"
            r"V\s*DROPOUT.*?(\d+\.?\d*)\s*mV",
        ],
        "Quiescent Current": [
            # "quiescent current: 38µA"
            r"quiescent\s+current\s*[:=]\s*(\d+\.?\d*)\s*[µu]A",
            # "Low quiescent current: 38µA"
            r"[Ll]ow\s+quiescent.*?(\d+\.?\d*)\s*[µu]A",
            # "ground current (typically 38µA)"
            r"ground\s+current\s*\(?(?:typically\s+)?(\d+\.?\d*)\s*[µu]A",
            # Table: "Quiescent Current ... 38 ... µA" or "Iq ... 38 ... µA"
            r"(?:Quiescent|Iq|IQ|I\s*Q).*?(\d+\.?\d*)\s*[µu]A",
            # "supply current ... 38 ... µA"
            r"supply\s+current.*?(\d+\.?\d*)\s*[µu]A",
        ],
        "Output Noise": [
            r"[Oo]utput\s+[Vv]oltage\s+[Nn]oise.*?(\d+\.?\d*)\s*[µu]V",
            r"[Oo]utput\s+[Nn]oise.*?(\d+\.?\d*)\s*[µu]V",
            r"noise.*?(\d+\.?\d*)\s*[µu]Vrms",
        ],
        "Load Regulation": [
            # "Load Regulation(10)  IOUT = 100µA to 300mA  8  40  mV"
            r"[Ll]oad\s+[Rr]egulation.*?(\d+\.?\d*)\s+(\d+\.?\d*)\s+mV",
            r"[Ll]oad\s+[Rr]egulation.*?(\d+\.?\d*)\s*mV",
            r"[Ll]oad\s+[Rr]egulation.*?(\d+\.?\d*)\s*%",
        ],
        "Line Regulation": [
            # "Line Regulation  VIN = VOUT +1V to 5.5V  0.02  0.3  %/V"
            r"[Ll]ine\s+[Rr]egulation.*?(\d+\.?\d*)\s+(\d+\.?\d*)\s*%",
            r"[Ll]ine\s+[Rr]egulation.*?(\d+\.?\d*)\s*%",
            r"[Ll]ine\s+[Rr]egulation.*?(\d+\.?\d*)\s*mV",
        ],
        "Enable Threshold": [
            r"[Ee]nable.*?[Tt]hreshold.*?(\d+\.?\d*)\s*V",
            r"EN\s+[Hh]igh.*?(\d+\.?\d*)\s*V",
            r"[Ee]nable\s+[Vv]oltage.*?(\d+\.?\d*)\s*V",
        ],
        "Current Limit": [
            r"[Cc]urrent\s+[Ll]imit.*?(\d+)\s*mA",
            r"[Ss]hort\s+[Cc]ircuit.*?(\d+)\s*mA",
        ],
        "Soft Start Time": [
            r"[Ss]oft[- ]?[Ss]tart.*?(\d+\.?\d*)\s*(?:ms|µs|us)",
        ],
    },

    "dcdc_converter": {
        "Efficiency Peak": [
            r"[Ee]fficiency.*?(\d+\.?\d*)\s*%",
            r"(\d+\.?\d*)\s*%\s*[Ee]fficiency",
        ],
        "Output Ripple": [
            r"[Oo]utput\s+[Rr]ipple.*?(\d+\.?\d*)\s*mV",
            r"[Rr]ipple.*?(\d+\.?\d*)\s*mV\s*(?:p-p|pp|peak)",
        ],
        "Switching Frequency": [
            r"[Ss]witching\s+[Ff]requency.*?(\d+\.?\d*)\s*(?:kHz|MHz)",
            r"f\s*SW.*?(\d+\.?\d*)\s*(?:kHz|MHz)",
        ],
        "Enable Threshold": [
            r"[Ee]nable.*?[Tt]hreshold.*?(\d+\.?\d*)\s*V",
        ],
        "Soft Start Time": [
            r"[Ss]oft[- ]?[Ss]tart.*?(\d+\.?\d*)\s*(?:ms|µs)",
        ],
        "Duty Cycle Max": [
            r"[Dd]uty\s+[Cc]ycle.*?(\d+\.?\d*)\s*%",
        ],
    },

    "audio_ic": {
        "THD+N": [
            r"THD\+?N.*?(\d+\.?\d*)\s*%",
            r"[Dd]istortion.*?(\d+\.?\d*)\s*%",
        ],
        "SNR": [
            r"(?:SNR|S/N).*?(\d+\.?\d*)\s*dB",
            r"[Ss]ignal.to.[Nn]oise.*?(\d+\.?\d*)\s*dB",
        ],
        "PSRR": [
            r"PSRR.*?(\d+\.?\d*)\s*dB",
        ],
        "Power Down Current": [
            r"(?:[Pp]ower[- ]?[Dd]own|[Ss]hutdown|[Ss]tandby)\s+[Cc]urrent.*?(\d+\.?\d*)\s*(?:[µu]A|mA|nA)",
        ],
    },

    "usb_ic": {
        "ESD Rating": [
            r"ESD.*?(\d+\.?\d*)\s*kV",
        ],
        "VBUS Detection": [
            r"VBUS\s+(?:[Dd]etect|[Tt]hreshold).*?(\d+\.?\d*)\s*V",
        ],
    },

    "clock_timing": {
        "Jitter RMS": [
            r"[Jj]itter.*?(?:rms|RMS).*?(\d+\.?\d*)\s*(?:ps|ns)",
            r"(?:rms|RMS)\s+[Jj]itter.*?(\d+\.?\d*)\s*(?:ps|ns)",
        ],
        "Phase Noise": [
            r"[Pp]hase\s+[Nn]oise.*?[-]?(\d+\.?\d*)\s*dBc",
        ],
    },

    "retimer_ic": {
        "Output Jitter": [
            r"[Oo]utput\s+[Jj]itter.*?(\d+\.?\d*)\s*(?:ps|ns)",
        ],
        "Return Loss": [
            r"[Rr]eturn\s+[Ll]oss.*?[-]?(\d+\.?\d*)\s*dB",
        ],
    },

    "protection_ic": {
        "Response Time": [
            r"[Rr]esponse\s+[Tt]ime.*?(\d+\.?\d*)\s*(?:ns|ps)",
        ],
    },

    "flash_memory": {
        "Page Program Time": [
            r"[Pp]age\s+[Pp]rogram.*?(\d+\.?\d*)\s*(?:ms|[µu]s)",
        ],
        "Standby Current": [
            r"[Ss]tandby\s+[Cc]urrent.*?(\d+\.?\d*)\s*(?:[µu]A|mA)",
        ],
    },

    "mcu_soc": {
        "Sleep Current": [
            r"(?:[Ss]leep|[Ss]top|[Ss]tandby)\s+(?:[Mm]ode\s+)?[Cc]urrent.*?(\d+\.?\d*)\s*(?:[µu]A|nA|mA)",
        ],
        "Wake Up Time": [
            r"[Ww]ake[- ]?[Uu]p\s+[Tt]ime.*?(\d+\.?\d*)\s*(?:[µu]s|ms)",
        ],
    },
}

# Copy patterns to related categories
for base, extras in [
    ("ldo_ic", ["power_sequencer", "battery_management"]),
    ("flash_memory", ["eeprom", "fram_mram_sram"]),
    ("clock_timing", ["logic_mux"]),
]:
    if base in CATEGORY_PATTERNS:
        for extra in extras:
            if extra not in CATEGORY_PATTERNS:
                CATEGORY_PATTERNS[extra] = CATEGORY_PATTERNS[base].copy()


# ═══════════════════════════════════════════════════════
# PIN HANDLING
# ═══════════════════════════════════════════════════════

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
        if not url or not REQUESTS_OK:
            return None
        safe = re.sub(r"[^\w\-.]", "_", mpn) + ".pdf"
        path = os.path.join(self.download_dir, safe)
        if os.path.exists(path):
            return path
        try:
            resp = requests.get(url, timeout=30, verify=False,
                                headers={"User-Agent": "Mozilla/5.0"})
            if resp.status_code == 200 and ("pdf" in resp.headers.get("content-type", "") or url.endswith(".pdf")):
                with open(path, "wb") as f:
                    f.write(resp.content)
                log.info("Downloaded %s (%d KB)", mpn, len(resp.content) // 1024)
                return path
        except Exception as exc:
            log.debug("Download failed %s: %s", mpn, exc)
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
        """Extract specs using multi-pattern matching per spec name."""
        text = "\n".join(page_texts)
        specs = {}

        # Universal patterns
        for name, patterns in UNIVERSAL_PATTERNS.items():
            for pat in patterns:
                m = re.search(pat, text, re.IGNORECASE | re.DOTALL)
                if m:
                    specs[name] = m.group(1).strip()
                    break

        # Category-specific patterns
        cat_pats = CATEGORY_PATTERNS.get(category, {})
        for name, patterns in cat_pats.items():
            if name in specs:
                continue
            for pat in patterns:
                m = re.search(pat, text, re.IGNORECASE | re.DOTALL)
                if m:
                    val = m.group(1).strip()
                    # If pattern captured two groups (min/max), take max
                    if m.lastindex and m.lastindex >= 2:
                        val = m.group(2).strip()
                    specs[name] = val
                    break

        return specs

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

    def batch_enrich(self, db, category=None, limit=50):
        conn = db._get_conn()
        q = "SELECT id FROM components WHERE datasheet_url != '' AND datasheet_url IS NOT NULL"
        params = []
        if category:
            q += " AND category = ?"
            params.append(category)
        q += " LIMIT ?"
        params.append(limit)
        parts = conn.execute(q, params).fetchall()
        enriched = 0
        for part in parts:
            specs, pinout = self.enrich_component(db, part[0])
            if specs or pinout.total_pins > 0:
                enriched += 1
        log.info("Enriched %d / %d", enriched, len(parts))
        return enriched