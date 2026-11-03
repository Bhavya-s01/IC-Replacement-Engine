"""
spec_extractor.py - Table-driven, unit-aware regex extraction of datasheet specs.

Add or tune a spec by editing SPECS only; the engine does not change.

How a value is found
  1. Find a label (e.g. "Dropout Voltage") on a line.
  2. Look at a short window after it (rest of the line + a few following lines;
     PyMuPDF often splits table cells onto separate lines).
  3. Collect numbers carrying a unit of the spec's family (mV, uA, dB, ...).
     Bare numbers followed by a unit ("8  40  mV") inherit that unit.
  4. Drop test conditions ("IOUT = 300mA", "@ 1kHz"), convert to the display
     unit, discard values outside the plausible range, pick min/typ/max.
Output values always carry a unit ("160 mV"), which match_rules / llm_parser
validation depend on.
"""

import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence

_NUM = r"[-+]?\d+(?:,\d{3})*(?:\.\d+)?"
_PREFIX = {"": 1.0, "p": 1e-12, "n": 1e-9, "u": 1e-6, "µ": 1e-6, "μ": 1e-6,
           "m": 1e-3, "k": 1e3, "K": 1e3, "M": 1e6, "G": 1e9}


@dataclass(frozen=True)
class Unit:
    """A unit family: `base` regex alternatives, optional SI prefixes."""
    base: str                      # regex for the base unit, e.g. "V", "Hz"
    display: str                   # unit used in the output, e.g. "mV"
    prefixes: str = "pnuµμmkMG"
    prefix_required: bool = False  # "s" alone is too ambiguous; "ns"/"ms" are fine
    word_boundary: bool = True


# display -> (base-unit factor)
def _display_factor(display: str, base_len: int) -> float:
    prefix = display[:-base_len] if base_len and len(display) > base_len else ""
    return _PREFIX.get(prefix, 1.0)


@dataclass
class SpecDef:
    name: str                      # canonical match_rules spec name
    labels: Sequence[str]          # regexes for the row label / prose phrase
    unit: Unit
    lo: float                      # plausible range, in display unit
    hi: float
    pick: str = "typ"              # typ | max | min | first
    base_len: int = 1              # characters of the display unit that are the base


V = lambda disp="V": Unit("V", disp)
A = lambda disp: Unit("A", disp)
HZ = lambda disp: Unit("Hz", disp)
SEC = lambda disp: Unit("s", disp, prefixes="pnµμum", prefix_required=True)
DB = Unit("dB", "dB", prefixes="")
PCT = Unit("%", "%", prefixes="", word_boundary=False)
OHM = Unit(r"(?:Ω|Ω|ohms?)", "Ω", prefixes="mk")
CW = Unit(r"°?C\s*/\s*W", "°C/W", prefixes="")
YEARS = Unit(r"(?i:years?)", "years", prefixes="")
CYCLES = Unit(r"(?i:(?:(?:program|erase|write)(?:\s*/\s*(?:program|erase|write))?\s+)?cycles?)", "cycles", prefixes="kKM")
GBPS = Unit(r"(?:bps|b/s)", "Gbps", prefixes="kMG")
KV = Unit("V", "kV", prefixes="k")
W = lambda disp: Unit("W", disp)


# ------------------------------------------------------------------ spec registry
UNIVERSAL: List[SpecDef] = [
    SpecDef("Thermal Resistance JA",
            [r"(?:θ|theta|R)\s*[_]?\s*J\s*A\b", r"thermal\s+resistance[^\n]{0,40}junction[- ]to[- ]ambient"],
            CW, 1, 600, "first", base_len=3),
    SpecDef("ESD Rating HBM",
            [r"\bHBM\b", r"human[- ]body[- ]model"], KV, 0.1, 30, "first", base_len=1),
]

