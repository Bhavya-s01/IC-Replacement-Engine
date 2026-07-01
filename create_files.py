"""
Run this once to create/fix all project files.
Usage: python create_files.py
"""

import os

BASE = os.path.dirname(os.path.abspath(__file__))
PLUGINS = os.path.join(BASE, "plugins")
os.makedirs(PLUGINS, exist_ok=True)

files = {}

# ============================================================
# plugins/__init__.py
# ============================================================
files[os.path.join(PLUGINS, "__init__.py")] = '"""IC Scraper plugin package."""\n'

# ============================================================
# plugins/base.py
# ============================================================
files[os.path.join(PLUGINS, "base.py")] = r'''"""Abstract base class for all data-source plugins."""

from abc import ABC, abstractmethod
from typing import List, Optional
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from models import Component


class PluginBase(ABC):
    name: str = "base"

    @abstractmethod
    def setup(self) -> None:
        ...

    @abstractmethod
    def scrape_category(self, category_slug: str, *, max_pages: Optional[int] = None) -> List[Component]:
        ...

    @abstractmethod
    def teardown(self) -> None:
        ...

    def __repr__(self):
        return f"<Plugin: {self.name}>"
'''

# ============================================================
# plugins/digikey_curl.py
# ============================================================
files[os.path.join(PLUGINS, "digikey_curl.py")] = r'''"""Fallback scraper using curl_cffi with browser-grade TLS fingerprinting."""

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
'''

# ============================================================
# plugins/csv_import.py
# ============================================================
files[os.path.join(PLUGINS, "csv_import.py")] = r'''"""Imports IC data from manually downloaded CSV or TSV files."""

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
'''

