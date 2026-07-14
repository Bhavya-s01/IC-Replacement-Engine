"""Gap 17: Parse all price break tiers, not just the first one."""

import re
import json


def parse_price_breaks(price_cell_text):
    """
    Parse DigiKey's multi-line price cell.
    Input: "1 : $0.81000\\nCut Tape (CT)\\n4,000 : $0.37516\\nTape & Reel (TR)"
    Output: [(1, 0.81), (4000, 0.37516)]
    """
    if not price_cell_text:
        return []

    breaks = []
    pattern = r"([\d,]+)\s*:\s*\$([\d.]+)"
    matches = re.findall(pattern, price_cell_text)

    for qty_str, price_str in matches:
        try:
            qty = int(qty_str.replace(",", ""))
            price = float(price_str)
            breaks.append((qty, price))
        except ValueError:
            continue

    breaks.sort(key=lambda x: x[0])
    return breaks


def price_breaks_to_json(breaks):
    return json.dumps([{"quantity": q, "unit_price": p} for q, p in breaks])