BY_CATEGORY: Dict[str, List[SpecDef]] = {
    "ldo_ic": [
        SpecDef("Voltage Dropout (Max)", [r"dropout\s+voltage", r"\bV\s*DO\b", r"\bV\s*DROP"], V("mV"), 1, 3000, "typ", base_len=1),
        SpecDef("Current - Quiescent (Iq)", [r"quiescent\s+current", r"ground\s+(?:pin\s+)?current", r"\bI\s*(?:Q|GND)\b"], A("µA"), 0.1, 20000, "typ"),
        SpecDef("PSRR", [r"\bPSRR\b", r"power\s+supply\s+rejection(?:\s+ratio)?", r"\bripple\s+rejection"], DB, 10, 140, "typ", base_len=2),
        SpecDef("Output Noise", [r"output\s+(?:voltage\s+)?noise", r"\be\s*N\b"], V("µV"), 0.1, 5000, "typ"),
        SpecDef("Load Regulation", [r"load\s+regulation"], V("mV"), 0.01, 500, "typ"),
        SpecDef("Load Regulation", [r"load\s+regulation"], Unit(r"%(?:\s*/\s*(?:mA|A))?", "%", prefixes="", word_boundary=False), 0.001, 10, "typ", base_len=1),
        SpecDef("Line Regulation", [r"line\s+regulation"], V("mV"), 0.01, 500, "typ"),
        SpecDef("Line Regulation", [r"line\s+regulation"], Unit(r"%(?:\s*/\s*V)?", "%/V", prefixes="", word_boundary=False), 0.001, 10, "typ", base_len=3),
        SpecDef("Current Limit", [r"(?:output\s+)?current[- ]limit", r"short[- ]circuit\s+(?:output\s+)?current"], A("mA"), 10, 20000, "typ"),
    ],
    "dcdc_converter": [
        SpecDef("Efficiency", [r"\befficiency"], PCT, 30, 100, "max", base_len=1),
        SpecDef("Switching Frequency", [r"switching\s+frequency", r"oscillator\s+frequency", r"\bf\s*SW\b"], HZ("kHz"), 10, 10000, "typ", base_len=2),
        SpecDef("Output Ripple", [r"output\s+(?:voltage\s+)?ripple"], V("mV"), 0.1, 1000, "typ"),
        SpecDef("Soft Start Time", [r"soft[- ]start(?:\s+time)?"], SEC("ms"), 0.01, 100, "typ", base_len=1),
        SpecDef("Voltage - Input (Min)", [r"input\s+(?:supply\s+)?voltage\s+range", r"\bV\s*IN\s+range"], V(), 0.5, 100, "first"),
    ],
    "gate_driver": [
        SpecDef("Current - Peak Output", [r"peak\s+(?:output\s+)?(?:source\s+|sink\s+)?current", r"\bI\s*O\s*[+-]?\b"], A("A"), 0.05, 50, "typ"),
        SpecDef("Rise / Fall Time", [r"rise\s+time", r"fall\s+time"], SEC("ns"), 1, 5000, "typ", base_len=1),
        SpecDef("Propagation Delay", [r"propagation\s+delay", r"\bt\s*(?:PLH|PHL|D)\b"], SEC("ns"), 1, 5000, "typ", base_len=1),
    ],
    "power_sequencer": [
        SpecDef("Voltage - Threshold", [r"(?:reset\s+|input\s+)?threshold\s+voltage", r"\bV\s*TH\b"], V(), 0.3, 30, "typ"),
    ],
    "battery_management": [
        SpecDef("Current - Charging", [r"charge\s+current", r"charging\s+current", r"fast[- ]charge"], A("mA"), 10, 20000, "max"),
    ],
    "audio_ic": [
        SpecDef("Output Power", [r"output\s+power", r"\bP\s*O\b"], W("W"), 0.01, 200, "max"),
        SpecDef("THD + Noise", [r"\bTHD\s*\+?\s*N?\b", r"total\s+harmonic\s+distortion"], PCT, 0.0001, 10, "typ"),
        SpecDef("S/N Ratio", [r"\bSNR\b", r"signal[- ]to[- ]noise", r"\bS/N\b"], DB, 30, 150, "typ", base_len=2),
        SpecDef("PSRR", [r"\bPSRR\b", r"power\s+supply\s+rejection"], DB, 10, 140, "typ", base_len=2),
        SpecDef("Power Down Current", [r"shutdown\s+(?:supply\s+)?current", r"power[- ]down\s+current", r"standby\s+current"], A("µA"), 0.001, 5000, "typ"),
        SpecDef("Sample Rate", [r"sampl(?:e|ing)\s+(?:rate|frequency)"], HZ("kHz"), 1, 1000, "max", base_len=2),
    ],
    "temp_sensor": [
        SpecDef("Accuracy", [r"\baccuracy", r"temperature\s+error"], Unit(r"°\s*C", "°C", prefixes=""), 0.05, 10, "typ", base_len=2),
    ],
    "ambient_light": [
        SpecDef("Power Down Current", [r"shutdown\s+current", r"standby\s+current", r"power[- ]down"], A("µA"), 0.001, 5000, "typ"),
    ],
    "protection_ic": [
        SpecDef("Response Time", [r"response\s+time", r"clamping\s+time"], SEC("ns"), 0.01, 5000, "typ", base_len=1),
        SpecDef("Capacitance", [r"(?:junction\s+|input\s+|line\s+)?capacitance", r"\bC\s*(?:IO|J|IN)\b"], Unit("F", "pF", prefixes="pnuµm"), 0.05, 5000, "typ"),
        SpecDef("Voltage - Clamping", [r"clamping\s+voltage", r"\bV\s*CL\b"], V(), 1, 200, "max"),
    ],
    "logic_mux": [
        SpecDef("On-State Resistance (Max)", [r"on[- ]resistance", r"\bR\s*ON\b", r"on[- ]state\s+resistance"], OHM, 0.01, 5000, "max", base_len=1),
        SpecDef("Propagation Delay", [r"propagation\s+delay", r"\bt\s*(?:PD|PLH|PHL)\b"], SEC("ns"), 0.1, 5000, "max", base_len=1),
        SpecDef("Bandwidth", [r"[-]?3\s*dB\s+bandwidth", r"\bbandwidth"], HZ("MHz"), 1, 20000, "typ", base_len=2),
        SpecDef("Crosstalk", [r"crosstalk"], DB, 20, 150, "typ", base_len=2),
    ],
    "clock_timing": [
        SpecDef("Jitter RMS", [r"(?:rms\s+)?(?:phase\s+)?jitter"], SEC("ps"), 0.01, 10000, "typ", base_len=1),
        SpecDef("Frequency", [r"output\s+frequency", r"frequency\s+range"], HZ("MHz"), 0.001, 5000, "max", base_len=2),
    ],
    "mcu_soc": [
        SpecDef("Speed", [r"(?:max(?:imum)?\s+)?(?:cpu|core|system)\s+(?:clock\s+)?frequency", r"up\s+to"], HZ("MHz"), 1, 1000, "max", base_len=2),
        SpecDef("Sleep Current", [r"(?:deep[- ])?sleep\s+(?:mode\s+)?current", r"standby\s+current", r"stop\s+mode"], A("µA"), 0.01, 5000, "typ"),
    ],
    "usb_ic": [
        SpecDef("Data Rate", [r"data\s+rate", r"\bup\s+to"], GBPS, 0.1, 100, "max", base_len=3),
    ],
    "retimer_ic": [
        SpecDef("Data Rate", [r"data\s+rate", r"\bup\s+to"], GBPS, 0.1, 100, "max", base_len=3),
    ],
    "video_interface": [
        SpecDef("Data Rate", [r"data\s+rate", r"\bup\s+to"], GBPS, 0.1, 100, "max", base_len=3),
    ],
    "opto_ic": [
        SpecDef("Voltage - Isolation", [r"isolation\s+voltage", r"withstand"], Unit(r"V\s*rms", "Vrms", prefixes="k"), 500, 20000, "first", base_len=4),
        SpecDef("Current Transfer Ratio (CTR)", [r"\bCTR\b", r"current\s+transfer\s+ratio"], PCT, 5, 5000, "first"),
    ],
}