# ============================================================
# plugins/digikey_playwright.py
# ============================================================
files[os.path.join(PLUGINS, "digikey_playwright.py")] = r'''"""Playwright + Edge scraper for DigiKey."""

from __future__ import annotations

import csv
import logging
import os
import re
import sys
import time
from typing import Dict, List, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from playwright.sync_api import (
    Browser, BrowserContext, Page, Playwright,
    sync_playwright, TimeoutError as PwTimeout,
)

from plugins.base import PluginBase
from models import Component
from config import (
    CATEGORIES, DIGIKEY_BASE, DIGIKEY_IC_LANDING, DOWNLOAD_DIR,
    EDGE_CHANNEL, HEADLESS_MODE, MAX_RETRIES,
    PAGE_LOAD_TIMEOUT_MS, REQUEST_DELAY_SECONDS, ICCategory,
)

log = logging.getLogger(__name__)

SELECTORS = {
    "table": [
        "table.MuiTable-root",
        "table[role='table']",
        "#data-table-0",
        "table",
    ],
    "thead_cells": [
        "thead th", "thead td",
        "tr.header-row th", "tr:first-child th",
    ],
    "tbody_rows": [
        "tbody tr[data-testid]",
        "tbody tr",
        "table tr:not(:first-child)",
    ],
    "per_page": [
        "select[data-testid='per-page']",
        "select.per-page-select",
        "select[aria-label*='per page']",
        "select[aria-label*='Per Page']",
    ],
    "next_page": [
        "button[data-testid='btn-next']",
        "button[aria-label='Next']",
        "a[aria-label='Next']",
        "button:has-text('Next')",
        "li.next a",
    ],
    "result_count": [
        "[data-testid='result-count']",
        "span.matching-records",
        "div.results-count",
    ],
    "download_btn": [
        "button[data-testid='download-table']",
        "button:has-text('Download Table')",
        "a:has-text('Download Table')",
        "button:has-text('Download')",
    ],
    "cookie_dismiss": [
        "button#onetrust-accept-btn-handler",
        "button:has-text('Accept All')",
        "button:has-text('Accept')",
        "button:has-text('I Agree')",
    ],
    "datasheet_link": [
        "a[data-testid='datasheet-link']",
        "a[href*='datasheet']",
        "a[title*='Datasheet']",
    ],
    "part_link": [
        "a[data-testid='part-number-link']",
        "a[href*='/en/products/detail/']",
    ],
}


def _first_match(page, selectors, timeout=5000):
    for sel in selectors:
        try:
            el = page.wait_for_selector(sel, timeout=timeout, state="attached")
            if el:
                return el
        except PwTimeout:
            continue
    return None


def _all_matches(page, selectors):
    for sel in selectors:
        results = page.query_selector_all(sel)
        if results:
            return results
    return []


class DigiKeyPlaywrightPlugin(PluginBase):
    name = "digikey_playwright"

    def __init__(self):
        self._pw = None
        self._browser = None
        self._context = None
        self._page = None

    def setup(self):
        log.info("Launching Playwright with Microsoft Edge...")
        os.makedirs(DOWNLOAD_DIR, exist_ok=True)

        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch(
            channel=EDGE_CHANNEL,
            headless=HEADLESS_MODE,
            args=["--disable-blink-features=AutomationControlled"],
        )
        self._context = self._browser.new_context(
            accept_downloads=True,
            viewport={"width": 1920, "height": 1080},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/125.0.0.0 Safari/537.36 Edg/125.0.0.0"
            ),
        )
        self._context.set_default_timeout(PAGE_LOAD_TIMEOUT_MS)
        self._page = self._context.new_page()
        self._page.goto(DIGIKEY_BASE, wait_until="domcontentloaded")
        self._dismiss_overlays()
        log.info("Browser ready.")

    def teardown(self):
        log.info("Shutting down browser...")
        if self._context:
            self._context.close()
        if self._browser:
            self._browser.close()
        if self._pw:
            self._pw.stop()

    def _dismiss_overlays(self):
        page = self._page
        for sel in SELECTORS["cookie_dismiss"]:
            try:
                btn = page.query_selector(sel)
                if btn and btn.is_visible():
                    btn.click()
                    log.debug("Dismissed overlay with %s", sel)
                    time.sleep(1)
                    return
            except Exception:
                continue

    def _polite_wait(self):
        time.sleep(REQUEST_DELAY_SECONDS)

    def _goto(self, url):
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                self._page.goto(url, wait_until="domcontentloaded")
                self._dismiss_overlays()
                return
            except Exception as exc:
                log.warning("Nav attempt %d failed: %s", attempt, exc)
                if attempt == MAX_RETRIES:
                    raise
                time.sleep(3 * attempt)

    def _discover_subcategory_urls(self):
        log.info("Discovering DigiKey subcategory URLs...")
        self._goto(DIGIKEY_IC_LANDING)
        self._polite_wait()

        all_anchors = self._page.query_selector_all("a[href]")
        hrefs = {}
        for a in all_anchors:
            href = a.get_attribute("href") or ""
            if "/en/products/filter/" in href or "/en/products/category/" in href:
                if href.startswith("/"):
                    href = DIGIKEY_BASE + href
                parts = href.rstrip("/").split("/")
                slug = parts[-1] if parts else ""
                if slug and not slug.isdigit():
                    hrefs[slug] = href

        log.info("Discovered %d subcategory URLs", len(hrefs))
        return hrefs

    def _match_urls_to_category(self, category, discovered):
        matched = []
        for desired_slug in category.digikey_subcategory_slugs:
            for disc_slug, url in discovered.items():
                if desired_slug in disc_slug or disc_slug in desired_slug:
                    if url not in matched:
                        matched.append(url)
        if not matched:
            for kw in category.search_keywords[:3]:
                search_url = (
                    f"{DIGIKEY_BASE}/en/products/result"
                    f"?keywords={kw.replace(' ', '+')}"
                )
                matched.append(search_url)
        log.info("Category %s matched %d URLs", category.name, len(matched))
        return matched

    def _try_csv_download(self):
        page = self._page
        download_btn = None
        for sel in SELECTORS["download_btn"]:
            download_btn = page.query_selector(sel)
            if download_btn and download_btn.is_visible():
                break
            download_btn = None

        if not download_btn:
            log.debug("No Download Table button found.")
            return None

        try:
            with page.expect_download(timeout=30_000) as dl_info:
                download_btn.click()
            download = dl_info.value
            dest = os.path.join(DOWNLOAD_DIR, download.suggested_filename or "table.csv")
            download.save_as(dest)
            log.info("Downloaded CSV -> %s", dest)
            return dest
        except Exception as exc:
            log.warning("CSV download failed: %s", exc)
            return None

    def _parse_csv_file(self, csv_path, category_slug, subcategory):
        components = []
        with open(csv_path, newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                comp = self._row_to_component(dict(row), category_slug, subcategory)
                if comp:
                    components.append(comp)
        log.info("Parsed %d components from CSV", len(components))
        return components

    def _set_per_page_max(self):
        page = self._page
        for sel in SELECTORS["per_page"]:
            el = page.query_selector(sel)
            if el:
                try:
                    for val in ["100", "500", "250"]:
                        try:
                            el.select_option(value=val)
                            log.debug("Set per-page to %s", val)
                            page.wait_for_load_state("networkidle", timeout=15_000)
                            return
                        except Exception:
                            continue
                except Exception:
                    continue

    def _get_total_results(self):
        page = self._page
        for sel in SELECTORS["result_count"]:
            el = page.query_selector(sel)
            if el:
                text = el.inner_text()
                m = re.search(r"of\s+([\d,]+)", text)
                if m:
                    return int(m.group(1).replace(",", ""))

        body = page.inner_text("body")
        m = re.search(r"of\s+([\d,]+)\s+[Rr]esults", body)
        if m:
            return int(m.group(1).replace(",", ""))
        return 0

    def _extract_table_headers(self):
        cells = _all_matches(self._page, SELECTORS["thead_cells"])
        headers = [c.inner_text().strip() for c in cells]
        return [h for h in headers if h and h.lower() not in ("", "compare", "image", "photo")]

    def _extract_table_rows(self, headers, category_slug, subcategory):
        page = self._page
        rows_els = _all_matches(page, SELECTORS["tbody_rows"])
        components = []

        for row_el in rows_els:
            cells = row_el.query_selector_all("td")
            raw = {}
            for i, cell in enumerate(cells):
                text = cell.inner_text().strip()
                if i < len(headers):
                    raw[headers[i]] = text
                else:
                    raw[f"_col{i}"] = text

            ds_link = ""
            for sel in SELECTORS["datasheet_link"]:
                a = row_el.query_selector(sel)
                if a:
                    ds_link = a.get_attribute("href") or ""
                    if ds_link.startswith("/"):
                        ds_link = DIGIKEY_BASE + ds_link
                    break

            part_url = ""
            for sel in SELECTORS["part_link"]:
                a = row_el.query_selector(sel)
                if a:
                    part_url = a.get_attribute("href") or ""
                    if part_url.startswith("/"):
                        part_url = DIGIKEY_BASE + part_url
                    break

            if ds_link:
                raw["_datasheet_url"] = ds_link
            if part_url:
                raw["_product_url"] = part_url

            comp = self._row_to_component(raw, category_slug, subcategory)
            if comp:
                components.append(comp)

        return components

    def _click_next_page(self):
        page = self._page
        for sel in SELECTORS["next_page"]:
            btn = page.query_selector(sel)
            if btn:
                if btn.is_disabled():
                    return False
                aria = btn.get_attribute("aria-disabled")
                if aria == "true":
                    return False
                cls = btn.get_attribute("class") or ""
                if "disabled" in cls.lower():
                    return False
                try:
                    btn.click()
                    page.wait_for_load_state("networkidle", timeout=15_000)
                    self._polite_wait()
                    return True
                except Exception as exc:
                    log.warning("Next-page click failed: %s", exc)
                    return False
        return False

    _FIELD_MAP = {
        "manufacturer_part_number": [
            "Manufacturer Part Number", "Mfr Part #", "MPN",
            "Manufacturer Part #", "Part Number",
        ],
        "manufacturer": ["Manufacturer", "Mfr", "Vendor"],
        "description": ["Description", "Product Description", "Desc"],
        "digikey_part_number": [
            "Digi-Key Part Number", "DK Part #", "DigiKey Part #",
        ],
        "stock": ["Quantity Available", "Stock", "Qty Available", "In Stock"],
        "unit_price": [
            "Unit Price", "Price", "Unit Price (USD)",
            "Price (USD)", "Unit Price USD",
        ],
        "package": [
            "Package / Case", "Package", "Case",
            "Supplier Device Package",
        ],
        "mounting_type": ["Mounting Type", "Mount Type"],
        "lifecycle_status": ["Part Status", "Lifecycle", "Status"],
        "datasheet_url": ["Datasheet", "_datasheet_url"],
        "product_url": ["_product_url", "Product URL"],
    }

    def _row_to_component(self, raw, category_slug, subcategory):
        def _find(field_keys):
            for k in field_keys:
                if k in raw:
                    return raw[k]
            return ""

        mpn = _find(self._FIELD_MAP["manufacturer_part_number"])
        if not mpn:
            return None

        stock_str = _find(self._FIELD_MAP["stock"])
        stock = 0
        if stock_str:
            stock_clean = re.sub(r"[^\d]", "", stock_str)
            stock = int(stock_clean) if stock_clean else 0

        price_str = _find(self._FIELD_MAP["unit_price"])
        price = 0.0
        if price_str:
            price_clean = re.sub(r"[^\d.]", "", price_str)
            try:
                price = float(price_clean)
            except ValueError:
                pass

        mapped_keys = set()
        for keys in self._FIELD_MAP.values():
            mapped_keys.update(keys)
        specs = {k: v for k, v in raw.items() if k not in mapped_keys and not k.startswith("_")}

        return Component(
            manufacturer_part_number=mpn,
            manufacturer=_find(self._FIELD_MAP["manufacturer"]),
            digikey_part_number=_find(self._FIELD_MAP["digikey_part_number"]),
            description=_find(self._FIELD_MAP["description"]),
            category=category_slug,
            subcategory=subcategory,
            datasheet_url=_find(self._FIELD_MAP["datasheet_url"]),
            product_url=_find(self._FIELD_MAP["product_url"]),
            stock=stock,
            unit_price=price,
            package=_find(self._FIELD_MAP["package"]),
            mounting_type=_find(self._FIELD_MAP["mounting_type"]),
            lifecycle_status=_find(self._FIELD_MAP["lifecycle_status"]),
            source="digikey",
            raw_specs=specs,
        )

    def _scrape_single_url(self, url, category_slug, subcategory, *, max_pages=None):
        log.info("Scraping %s", url)
        self._goto(url)
        self._polite_wait()

        # Strategy 1: CSV download
        csv_path = self._try_csv_download()
        if csv_path:
            return self._parse_csv_file(csv_path, category_slug, subcategory)

        # Strategy 2: HTML table scraping
        log.info("Using HTML table scraping for %s", url)
        self._set_per_page_max()
        self._polite_wait()

        total = self._get_total_results()
        log.info("Total results: %d", total)

        all_components = []
        headers = self._extract_table_headers()
        if not headers:
            log.warning("Could not extract table headers from %s", url)
            return all_components
        log.debug("Table headers: %s", headers)

        page_num = 0
        while True:
            page_num += 1
            if max_pages and page_num > max_pages:
                log.info("Reached max_pages=%d, stopping.", max_pages)
                break

            log.info("  Page %d (collected %d so far)", page_num, len(all_components))
            comps = self._extract_table_rows(headers, category_slug, subcategory)
            all_components.extend(comps)

            if not self._click_next_page():
                log.info("  No more pages.")
                break

        log.info("Scraped %d components from %s", len(all_components), url)
        return all_components

    def scrape_category(self, category_slug, *, max_pages=None):
        cat = CATEGORIES.get(category_slug)
        if not cat:
            log.error("Unknown category slug: %s", category_slug)
            return []

        log.info("=== Scraping category: %s ===", cat.name)

        discovered = self._discover_subcategory_urls()
        urls = self._match_urls_to_category(cat, discovered)

        if not urls:
            for kw in cat.search_keywords[:2]:
                urls.append(
                    f"{DIGIKEY_BASE}/en/products/result"
                    f"?keywords={kw.replace(' ', '+')}"
                )

        all_components = []
        for url in urls:
            subcategory = url.rstrip("/").split("/")[-2] if "/filter/" in url else "search"
            try:
                comps = self._scrape_single_url(
                    url, category_slug, subcategory, max_pages=max_pages
                )
                all_components.extend(comps)
            except Exception as exc:
                log.error("Failed scraping %s: %s", url, exc, exc_info=True)

        seen = set()
        unique = []
        for c in all_components:
            if c.manufacturer_part_number not in seen:
                seen.add(c.manufacturer_part_number)
                unique.append(c)

        log.info("=== %s complete: %d unique components ===", cat.name, len(unique))
        return unique
'''

