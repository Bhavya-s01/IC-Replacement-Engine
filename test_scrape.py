"""
test_scrape.py - Quick test: scrape 1 page of 1 subcategory
Run: python test_scrape.py
"""

import sys
import os
import logging

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(message)s")

from plugins.digikey_playwright import DigiKeyPlaywrightPlugin
from database import Database

db = Database()
plugin = DigiKeyPlaywrightPlugin()
plugin.setup()

try:
    comps = plugin._scrape_single_url(
        "/en/products/filter/integrated-circuits-ics/pmic-voltage-regulators-linear/699",
        "power_ic",
        "pmic-voltage-regulators-linear",
        max_pages=3,
    )
    print("")
    print("Scraped {} components".format(len(comps)))

    if comps:
        count = db.bulk_upsert(comps)
        print("Saved {} to database".format(count))

        print("")
        print("=== SAMPLES ===")
        for c in comps[:5]:
            print("  MPN:  {}".format(c.manufacturer_part_number))
            print("  MFR:  {}".format(c.manufacturer))
            print("  DESC: {}".format(c.description))
            print("  STOCK: {}  PRICE: {}".format(c.stock, c.unit_price))
            print("  SPECS: {}".format(list(c.raw_specs.keys())[:6]))
            print("")
    else:
        print("No components scraped!")

finally:
    plugin.teardown()
    db.close()

print("Done!")