_MEMORY = [
    SpecDef("Clock Frequency", [r"(?:clock|SCK?L?|max(?:imum)?)\s+(?:clock\s+)?frequency", r"\bf\s*(?:C|SCL|CLK|R)\b"], HZ("MHz"), 0.01, 1000, "max", base_len=2),
    SpecDef("Standby Current", [r"standby\s+(?:supply\s+)?current", r"power[- ]down\s+current"], A("µA"), 0.01, 5000, "typ"),
    SpecDef("Write Endurance", [r"endurance", r"erase/(?:program|write)\s+cycles"], CYCLES, 1e3, 1e16, "first", base_len=6),
    SpecDef("Data Retention", [r"data\s+retention", r"retention"], YEARS, 1, 200, "first", base_len=5),
    SpecDef("Write Cycle Time", [r"write\s+cycle\s+time", r"page[- ]?(?:write|program)\s+time", r"byte[- ]write\s+time"], SEC("ms"), 0.01, 1000, "max", base_len=1),
]
for _cat in ("flash_memory", "eeprom", "fram_mram_sram"):
    BY_CATEGORY[_cat] = _MEMORY

_MEM_SIZE = re.compile(r"\b(\d{1,4})\s*[- ]?\s*([KMG])\s*[- ]?\s*(?:bit|b)s?\b(?!\w)", re.I)
_BAD_BEFORE = re.compile(r"(?:=|@|\+|\bat|\bfor|\bto|\bC\d?=?)\s*$", re.I)