# ============================================================
# config.py
# ============================================================
files[os.path.join(BASE, "config.py")] = r'''"""
config.py - Central configuration for the IC Database Engine.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional
import os

DB_PATH = os.environ.get("IC_DB_PATH", "ic_database.db")

REQUEST_DELAY_SECONDS = 2.0
PAGE_LOAD_TIMEOUT_MS  = 60_000
MAX_RETRIES           = 3
RESULTS_PER_PAGE      = 100
HEADLESS_MODE         = False
EDGE_CHANNEL          = "msedge"
DOWNLOAD_DIR          = os.path.join(os.path.dirname(os.path.abspath(__file__)), "downloads")

DIGIKEY_BASE       = "https://www.digikey.com"
DIGIKEY_IC_LANDING = f"{DIGIKEY_BASE}/en/products/category/integrated-circuits-ics/32"


@dataclass
class ICCategory:
    name: str
    slug: str
    digikey_subcategory_slugs: List[str]
    search_keywords: List[str]
    key_specifications: List[str]
    description: str = ""


CATEGORIES: Dict[str, ICCategory] = {

    "power_ic": ICCategory(
        name="Power IC",
        slug="power_ic",
        digikey_subcategory_slugs=[
            "pmic-voltage-regulators-linear",
            "pmic-voltage-regulators-dc-dc-switching-regulators",
            "pmic-voltage-regulators-dc-dc-switching-controllers",
            "pmic-voltage-regulators-dc-dc-converters",
            "pmic-full-half-bridge-drivers",
            "pmic-gate-drivers",
            "pmic-battery-management",
            "pmic-power-distribution-switches",
            "pmic-voltage-reference",
            "pmic-ac-dc-converters-offline-switchers",
            "pmic-led-drivers",
            "pmic-hot-swap-controllers",
            "pmic-motor-drivers-controllers",
            "pmic-or-controllers-ideal-diodes",
            "pmic-supervisors",
            "pmic-current-regulation-management",
            "pmic-power-management-specialized",
        ],
        search_keywords=[
            "voltage regulator", "LDO", "DC-DC converter",
            "buck converter", "boost converter", "PMIC",
            "gate driver", "LED driver", "battery charger",
        ],
        key_specifications=[
            "Output Voltage", "Input Voltage", "Output Current",
            "Dropout Voltage", "Quiescent Current", "Switching Frequency",
            "Efficiency", "Topology", "Number of Outputs",
            "Voltage - Input (Min)", "Voltage - Input (Max)",
            "Voltage - Output (Min/Fixed)", "Voltage - Output (Max)",
            "Current - Output", "Current - Quiescent (Iq)",
        ],
        description="Linear regulators, DC-DC converters, PMICs, gate drivers, LED drivers",
    ),

    "memory_ic": ICCategory(
        name="Memory IC",
        slug="memory_ic",
        digikey_subcategory_slugs=["memory", "sram", "dram", "fifo", "memory-configuration-proms-for-fpgas"],
        search_keywords=["SRAM", "DRAM", "SDRAM", "DDR memory", "FIFO memory"],
        key_specifications=["Memory Size", "Memory Type", "Memory Interface", "Clock Frequency", "Access Time", "Voltage - Supply", "Operating Temperature", "Write Endurance"],
        description="SRAM, DRAM, SDRAM, FIFO, and other volatile memory",
    ),

    "flash_ic": ICCategory(
        name="Flash IC",
        slug="flash_ic",
        digikey_subcategory_slugs=["nor-flash", "nand-flash", "eeprom", "flash"],
        search_keywords=["NOR flash", "NAND flash", "SPI flash", "EEPROM", "serial flash", "parallel flash"],
        key_specifications=["Memory Size", "Memory Interface", "Clock Frequency", "Write Cycle Time", "Write Endurance", "Data Retention", "Voltage - Supply", "Operating Temperature"],
        description="NOR flash, NAND flash, EEPROM, serial/parallel flash",
    ),

    "scalar_ic": ICCategory(
        name="Scalar IC",
        slug="scalar_ic",
        digikey_subcategory_slugs=["microcontrollers", "microprocessors", "digital-signal-processors-dsp", "fpga", "cpld", "system-on-chip-soc"],
        search_keywords=["microcontroller", "MCU", "ARM Cortex", "RISC-V", "DSP", "FPGA", "SoC"],
        key_specifications=["Core Processor", "Core Size", "Speed", "Program Memory Size", "RAM Size", "Number of I/O", "Peripherals", "Connectivity", "Voltage - Supply", "Operating Temperature"],
        description="Microcontrollers, microprocessors, DSPs, FPGAs",
    ),

    "audio_ic": ICCategory(
        name="Audio IC",
        slug="audio_ic",
        digikey_subcategory_slugs=["audio-special-purpose", "audio-amplifiers"],
        search_keywords=["audio codec", "audio amplifier", "DAC audio", "ADC audio", "class D amplifier", "audio DSP", "I2S"],
        key_specifications=["Type", "Output Type", "Output Power", "S/N Ratio", "THD + Noise", "Sample Rate", "Resolution (Bits)", "Number of Channels", "Interface", "Voltage - Supply"],
        description="Audio codecs, amplifiers, DACs, ADCs, Class-D drivers",
    ),

    "usb_ic": ICCategory(
        name="USB IC",
        slug="usb_ic",
        digikey_subcategory_slugs=["usb-interface-ics", "interface-controllers", "interface-specialized"],
        search_keywords=["USB controller", "USB hub", "USB switch", "USB Type-C", "USB PD", "USB transceiver", "USB bridge"],
        key_specifications=["Protocol", "USB Standard", "Data Rate", "Number of Ports", "Features", "Voltage - Supply", "Operating Temperature"],
        description="USB controllers, hubs, bridges, Type-C PD controllers",
    ),

    "sensor_ic": ICCategory(
        name="Sensor IC",
        slug="sensor_ic",
        digikey_subcategory_slugs=["temperature-sensors-analog-and-digital-output", "pressure-sensors-transducers", "magnetic-sensors-linear-compasses", "magnetic-sensors-hall-effect-switches", "accelerometers", "gyroscopes", "inertial-measurement-units-imus", "humidity-moisture-sensors", "ambient-light-sensors", "current-sensors", "image-sensors-camera", "proximity-sensors"],
        search_keywords=["temperature sensor", "accelerometer", "gyroscope", "IMU", "pressure sensor", "humidity sensor", "hall effect", "current sensor", "ambient light sensor"],
        key_specifications=["Sensor Type", "Sensing Range", "Sensitivity", "Accuracy", "Resolution", "Interface", "Output Type", "Voltage - Supply", "Operating Temperature", "Response Time"],
        description="Temperature, pressure, IMU, hall, current, light sensors",
    ),

    "protection_ic": ICCategory(
        name="Protection IC",
        slug="protection_ic",
        digikey_subcategory_slugs=["esd-suppressors-tvs", "esd-protection-diodes", "pmic-voltage-supervisors", "pmic-thermal-management", "over-voltage-protection"],
        search_keywords=["ESD protection", "TVS diode", "overvoltage protection", "voltage supervisor", "eFuse", "load switch protection"],
        key_specifications=["Type", "Voltage - Clamping", "Voltage - Breakdown", "Voltage - Reverse Standoff", "Current - Peak Pulse", "Number of Circuits", "Capacitance", "Voltage - Supply", "Operating Temperature"],
        description="ESD protection, TVS, voltage supervisors, eFuses",
    ),

    "mux_logic_ic": ICCategory(
        name="MUX/Logic IC",
        slug="mux_logic_ic",
        digikey_subcategory_slugs=["logic-buffers-drivers-receivers-transceivers", "logic-gates-and-inverters", "logic-flip-flops", "logic-shift-registers", "logic-counters-dividers", "logic-comparators", "logic-multiplexers", "logic-signal-switches-multiplexers-decoders", "logic-level-translators-shifters", "logic-latches"],
        search_keywords=["multiplexer", "logic gate", "buffer driver", "level shifter", "bus switch", "decoder", "shift register", "flip flop"],
        key_specifications=["Logic Type", "Number of Circuits", "Number of Inputs", "Number of Outputs", "Voltage - Supply", "Logic Level", "Propagation Delay", "Output Type", "Current - Output High/Low", "Operating Temperature"],
        description="Multiplexers, logic gates, buffers, level shifters, decoders",
    ),

    "ethernet_ic": ICCategory(
        name="Ethernet IC",
        slug="ethernet_ic",
        digikey_subcategory_slugs=["ethernet-ics", "interface-ethernet-controllers"],
        search_keywords=["Ethernet PHY", "Ethernet controller", "Ethernet switch", "Ethernet transceiver", "Ethernet MAC"],
        key_specifications=["Protocol", "Data Rate", "Number of Ports", "Interface", "Standards", "Features", "Voltage - Supply", "Operating Temperature"],
        description="Ethernet PHYs, MACs, controllers, switches",
    ),

    "opto_ic": ICCategory(
        name="Opto IC",
        slug="opto_ic",
        digikey_subcategory_slugs=["optoisolators-transistor-photovoltaic-output", "optoisolators-triac-scr-output", "optoisolators-logic-output", "optoisolators-gate-driver-output"],
        search_keywords=["optocoupler", "optoisolator", "photo coupler", "optical isolator", "gate driver opto"],
        key_specifications=["Output Type", "Number of Channels", "Current Transfer Ratio (CTR)", "Voltage - Isolation", "Voltage - Forward (Vf)", "Current - Input (If)", "Voltage - Output (Max)", "Current - Output / Channel", "Turn On / Turn Off Time", "Operating Temperature"],
        description="Optocouplers, optoisolators (transistor, triac, logic, gate driver output)",
    ),
}


def get_category(slug):
    return CATEGORIES.get(slug)


def all_category_slugs():
    return sorted(CATEGORIES.keys())
'''

