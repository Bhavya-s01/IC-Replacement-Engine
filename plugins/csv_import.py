"""Imports IC data from manually downloaded CSV or TSV files."""

from __future__ import annotations
import csv
import logging
import os
import re
import sys
from typing import Dict, List, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from plugins.base import PluginBase
from models import Component

log = logging.getLogger(__name__)


class CSVImportPlugin(PluginBase):
    name = "csv_import"

    def __init__(self, directory="imports"):
        self.directory = directory

    def setup(self):
        os.makedirs(self.directory, exist_ok=True)
        log.info("CSV import plugin ready. Drop files into: %s/", self.directory)

    def teardown(self):
        pass

    def scrape_category(self, category_slug, *, max_pages=None):
        components = []
        if not os.path.isdir(self.directory):
            log.warning("Import directory does not exist: %s", self.directory)
            return components

        for fname in os.listdir(self.directory):
            if category_slug not in fname.lower():
                continue
            if not fname.lower().endswith((".csv", ".tsv", ".txt")):
                continue

            fpath = os.path.join(self.directory, fname)
            log.info("Importing %s", fpath)

            delimiter = "\t" if fname.endswith(".tsv") else ","
            with open(fpath, newline="", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f, delimiter=delimiter)
                for row in reader:
                    comp = self._row_to_component(dict(row), category_slug)
                    if comp:
                        components.append(comp)

            log.info("  -> %d components from %s", len(components), fname)
        return components

    @staticmethod
    def _row_to_component(row, category_slug):
        mpn = (
            row.get("Manufacturer Part Number")
            or row.get("Mfr Part #")
            or row.get("MPN")
            or row.get("Part Number")
            or ""
        ).strip()
        if not mpn:
            return None

        stock_str = row.get("Quantity Available", row.get("Stock", "0"))
        stock_clean = re.sub(r"[^\d]", "", stock_str)
        stock = int(stock_clean) if stock_clean else 0

        price_str = row.get("Unit Price", row.get("Price", "0"))
        price_clean = re.sub(r"[^\d.]", "", price_str)
        try:
            price = float(price_clean)
        except ValueError:
            price = 0.0

        common_keys = {
            "Manufacturer Part Number", "Mfr Part #", "MPN", "Part Number",
            "Manufacturer", "Description", "Digi-Key Part Number",
            "Quantity Available", "Stock", "Unit Price", "Price",
            "Package / Case", "Mounting Type", "Part Status",
            "Datasheet", "Product URL",
        }
        specs = {k: v for k, v in row.items() if k not in common_keys and v}

        return Component(
            manufacturer_part_number=mpn,
            manufacturer=row.get("Manufacturer", ""),
            digikey_part_number=row.get("Digi-Key Part Number", ""),
            description=row.get("Description", ""),
            category=category_slug,
            subcategory="csv_import",
            datasheet_url=row.get("Datasheet", ""),
            product_url=row.get("Product URL", ""),
            stock=stock, unit_price=price,
            package=row.get("Package / Case", ""),
            mounting_type=row.get("Mounting Type", ""),
            lifecycle_status=row.get("Part Status", ""),
            source="csv_import", raw_specs=specs,
        )