# ------------------------------------------------------------------ engine
def _unit_regex(u: Unit) -> re.Pattern:
    pre = f"[{re.escape(u.prefixes)}]" if u.prefixes else ""
    pre = f"(?P<p>{pre})" + ("" if u.prefix_required else "?") if pre else "(?P<p>)"
    tail = r"(?![A-Za-z])" if u.word_boundary else ""
    return re.compile(rf"\s*{pre}(?P<b>{u.base}){tail}")


def _tokens(window: str, ureg: re.Pattern):
    """Yield (value_in_base, has_unit_match, start, end) for each number in window."""
    out = []
    for m in re.finditer(_NUM, window):
        um = ureg.match(window, m.end())
        # A prefix-less unit must not swallow the next word (handled by lookahead).
        val = float(m.group(0).replace(",", ""))
        factor = _PREFIX.get(um.group("p") or "", 1.0) if um else None
        out.append([val, factor, m.start(), m.end(), um.end() if um else None])
    # bare numbers inherit the factor of the next united number if only whitespace between
    for i in range(len(out) - 2, -1, -1):
        if out[i][1] is None and out[i + 1][1] is not None:
            if not window[out[i][3]:out[i + 1][2]].strip():
                out[i][1] = out[i + 1][1]
    return out


def _candidates(window: str, sd: SpecDef, ureg: re.Pattern) -> List[float]:
    disp_factor = _display_factor(sd.unit.display, sd.base_len) if sd.unit.prefixes or sd.base_len else 1.0
    vals = []
    for val, factor, start, _end, _uend in _tokens(window, ureg):
        if factor is None:
            continue
        if _BAD_BEFORE.search(window[max(0, start - 6):start]):
            continue  # test condition, not a parameter value
        v = val * factor / disp_factor
        if sd.lo <= v <= sd.hi:
            vals.append(v)
    return vals


def _choose(vals: List[float], pick: str) -> Optional[float]:
    if not vals:
        return None
    vals = vals[:3]
    if pick == "max":
        return max(vals)
    if pick == "min":
        return min(vals)
    if pick == "typ" and len(vals) >= 3:
        return vals[1]
    return vals[0]


def _fmt(v: float, unit: str) -> str:
    return f"{v:,.0f} {unit}" if abs(v) >= 1e5 else f"{v:.4g} {unit}"


def _lines(page_texts: Sequence[str]) -> List[str]:
    lines = []
    for t in page_texts:
        lines.extend(l.strip() for l in t.splitlines() if l.strip())
    return lines


def _extract_one(lines: List[str], sd: SpecDef) -> Optional[str]:
    ureg = _unit_regex(sd.unit)
    label_res = [re.compile(l, re.I) for l in sd.labels]
    prose = []
    for i, line in enumerate(lines):
        for lr in label_res:
            m = lr.search(line)
            if not m:
                continue
            after = line[m.end():]
            window = " ".join([after] + lines[i + 1:i + 6])
            window = re.sub(r"\(\d{1,2}\)", " ", window)[:220]  # footnote markers
            at_start = m.start() <= 2
            vals = _candidates(window, sd, ureg)
            chosen = _choose(vals, sd.pick)
            if chosen is None:
                continue
            if at_start:
                return _fmt(chosen, sd.unit.display)  # table row beats prose
            prose.append(chosen)
            break
    return _fmt(prose[0], sd.unit.display) if prose else None


def _memory_size(lines: List[str]) -> Optional[str]:
    first = None
    for line in lines[:150]:
        m = _MEM_SIZE.search(line)
        if not m:
            continue
        hit = f"{m.group(1)}{m.group(2).upper()}bit"
        if re.search(r"serial|flash|memory|eeprom|sram|fram|mram", line, re.I):
            return hit
        first = first or hit
    return first


def extract_specs(page_texts: Sequence[str], category: str = "") -> Dict[str, str]:
    """Return {canonical spec name: "value unit"} found in the datasheet text."""
    lines = _lines(page_texts)
    out: Dict[str, str] = {}
    for sd in UNIVERSAL + BY_CATEGORY.get(category, []):
        if sd.name in out:
            continue
        val = _extract_one(lines, sd)
        if val:
            out[sd.name] = val
    if category in ("flash_memory", "eeprom", "fram_mram_sram"):
        size = _memory_size(lines)
        if size:
            out["Memory Size"] = size
    return out
