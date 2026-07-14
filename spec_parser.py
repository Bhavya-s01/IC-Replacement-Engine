"""
spec_parser.py — Parses DigiKey spec strings into comparable numeric values.

Handles formats like:
  "3.3V", "100mA", "2.5A", "-40°C ~ 125°C", "1.8V ~ 3.6V",
  "500kHz", "1MHz", "10µA", "200mOhm", "60dB", etc.
"""

import re
from typing import Optional, Tuple

# SI prefix multipliers
MULTIPLIERS = {
    "p": 1e-12, "n": 1e-9, "u": 1e-6, "\u00b5": 1e-6, "\u03bc": 1e-6,
    "m": 1e-3, "": 1.0, "k": 1e3, "K": 1e3, "M": 1e6, "G": 1e9,
}


def _parse_single_value(text):
    """Extract a single numeric value with optional SI prefix."""
    text = text.strip()
    m = re.match(r"([+-]?\d+\.?\d*)\s*([pnu\u00b5\u03bcmkKMG]?)\s*([A-Za-z\u00b0\u2126%]*)", text)
    if not m:
        return None
    value = float(m.group(1))
    prefix = m.group(2)
    multiplier = MULTIPLIERS.get(prefix, 1.0)
    return value * multiplier


def parse_value(spec_str):
    """Parse a spec string and return a single numeric value (or midpoint of range)."""
    if not spec_str or spec_str.strip() in ("-", "", "N/A"):
        return None
    spec_str = spec_str.strip()
    for tag in ["(Typ)", "(Max)", "(Min)", "(typ)", "(max)", "(min)"]:
        spec_str = spec_str.replace(tag, "")
    spec_str = spec_str.strip()

    # Handle ranges: "1.8V ~ 3.6V" or "-40°C ~ 125°C"
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
    """Parse a spec string and return (min_value, max_value)."""
    if not spec_str or spec_str.strip() in ("-", "", "N/A"):
        return (None, None)
    spec_str = spec_str.strip()
    for tag in ["(Typ)", "(Max)", "(Min)", "(typ)", "(max)", "(min)"]:
        spec_str = spec_str.replace(tag, "")
    spec_str = spec_str.strip()

    for sep in [" ~ ", " - ", "~", " to "]:
        if sep in spec_str:
            parts = spec_str.split(sep, 1)
            low = _parse_single_value(parts[0])
            high = _parse_single_value(parts[1])
            return (low, high)

    val = _parse_single_value(spec_str)
    return (val, val)


def parse_temperature_range(spec_str):
    """Parse temperature range like '-40°C ~ 125°C'."""
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
    """Check if candidate value is within tolerance of target."""
    if target_val is None or candidate_val is None:
        return True
    if target_val == 0:
        return abs(candidate_val) < 0.001
    diff_pct = abs(candidate_val - target_val) / abs(target_val) * 100
    return diff_pct <= tolerance_pct


def range_covers(target_range, candidate_range):
    """Check if candidate range covers (equal to or wider than) target."""
    t_min, t_max = target_range
    c_min, c_max = candidate_range
    if t_min is None or t_max is None or c_min is None or c_max is None:
        return True
    return c_min <= t_min + 0.001 and c_max >= t_max - 0.001


def candidate_meets_or_exceeds(target_val, candidate_val):
    """Check if candidate meets or exceeds target (e.g. current capacity)."""
    if target_val is None or candidate_val is None:
        return True
    return candidate_val >= target_val * 0.95