# ============================================================
# models.py
# ============================================================
files[os.path.join(BASE, "models.py")] = r'''"""Data models for scraped IC components."""

from dataclasses import dataclass, field
from typing import Dict, List, Optional
from datetime import datetime
import json


@dataclass
class PriceBreak:
    quantity: int
    unit_price: float

    def to_dict(self):
        return {"quantity": self.quantity, "unit_price": self.unit_price}


@dataclass
class Component:
    manufacturer_part_number: str
    manufacturer: str
    digikey_part_number: str = ""
    description: str = ""
    category: str = ""
    subcategory: str = ""
    datasheet_url: str = ""
    product_url: str = ""
    stock: int = 0
    unit_price: float = 0.0
    price_breaks: List[PriceBreak] = field(default_factory=list)
    package: str = ""
    mounting_type: str = ""
    lifecycle_status: str = ""
    source: str = "digikey"
    scraped_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    raw_specs: Dict[str, str] = field(default_factory=dict)
    substitutes: List[str] = field(default_factory=list)

    def price_breaks_json(self):
        return json.dumps([pb.to_dict() for pb in self.price_breaks])

    def raw_specs_json(self):
        return json.dumps(self.raw_specs, ensure_ascii=False)

    def __repr__(self):
        return f"Component({self.manufacturer_part_number!r}, mfr={self.manufacturer!r}, cat={self.category!r})"
'''

