"""Fallback scraper using curl_cffi with browser-grade TLS fingerprinting."""

from __future__ import annotations
import logging
import re
import time
import sys
import os
from typing import Dict, List, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bs4 import BeautifulSoup

try:
    from curl_cffi import requests as curl_requests
    CURL_AVAILABLE = True
except ImportError:
    CURL_AVAILABLE = False

from plugins.base import PluginBase
from models import Component
from config import (
    CATEGORIES, DIGIKEY_BASE, MAX_RETRIES,
    REQUEST_DELAY_SECONDS,
)

log = logging.getLogger(__name__)


class DigiKeyCurlPlugin(PluginBase):
    name = "digikey_curl"

    def __init__(self):
        self._session = None

    def setup(self):
        if not CURL_AVAILABLE:
            raise RuntimeError("curl_cffi not installed. Run: pip install curl_cffi")
        self._session = curl_requests.Session(impersonate="chrome")
        log.info("curl_cffi session ready.")

    def teardown(self):
        if self._session:
            self._session.close()

    def _get(self, url):
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                resp = self._session.get(url, timeout=30)
                if resp.status_code == 200:
                    return resp.text
                log.warning("HTTP %d from %s (attempt %d)", resp.status_code, url, attempt)
            except Exception as exc:
                log.warning("Request error %s (attempt %d)", exc, attempt)
            time.sleep(3 * attempt)
        return None

    def _parse_table(self, html, category_slug, subcategory):
        soup = BeautifulSoup(html, "lxml")
        components = []
        table = soup.find("table")
        if not table:
            log.warning("No table found in HTML.")
            return components

        header_row = table.find("thead")
        if header_row:
            headers = [th.get_text(strip=True) for th in header_row.find_all(["th", "td"])]
        else:
            first_row = table.find("tr")
            headers = [td.get_text(strip=True) for td in first_row.find_all(["th", "td"])] if first_row else []

        if not headers:
            return components

        tbody = table.find("tbody") or table
        for tr in tbody.find_all("tr"):
            cells = tr.find_all("td")
            if len(cells) < 3:
                continue
            raw = {}
            for i, cell in enumerate(cells):
                hdr = headers[i] if i < len(headers) else f"_col{i}"
                raw[hdr] = cell.get_text(strip=True)
                a = cell.find("a", href=True)
                if a:
                    href = a["href"]
                    if "datasheet" in href.lower():
                        raw["_datasheet_url"] = href if href.startswith("http") else DIGIKEY_BASE + href
                    elif "/en/products/detail/" in href:
                        raw["_product_url"] = href if href.startswith("http") else DIGIKEY_BASE + href

            comp = self._raw_to_component(raw, category_slug, subcategory)
            if comp:
                components.append(comp)
        return components

    def _raw_to_component(self, raw, cat, subcat):
        mpn = raw.get("Manufacturer Part Number") or raw.get("Mfr Part #") or raw.get("MPN") or ""
        if not mpn:
            return None

        stock_str = raw.get("Quantity Available", raw.get("Stock", ""))
        stock_clean = re.sub(r"[^\d]", "", stock_str)
        stock = int(stock_clean) if stock_clean else 0

        price_str = raw.get("Unit Price", raw.get("Price", ""))
        price_clean = re.sub(r"[^\d.]", "", price_str)
        try:
            price = float(price_clean)
        except ValueError:
            price = 0.0

        mapped = {
            "Manufacturer Part Number", "Mfr Part #", "MPN",
            "Manufacturer", "Description", "Digi-Key Part Number",
            "Quantity Available", "Stock", "Unit Price", "Price",
            "Package / Case", "Mounting Type", "Part Status",
        }
        specs = {k: v for k, v in raw.items() if k not in mapped and not k.startswith("_")}

        return Component(
            manufacturer_part_number=mpn,
            manufacturer=raw.get("Manufacturer", ""),
            digikey_part_number=raw.get("Digi-Key Part Number", ""),
            description=raw.get("Description", ""),
            category=cat, subcategory=subcat,
            datasheet_url=raw.get("_datasheet_url", ""),
            product_url=raw.get("_product_url", ""),
            stock=stock, unit_price=price,
            package=raw.get("Package / Case", ""),
            mounting_type=raw.get("Mounting Type", ""),
            lifecycle_status=raw.get("Part Status", ""),
            source="digikey", raw_specs=specs,
        )

    def _find_next_page_url(self, html):
        soup = BeautifulSoup(html, "lxml")
        for a in soup.find_all("a", href=True):
            text = a.get_text(strip=True).lower()
            if text in ("next", ">", ">>"):
                href = a["href"]
                if href.startswith("/"):
                    return DIGIKEY_BASE + href
                return href
        return None

    def scrape_category(self, category_slug, *, max_pages=None):
        cat = CATEGORIES.get(category_slug)
        if not cat:
            log.error("Unknown category: %s", category_slug)
            return []

        log.info("[curl] Scraping category: %s", cat.name)
        urls = []
        for kw in cat.search_keywords[:5]:
            urls.append(f"{DIGIKEY_BASE}/en/products/result?keywords={kw.replace(' ', '+')}")

        all_components = []
        for url in urls:
            page_num = 0
            current_url = url
            while current_url:
                page_num += 1
                if max_pages and page_num > max_pages:
                    break
                log.info("  [curl] Page %d: %s", page_num, current_url[:100])
                html = self._get(current_url)
                if not html:
                    break
                comps = self._parse_table(html, category_slug, cat.slug)
                all_components.extend(comps)
                current_url = self._find_next_page_url(html)
                time.sleep(REQUEST_DELAY_SECONDS)

        seen = set()
        unique = []
        for c in all_components:
            if c.manufacturer_part_number not in seen:
                seen.add(c.manufacturer_part_number)
                unique.append(c)
        log.info("[curl] %s: %d unique components", cat.name, len(unique))
        return unique
