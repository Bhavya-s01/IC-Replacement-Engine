"""
spec_parser.py — Parses DigiKey spec strings into comparable numeric values.
Handles: "3.3V", "100mA", "-40°C ~ 125°C", "500kHz", "60dB", etc.
"""

import re
from typing import Optional, Tuple

MULTIPLIERS = {
    "p": 1e-12, "n": 1e-9, "u": 1e-6, "\u00b5": 1e-6, "\u03bc": 1e-6,
    "m": 1e-3, "": 1.0, "k": 1e3, "K": 1e3, "M": 1e6, "G": 1e9,
}


def _parse_single_value(text):
    text = text.strip()
    m = re.match(r"([+-]?\d+\.?\d*)\s*([pnu\u00b5\u03bcmkKMG]?)\s*([A-Za-z\u00b0\u2126%]*)", text)
    if not m:
        return None
    return float(m.group(1)) * MULTIPLIERS.get(m.group(2), 1.0)


def parse_value(spec_str):
    if not spec_str or spec_str.strip() in ("-", "", "N/A"):
        return None
    spec_str = spec_str.strip()
    for tag in ["(Typ)", "(Max)", "(Min)", "(typ)", "(max)", "(min)"]:
        spec_str = spec_str.replace(tag, "")
    spec_str = spec_str.strip()
    for sep in [" ~ ", " - ", "~", " to "]:
        if sep in spec_str:
            parts = spec_str.split(sep, 1)
            low = _parse_single_value(parts[0])
            high = _parse_single_value(parts[1])
            if low is not None and high is not None:
                return (low + high) / 2
            return high if high is not None else low
    return _parse_single_value(spec_str)


def parse_range(spec_str):
    if not spec_str or spec_str.strip() in ("-", "", "N/A"):
        return (None, None)
    spec_str = spec_str.strip()
    for tag in ["(Typ)", "(Max)", "(Min)"]:
        spec_str = spec_str.replace(tag, "")
    for sep in [" ~ ", " - ", "~", " to "]:
        if sep in spec_str:
            parts = spec_str.split(sep, 1)
            return (_parse_single_value(parts[0]), _parse_single_value(parts[1]))
    val = _parse_single_value(spec_str)
    return (val, val)


def parse_temperature_range(spec_str):
    if not spec_str or spec_str.strip() in ("-", "", "N/A"):
        return (None, None)
    spec_str = re.sub(r"\([^)]*\)", "", spec_str).strip()
    numbers = re.findall(r"[-+]?\d+\.?\d*", spec_str)
    if len(numbers) >= 2:
        return (float(numbers[0]), float(numbers[1]))
    elif len(numbers) == 1:
        return (float(numbers[0]), float(numbers[0]))
    return (None, None)


def values_compatible(target_val, candidate_val, tolerance_pct=10):
    if target_val is None or candidate_val is None:
        return True
    if target_val == 0:
        return abs(candidate_val) < 0.001
    return abs(candidate_val - target_val) / abs(target_val) * 100 <= tolerance_pct


def range_covers(target_range, candidate_range):
    t_min, t_max = target_range
    c_min, c_max = candidate_range
    if t_min is None or t_max is None or c_min is None or c_max is None:
        return True
    return c_min <= t_min + 0.001 and c_max >= t_max - 0.001


def candidate_meets_or_exceeds(target_val, candidate_val):
    if target_val is None or candidate_val is None:
        return True
    return candidate_val >= target_val * 0.95