# ============================================================
# database.py
# ============================================================
files[os.path.join(BASE, "database.py")] = r'''"""SQLite database manager for the IC database."""

import sqlite3
import json
import logging
import sys
import os
from typing import Dict, List, Optional
from contextlib import contextmanager

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from models import Component
from config import DB_PATH

log = logging.getLogger(__name__)

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS components (
    id                        INTEGER PRIMARY KEY AUTOINCREMENT,
    digikey_part_number       TEXT,
    manufacturer_part_number  TEXT,
    manufacturer              TEXT,
    description               TEXT,
    category                  TEXT,
    subcategory               TEXT,
    datasheet_url             TEXT,
    product_url               TEXT,
    stock                     INTEGER DEFAULT 0,
    unit_price                REAL    DEFAULT 0.0,
    price_breaks              TEXT    DEFAULT '[]',
    package                   TEXT,
    mounting_type             TEXT,
    lifecycle_status          TEXT,
    source                    TEXT    DEFAULT 'digikey',
    scraped_at                TEXT,
    raw_data                  TEXT    DEFAULT '{}',
    UNIQUE(manufacturer_part_number, source)
);

CREATE TABLE IF NOT EXISTS specifications (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    component_id  INTEGER NOT NULL,
    spec_name     TEXT    NOT NULL,
    spec_value    TEXT,
    FOREIGN KEY (component_id) REFERENCES components(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS substitutes (
    id                         INTEGER PRIMARY KEY AUTOINCREMENT,
    component_id               INTEGER NOT NULL,
    substitute_part_number     TEXT,
    substitute_manufacturer    TEXT,
    compatibility_notes        TEXT,
    FOREIGN KEY (component_id) REFERENCES components(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_comp_category    ON components(category);
CREATE INDEX IF NOT EXISTS idx_comp_mfr         ON components(manufacturer);
CREATE INDEX IF NOT EXISTS idx_comp_mpn         ON components(manufacturer_part_number);
CREATE INDEX IF NOT EXISTS idx_comp_source      ON components(source);
CREATE INDEX IF NOT EXISTS idx_spec_comp        ON specifications(component_id);
CREATE INDEX IF NOT EXISTS idx_spec_name        ON specifications(spec_name);
CREATE INDEX IF NOT EXISTS idx_spec_name_value  ON specifications(spec_name, spec_value);
CREATE INDEX IF NOT EXISTS idx_sub_comp         ON substitutes(component_id);
"""


class Database:
    def __init__(self, db_path=DB_PATH):
        self.db_path = db_path
        self._conn = None
        self._init_db()

    def _get_conn(self):
        if self._conn is None:
            self._conn = sqlite3.connect(self.db_path)
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA foreign_keys=ON")
            self._conn.execute("PRAGMA synchronous=NORMAL")
            self._conn.row_factory = sqlite3.Row
        return self._conn

    def _init_db(self):
        conn = self._get_conn()
        conn.executescript(SCHEMA_SQL)
        conn.commit()
        log.info("Database initialised at %s", self.db_path)

    @contextmanager
    def transaction(self):
        conn = self._get_conn()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    def close(self):
        if self._conn:
            self._conn.close()
            self._conn = None

    def upsert_component(self, comp):
        conn = self._get_conn()
        conn.execute(
            """
            INSERT INTO components (
                digikey_part_number, manufacturer_part_number,
                manufacturer, description, category, subcategory,
                datasheet_url, product_url, stock, unit_price,
                price_breaks, package, mounting_type,
                lifecycle_status, source, scraped_at, raw_data
            ) VALUES (
                :dk, :mpn, :mfr, :desc, :cat, :subcat,
                :ds, :url, :stock, :price, :pb, :pkg,
                :mount, :lc, :src, :ts, :raw
            )
            ON CONFLICT(manufacturer_part_number, source) DO UPDATE SET
                digikey_part_number = excluded.digikey_part_number,
                manufacturer        = excluded.manufacturer,
                description         = excluded.description,
                category            = excluded.category,
                subcategory         = excluded.subcategory,
                datasheet_url       = excluded.datasheet_url,
                product_url         = excluded.product_url,
                stock               = excluded.stock,
                unit_price          = excluded.unit_price,
                price_breaks        = excluded.price_breaks,
                package             = excluded.package,
                mounting_type       = excluded.mounting_type,
                lifecycle_status    = excluded.lifecycle_status,
                scraped_at          = excluded.scraped_at,
                raw_data            = excluded.raw_data
            """,
            {
                "dk": comp.digikey_part_number,
                "mpn": comp.manufacturer_part_number,
                "mfr": comp.manufacturer,
                "desc": comp.description,
                "cat": comp.category,
                "subcat": comp.subcategory,
                "ds": comp.datasheet_url,
                "url": comp.product_url,
                "stock": comp.stock,
                "price": comp.unit_price,
                "pb": comp.price_breaks_json(),
                "pkg": comp.package,
                "mount": comp.mounting_type,
                "lc": comp.lifecycle_status,
                "src": comp.source,
                "ts": comp.scraped_at,
                "raw": comp.raw_specs_json(),
            },
        )
        row = conn.execute(
            "SELECT id FROM components WHERE manufacturer_part_number=? AND source=?",
            (comp.manufacturer_part_number, comp.source),
        ).fetchone()
        comp_id = row["id"]

        conn.execute("DELETE FROM specifications WHERE component_id=?", (comp_id,))
        for name, value in comp.raw_specs.items():
            conn.execute(
                "INSERT INTO specifications (component_id, spec_name, spec_value) VALUES (?, ?, ?)",
                (comp_id, name, value),
            )
        conn.commit()
        return comp_id

    def bulk_upsert(self, components):
        count = 0
        with self.transaction():
            for comp in components:
                self.upsert_component(comp)
                count += 1
        log.info("Bulk upserted %d components", count)
        return count

    def count_by_category(self):
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT category, COUNT(*) as cnt FROM components GROUP BY category"
        ).fetchall()
        return {r["category"]: r["cnt"] for r in rows}

    def search(self, *, category=None, manufacturer=None, keyword=None,
               spec_filters=None, limit=100):
        conn = self._get_conn()
        conditions = []
        params = []

        if category:
            conditions.append("c.category = ?")
            params.append(category)
        if manufacturer:
            conditions.append("c.manufacturer LIKE ?")
            params.append(f"%{manufacturer}%")
        if keyword:
            conditions.append(
                "(c.description LIKE ? OR c.manufacturer_part_number LIKE ?)"
            )
            params.extend([f"%{keyword}%", f"%{keyword}%"])

        where = " AND ".join(conditions) if conditions else "1=1"
        sql = f"SELECT DISTINCT c.* FROM components c"

        if spec_filters:
            for i, (sname, sval) in enumerate(spec_filters.items()):
                alias = f"s{i}"
                sql += (
                    f" JOIN specifications {alias} "
                    f"ON {alias}.component_id = c.id "
                    f"AND {alias}.spec_name = ? "
                    f"AND {alias}.spec_value LIKE ? "
                )
                params = [sname, f"%{sval}%"] + params

        sql += f" WHERE {where} ORDER BY c.manufacturer_part_number LIMIT ?"
        params.append(limit)

        rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]

    def get_specifications(self, component_id):
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT spec_name, spec_value FROM specifications WHERE component_id=?",
            (component_id,),
        ).fetchall()
        return {r["spec_name"]: r["spec_value"] for r in rows}

    def total_components(self):
        conn = self._get_conn()
        row = conn.execute("SELECT COUNT(*) as cnt FROM components").fetchone()
        return row["cnt"]
'''

