"""Gap 11: Fuzzy spec name normalization across DigiKey inconsistencies."""

import re

SPEC_ALIASES = {
    "Voltage - Supply": [
        "Voltage - Supply", "Voltage - Supply (V)", "Supply Voltage",
        "Voltage Supply", "VDD", "Vcc", "Voltage - Supply (Vcc/Vdd)",
        "Operating Voltage",
    ],
    "Voltage - Output": [
        "Voltage - Output (Min/Fixed)", "Voltage - Output", "Output Voltage",
        "Voltage - Output (Max)", "Vout",
    ],
    "Voltage - Input": [
        "Voltage - Input (Min)", "Voltage - Input (Max)", "Voltage - Input",
        "Input Voltage", "Vin",
    ],
    "Current - Output": [
        "Current - Output", "Current - Output (Max)", "Output Current",
        "Current Output", "Iout", "Iout (Max)",
    ],
    "Current - Quiescent": [
        "Current - Quiescent (Iq)", "Quiescent Current", "Iq",
        "Current - Supply", "Supply Current", "Idd",
    ],
    "Operating Temperature": [
        "Operating Temperature", "Temperature Range",
        "Operating Temp Range", "Temperature - Operating",
    ],
    "Package": [
        "Package / Case", "Package", "Case",
        "Supplier Device Package",
    ],
}

_ALIAS_MAP = {}
for canonical, variants in SPEC_ALIASES.items():
    for v in variants:
        _ALIAS_MAP[v.lower().strip()] = canonical


def normalize_spec_name(raw_name):
    """Map a raw DigiKey spec name to its canonical form."""
    canonical = _ALIAS_MAP.get(raw_name.lower().strip())
    if canonical:
        return canonical

    cleaned = re.sub(r"\s*\(.*?\)\s*", "", raw_name).strip()
    canonical = _ALIAS_MAP.get(cleaned.lower())
    if canonical:
        return canonical

    return raw_name