# ============================================================
# engine.py
# ============================================================
files[os.path.join(BASE, "engine.py")] = r'''"""Core orchestration engine."""

from __future__ import annotations

import logging
import time
import sys
import os
from typing import Dict, List, Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import CATEGORIES, all_category_slugs
from database import Database
from models import Component
from plugins.base import PluginBase

log = logging.getLogger(__name__)


class IngestionEngine:
    def __init__(self, db=None):
        self.db = db or Database()
        self._plugins = {}

    def register_plugin(self, plugin):
        self._plugins[plugin.name] = plugin
        log.info("Registered plugin: %s", plugin.name)

    def remove_plugin(self, name):
        if name in self._plugins:
            del self._plugins[name]

    def list_plugins(self):
        return list(self._plugins.keys())

    def _get_plugin(self, name=None):
        if name:
            if name not in self._plugins:
                raise RuntimeError(f"Plugin '{name}' not registered.")
            return self._plugins[name]
        if not self._plugins:
            raise RuntimeError("No plugins registered.")
        return next(iter(self._plugins.values()))

    def scrape_category(self, category_slug, *, plugin_name=None, max_pages=None, dry_run=False):
        plugin = self._get_plugin(plugin_name)

        cat = CATEGORIES.get(category_slug)
        if not cat:
            log.error("Unknown category: %s", category_slug)
            return 0

        log.info("Starting ingestion for [%s] via plugin [%s]", cat.name, plugin.name)
        start = time.time()

        components = plugin.scrape_category(category_slug, max_pages=max_pages)
        elapsed = time.time() - start

        log.info("Scraped %d components in %.1f s", len(components), elapsed)

        if dry_run:
            log.info("DRY RUN - not saving to database.")
            for c in components[:5]:
                log.info("  %s", c)
            return len(components)

        count = self.db.bulk_upsert(components)
        log.info("Stored %d components in database.", count)
        return count

    def scrape_all(self, *, plugin_name=None, max_pages=None, categories=None):
        slugs = categories or all_category_slugs()
        results = {}

        for slug in slugs:
            try:
                count = self.scrape_category(slug, plugin_name=plugin_name, max_pages=max_pages)
                results[slug] = count
            except Exception as exc:
                log.error("Failed to scrape %s: %s", slug, exc, exc_info=True)
                results[slug] = 0

        log.info("=== Ingestion complete ===")
        for slug, cnt in results.items():
            log.info("  %-20s : %6d components", slug, cnt)
        log.info("  TOTAL              : %6d", sum(results.values()))
        return results

    def status(self):
        return self.db.count_by_category()

    def search(self, **kwargs):
        return self.db.search(**kwargs)

    def close(self):
        self.db.close()
'''

# ============================================================
# main.py
# ============================================================
files[os.path.join(BASE, "main.py")] = r'''#!/usr/bin/env python3
"""
IC Database Ingestion Engine - CLI entry point.

Usage:
  python main.py scrape --all
  python main.py scrape --category power_ic --max-pages 3
  python main.py scrape --category power_ic --plugin digikey_curl
  python main.py import-csv --category power_ic
  python main.py status
  python main.py search --category power_ic --keyword LDO
  python main.py categories
"""

from __future__ import annotations

import logging
import sys
import os
import json
import argparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import CATEGORIES, all_category_slugs
from database import Database
from engine import IngestionEngine

try:
    from rich.console import Console
    from rich.table import Table as RichTable
    from rich.logging import RichHandler
    RICH = True
except ImportError:
    RICH = False


def setup_logging(verbose=False):
    level = logging.DEBUG if verbose else logging.INFO
    if RICH:
        logging.basicConfig(level=level, format="%(message)s", datefmt="[%X]",
                            handlers=[RichHandler(rich_tracebacks=True)])
    else:
        logging.basicConfig(level=level,
                            format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s")


log = logging.getLogger("ic_scraper")


def build_engine(plugin_name="digikey_playwright"):
    db = Database()
    engine = IngestionEngine(db=db)

    if plugin_name == "digikey_playwright":
        from plugins.digikey_playwright import DigiKeyPlaywrightPlugin
        plugin = DigiKeyPlaywrightPlugin()
    elif plugin_name == "digikey_curl":
        from plugins.digikey_curl import DigiKeyCurlPlugin
        plugin = DigiKeyCurlPlugin()
    elif plugin_name == "csv_import":
        from plugins.csv_import import CSVImportPlugin
        plugin = CSVImportPlugin()
    else:
        print(f"Unknown plugin: {plugin_name}")
        sys.exit(1)

    engine.register_plugin(plugin)
    return engine


def cmd_scrape(args):
    engine = build_engine(args.plugin)
    p = engine._get_plugin()
    p.setup()

    try:
        if args.all:
            results = engine.scrape_all(plugin_name=args.plugin, max_pages=args.max_pages)
        elif args.category:
            results = {}
            for cat in args.category:
                count = engine.scrape_category(cat, plugin_name=args.plugin, max_pages=args.max_pages)
                results[cat] = count
        else:
            print("Specify --all or --category <slug>. Use 'categories' to list slugs.")
            return

        print("\n=== Scrape Results ===")
        for slug, cnt in results.items():
            name = CATEGORIES[slug].name if slug in CATEGORIES else slug
            print(f"  {name:<25} {cnt:>8}")
        print(f"  {'TOTAL':<25} {sum(results.values()):>8}")

    finally:
        p.teardown()
        engine.close()


def cmd_status(args):
    db = Database()
    counts = db.count_by_category()
    total = db.total_components()

    print("\n=== IC Database Status ===")
    for slug in all_category_slugs():
        name = CATEGORIES[slug].name
        cnt = counts.get(slug, 0)
        print(f"  {name:<25} {cnt:>8}")
    print(f"  {'TOTAL':<25} {total:>8}")
    db.close()


def cmd_categories(args):
    print("\n=== IC Categories ===")
    for slug in all_category_slugs():
        cat = CATEGORIES[slug]
        print(f"  {slug:<20} {cat.name:<20} ({cat.description})")


def cmd_search(args):
    db = Database()
    spec_filters = {}
    if args.spec:
        for s in args.spec:
            if "=" in s:
                k, v = s.split("=", 1)
                spec_filters[k.strip()] = v.strip()

    results = db.search(
        category=args.category,
        keyword=args.keyword,
        manufacturer=args.manufacturer,
        spec_filters=spec_filters if spec_filters else None,
        limit=args.limit,
    )

    if not results:
        print("No results found.")
        return

    print(f"\n=== Search Results ({len(results)} found) ===")
    print(f"  {'MPN':<30} {'Manufacturer':<20} {'Category':<15} {'Stock':>8} {'Price':>10}")
    print("  " + "-" * 85)
    for r in results:
        print(f"  {r.get('manufacturer_part_number',''):<30} "
              f"{r.get('manufacturer',''):<20} "
              f"{r.get('category',''):<15} "
              f"{r.get('stock', 0):>8} "
              f"${r.get('unit_price', 0):>9.4f}")
    db.close()


def cmd_import_csv(args):
    from plugins.csv_import import CSVImportPlugin
    engine = IngestionEngine()
    plugin = CSVImportPlugin(directory=args.directory)
    plugin.setup()
    engine.register_plugin(plugin)
    count = engine.scrape_category(args.category, plugin_name="csv_import")
    print(f"Imported {count} components for {args.category}.")
    engine.close()


def cmd_compare(args):
    db = Database()
    r1 = db.search(keyword=args.mpn1, limit=1)
    r2 = db.search(keyword=args.mpn2, limit=1)

    if not r1:
        print(f"Not found: {args.mpn1}")
        return
    if not r2:
        print(f"Not found: {args.mpn2}")
        return

    c1, c2 = r1[0], r2[0]
    specs1 = db.get_specifications(c1["id"])
    specs2 = db.get_specifications(c2["id"])
    all_names = sorted(set(list(specs1.keys()) + list(specs2.keys())))

    print(f"\n{'Parameter':<40} {args.mpn1:<30} {args.mpn2:<30}")
    print("-" * 100)
    for field in ["manufacturer", "description", "category", "package", "mounting_type", "stock", "unit_price"]:
        print(f"  {field:<38} {str(c1.get(field, '')):<30} {str(c2.get(field, '')):<30}")
    print("-" * 100)
    for name in all_names:
        v1 = specs1.get(name, "-")
        v2 = specs2.get(name, "-")
        print(f"  {name:<38} {v1:<30} {v2:<30}")
    db.close()


def main():
    parser = argparse.ArgumentParser(description="IC Database Ingestion Engine")
    parser.add_argument("-v", "--verbose", action="store_true", help="Debug logging")
    sub = parser.add_subparsers(dest="command")

    # scrape
    sp = sub.add_parser("scrape", help="Scrape IC data from DigiKey")
    sp.add_argument("--all", action="store_true", help="Scrape all 11 categories")
    sp.add_argument("-c", "--category", nargs="+", help="Category slug(s)")
    sp.add_argument("-p", "--plugin", default="digikey_playwright",
                    choices=["digikey_playwright", "digikey_curl"])
    sp.add_argument("-m", "--max-pages", type=int, default=None)

    # status
    sub.add_parser("status", help="Show database statistics")

    # categories
    sub.add_parser("categories", help="List all IC categories")

    # search
    sp = sub.add_parser("search", help="Search the database")
    sp.add_argument("-c", "--category", default=None)
    sp.add_argument("-k", "--keyword", default=None)
    sp.add_argument("-m", "--manufacturer", default=None)
    sp.add_argument("-s", "--spec", nargs="*", default=[])
    sp.add_argument("-l", "--limit", type=int, default=25)

    # import-csv
    sp = sub.add_parser("import-csv", help="Import from CSV files")
    sp.add_argument("-c", "--category", required=True)
    sp.add_argument("-d", "--directory", default="imports")

    # compare
    sp = sub.add_parser("compare", help="Compare two components")
    sp.add_argument("mpn1", help="First MPN")
    sp.add_argument("mpn2", help="Second MPN")

    args = parser.parse_args()
    setup_logging(args.verbose)

    if args.command == "scrape":
        cmd_scrape(args)
    elif args.command == "status":
        cmd_status(args)
    elif args.command == "categories":
        cmd_categories(args)
    elif args.command == "search":
        cmd_search(args)
    elif args.command == "import-csv":
        cmd_import_csv(args)
    elif args.command == "compare":
        cmd_compare(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
'''

# ============================================================
# Write all files
# ============================================================
print("Creating project files...\n")
for path, content in files.items():
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    relpath = os.path.relpath(path, BASE)
    print(f"  OK  {relpath}")

# Clean pycache
import shutil
for root, dirs, fnames in os.walk(BASE):
    for d in dirs:
        if d == "__pycache__":
            p = os.path.join(root, d)
            shutil.rmtree(p, ignore_errors=True)
            print(f"  DEL {os.path.relpath(p, BASE)}")

print("\nDone! All files created successfully.")
print("\nNext steps:")
print("  1.  pip install playwright")
print("  2.  python -m playwright install msedge")
print("  3.  python main.py categories")
print("  4.  python main.py scrape --category power_ic --max-pages 1 -v")