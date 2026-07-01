"""
fix_playwright.py
Run once:  python fix_playwright.py
Overwrites the playwright plugin with a fully fixed version.
"""

import os

BASE = os.path.dirname(os.path.abspath(__file__))
path = os.path.join(BASE, "plugins", "digikey_playwright.py")

content = '''"""Playwright + Edge scraper for DigiKey - Fixed version."""

from __future__ import annotations

import csv
import logging
import os
import re
import sys
import time
from typing import Dict, List, Optional
from urllib.parse import urlencode, urljoin

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from playwright.sync_api import (
    Browser, BrowserContext, Page, Playwright,
    sync_playwright, TimeoutError as PwTimeout,
)

from plugins.base import PluginBase
from models import Component
from config import (
    CATEGORIES, DIGIKEY_BASE, DOWNLOAD_DIR,
    EDGE_CHANNEL, HEADLESS_MODE, MAX_RETRIES,
    PAGE_LOAD_TIMEOUT_MS, REQUEST_DELAY_SECONDS,
)

log = logging.getLogger(__name__)


# ================================================================
# Direct DigiKey filter page URLs for each IC category.
# These go straight to the parametric table - no discovery needed.
# Format: /en/products/filter/<path>/<digikey-category-id>
# ================================================================
CATEGORY_URLS = {
    "power_ic": [
        "/en/products/filter/integrated-circuits-ics/pmic-voltage-regulators-linear/699",
        "/en/products/filter/integrated-circuits-ics/pmic-voltage-regulators-dc-dc-switching-regulators/749",
        "/en/products/filter/integrated-circuits-ics/pmic-voltage-regulators-dc-dc-switching-controllers/750",
        "/en/products/filter/integrated-circuits-ics/pmic-gate-drivers/731",
        "/en/products/filter/integrated-circuits-ics/pmic-battery-management/726",
        "/en/products/filter/integrated-circuits-ics/pmic-led-drivers/735",
        "/en/products/filter/integrated-circuits-ics/pmic-voltage-reference/732",
        "/en/products/filter/integrated-circuits-ics/pmic-power-distribution-switches-load-drivers/752",
        "/en/products/filter/integrated-circuits-ics/pmic-supervisors/753",
        "/en/products/filter/integrated-circuits-ics/pmic-motor-drivers-controllers/740",
        "/en/products/filter/integrated-circuits-ics/pmic-ac-dc-converters-offline-switchers/751",
        "/en/products/filter/integrated-circuits-ics/pmic-hot-swap-controllers/733",
        "/en/products/filter/integrated-circuits-ics/pmic-current-regulation-management/739",
        "/en/products/filter/integrated-circuits-ics/pmic-or-controllers-ideal-diodes/737",
        "/en/products/filter/integrated-circuits-ics/pmic-full-half-bridge-drivers/730",
        "/en/products/filter/integrated-circuits-ics/pmic-power-management-specialized/755",
    ],
    "memory_ic": [
        "/en/products/filter/integrated-circuits-ics/memory/774",
    ],
    "flash_ic": [
        "/en/products/filter/integrated-circuits-ics/memory/774",
    ],
    "scalar_ic": [
        "/en/products/filter/integrated-circuits-ics/embedded-microcontrollers/685",
        "/en/products/filter/integrated-circuits-ics/embedded-microprocessors/686",
        "/en/products/filter/integrated-circuits-ics/embedded-fpgas-field-programmable-gate-array/696",
        "/en/products/filter/integrated-circuits-ics/embedded-dsps-digital-signal-processors/689",
    ],
    "audio_ic": [
        "/en/products/filter/integrated-circuits-ics/audio-special-purpose/717",
    ],
    "usb_ic": [
        "/en/products/filter/integrated-circuits-ics/interface-controllers/771",
        "/en/products/filter/integrated-circuits-ics/interface-specialized/772",
    ],
    "sensor_ic": [
        "/en/products/filter/sensors-transducers/temperature-sensors-analog-and-digital-output/518",
        "/en/products/filter/sensors-transducers/magnetic-sensors-hall-effect-digital-switch-linear/519",
        "/en/products/filter/sensors-transducers/pressure-sensors-transducers/512",
    ],
    "protection_ic": [
        "/en/products/filter/circuit-protection/tvs-diodes/144",
    ],
    "mux_logic_ic": [
        "/en/products/filter/integrated-circuits-ics/logic-buffers-drivers-receivers-transceivers/710",
        "/en/products/filter/integrated-circuits-ics/logic-gates-and-inverters/711",
        "/en/products/filter/integrated-circuits-ics/logic-signal-switches-multiplexers-decoders/716",
        "/en/products/filter/integrated-circuits-ics/logic-translators-level-shifters/712",
    ],
    "ethernet_ic": [
        "/en/products/filter/integrated-circuits-ics/interface-ethernet-ics/769",
    ],
    "opto_ic": [
        "/en/products/filter/isolators/optoisolators-transistor-photovoltaic-output/325",
        "/en/products/filter/isolators/optoisolators-triac-scr-output/326",
        "/en/products/filter/isolators/optoisolators-logic-output/327",
    ],
}


class DigiKeyPlaywrightPlugin(PluginBase):
    name = "digikey_playwright"

    def __init__(self):
        self._pw = None
        self._browser = None
        self._context = None
        self._page = None

    # ════════════════════════════════════════
    # LIFECYCLE
    # ════════════════════════════════════════
    def setup(self):
        log.info("Launching Playwright with Microsoft Edge...")
        os.makedirs(DOWNLOAD_DIR, exist_ok=True)

        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch(
            channel=EDGE_CHANNEL,
            headless=HEADLESS_MODE,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-first-run",
                "--no-default-browser-check",
            ],
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

        # Visit DigiKey home to get cookies and dismiss popups
        log.info("Navigating to DigiKey homepage...")
        self._page.goto(DIGIKEY_BASE, wait_until="domcontentloaded")
        time.sleep(3)

        # Handle region + cookie popups
        self._handle_initial_popups()
        log.info("Browser ready.")

    def teardown(self):
        log.info("Shutting down browser...")
        try:
            if self._context:
                self._context.close()
        except Exception:
            pass
        try:
            if self._browser:
                self._browser.close()
        except Exception:
            pass
        try:
            if self._pw:
                self._pw.stop()
        except Exception:
            pass

    # ════════════════════════════════════════
    # POPUP HANDLING
    # ════════════════════════════════════════
    def _handle_initial_popups(self):
        """Handle region selector, cookie consent, and any other overlays."""
        page = self._page
        time.sleep(2)

        # --- Region / Country selector ---
        region_selectors = [
            # "Ship to United States" or country confirm button
            "button:has-text('United States')",
            "a:has-text('United States')",
            "button:has-text('US')",
            # Generic confirm/OK on region modal
            "button:has-text('Confirm')",
            "button:has-text('OK')",
            "button:has-text('Go')",
            # DigiKey specific region selectors
            "[data-testid='region-confirm']",
            "[data-testid='country-confirm']",
            "button[data-testid='header-country-ok']",
            # Modal close buttons
            ".modal button.btn-primary",
            ".modal button:has-text('Continue')",
            "div[role='dialog'] button:has-text('Confirm')",
            "div[role='dialog'] button:has-text('OK')",
            "div[role='dialog'] button:has-text('Continue')",
            # Sometimes it is a dropdown + confirm
            "#header-country-picker",
        ]
        for sel in region_selectors:
            try:
                el = page.query_selector(sel)
                if el and el.is_visible():
                    log.info("Clicking region popup: %s", sel)
                    el.click()
                    time.sleep(2)
                    break
            except Exception:
                continue

        # --- Cookie consent ---
        cookie_selectors = [
            "button#onetrust-accept-btn-handler",
            "button:has-text('Accept All Cookies')",
            "button:has-text('Accept All')",
            "button:has-text('Accept Cookies')",
            "button:has-text('Accept')",
            "button:has-text('I Agree')",
            "button:has-text('Got it')",
            "#onetrust-accept-btn-handler",
        ]
        for sel in cookie_selectors:
            try:
                el = page.query_selector(sel)
                if el and el.is_visible():
                    log.info("Clicking cookie consent: %s", sel)
                    el.click()
                    time.sleep(1)
                    break
            except Exception:
                continue

        # --- Any remaining overlay close buttons ---
        close_selectors = [
            "button[aria-label='Close']",
            "button.close",
            "[data-testid='modal-close']",
            ".modal-close",
        ]
        for sel in close_selectors:
            try:
                el = page.query_selector(sel)
                if el and el.is_visible():
                    log.info("Closing overlay: %s", sel)
                    el.click()
                    time.sleep(1)
            except Exception:
                continue

        log.info("Popup handling complete.")

    def _dismiss_popups(self):
        """Quick popup dismiss for subsequent pages."""
        page = self._page
        quick_selectors = [
            "button#onetrust-accept-btn-handler",
            "button:has-text('Accept All')",
            "button:has-text('Accept')",
            "button[aria-label='Close']",
        ]
        for sel in quick_selectors:
            try:
                el = page.query_selector(sel)
                if el and el.is_visible():
                    el.click()
                    time.sleep(0.5)
            except Exception:
                continue

    # ════════════════════════════════════════
    # PAGE MANAGEMENT
    # ════════════════════════════════════════
    def _is_page_alive(self):
        try:
            if self._page and not self._page.is_closed():
                self._page.title()
                return True
        except Exception:
            pass
        return False

    def _ensure_page(self):
        """Recreate page if it crashed."""
        if not self._is_page_alive():
            log.warning("Page was closed/crashed. Creating new page...")
            try:
                self._page = self._context.new_page()
                self._page.goto(DIGIKEY_BASE, wait_until="domcontentloaded")
                time.sleep(2)
                self._handle_initial_popups()
                log.info("New page created successfully.")
            except Exception as exc:
                log.error("Failed to create new page: %s", exc)
                raise

    def _goto(self, url):
        """Navigate with retry and page recovery."""
        self._ensure_page()
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                log.info("Navigating to: %s", url)
                self._page.goto(url, wait_until="domcontentloaded", timeout=PAGE_LOAD_TIMEOUT_MS)
                time.sleep(2)
                self._dismiss_popups()
                return
            except Exception as exc:
                log.warning("Navigation attempt %d failed: %s", attempt, exc)
                if attempt < MAX_RETRIES:
                    self._ensure_page()
                    time.sleep(3 * attempt)
                else:
                    raise

    def _polite_wait(self):
        time.sleep(REQUEST_DELAY_SECONDS)

    # ════════════════════════════════════════
    # SCREENSHOT FOR DEBUGGING
    # ════════════════════════════════════════
    def _screenshot(self, name="debug"):
        """Take a screenshot for debugging."""
        try:
            os.makedirs(DOWNLOAD_DIR, exist_ok=True)
            path = os.path.join(DOWNLOAD_DIR, f"{name}.png")
            self._page.screenshot(path=path)
            log.info("Screenshot saved: %s", path)
        except Exception as exc:
            log.debug("Screenshot failed: %s", exc)

    # ════════════════════════════════════════
    # CSV DOWNLOAD (Strategy 1 - preferred)
    # ════════════════════════════════════════
    def _try_csv_download(self):
        """Try to click Download Table button and save CSV."""
        page = self._page
        download_selectors = [
            "button[data-testid='download-table']",
            "button:has-text('Download Table')",
            "a:has-text('Download Table')",
        ]

        download_btn = None
        for sel in download_selectors:
            try:
                download_btn = page.query_selector(sel)
                if download_btn and download_btn.is_visible():
                    break
                download_btn = None
            except Exception:
                download_btn = None
                continue

        if not download_btn:
            log.debug("No Download Table button found on this page.")
            return None

        try:
            with page.expect_download(timeout=60_000) as dl_info:
                download_btn.click()
            download = dl_info.value
            fname = download.suggested_filename or "digikey_table.csv"
            dest = os.path.join(DOWNLOAD_DIR, fname)
            download.save_as(dest)
            log.info("CSV downloaded: %s", dest)
            return dest
        except Exception as exc:
            log.warning("CSV download failed: %s", exc)
            return None

    def _parse_csv_file(self, csv_path, category_slug, subcategory):
        """Parse downloaded CSV into Component objects."""
        components = []
        try:
            with open(csv_path, newline="", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    comp = self._row_to_component(dict(row), category_slug, subcategory)
                    if comp:
                        components.append(comp)
        except Exception as exc:
            log.error("CSV parse error: %s", exc)
        log.info("Parsed %d components from CSV: %s", len(components), csv_path)
        return components

    # ════════════════════════════════════════
    # HTML TABLE SCRAPING (Strategy 2 - fallback)
    # ════════════════════════════════════════
    def _wait_for_table(self, timeout=15):
        """Wait for a product table to appear on the page."""
        page = self._page
        table_selectors = [
            "table",
            "[data-testid='data-table']",
            ".MuiTable-root",
            "table[role='table']",
        ]
        deadline = time.time() + timeout
        while time.time() < deadline:
            for sel in table_selectors:
                try:
                    el = page.query_selector(sel)
                    if el and el.is_visible():
                        log.debug("Table found with selector: %s", sel)
                        return True
                except Exception:
                    continue
            time.sleep(1)

        log.warning("No table found after %d seconds.", timeout)
        return False

    def _set_per_page_max(self):
        """Try to set results per page to maximum."""
        page = self._page
        per_page_selectors = [
            "select[data-testid='per-page']",
            "select.per-page-select",
            "select[aria-label*='per page']",
            "select[aria-label*='Per Page']",
            "select[aria-label*='results']",
        ]
        for sel in per_page_selectors:
            try:
                el = page.query_selector(sel)
                if el and el.is_visible():
                    for val in ["100", "250", "500", "50"]:
                        try:
                            el.select_option(value=val)
                            log.info("Set per-page to %s", val)
                            time.sleep(3)
                            page.wait_for_load_state("networkidle", timeout=15_000)
                            return True
                        except Exception:
                            continue
            except Exception:
                continue
        log.debug("Could not set per-page dropdown.")
        return False

    def _get_total_results(self):
        """Try to parse total result count from page."""
        page = self._page
        try:
            body_text = page.inner_text("body")
        except Exception:
            return 0

        # Patterns like "1 - 25 of 15,234" or "15,234 Products" or "Results: 15,234"
        patterns = [
            r"of\s+([\d,]+)\s",
            r"([\d,]+)\s+Products",
            r"([\d,]+)\s+Results",
            r"([\d,]+)\s+results",
            r"([\d,]+)\s+items",
            r"Showing.*?of\s+([\d,]+)",
        ]
        for pat in patterns:
            m = re.search(pat, body_text)
            if m:
                count = int(m.group(1).replace(",", ""))
                if count > 0:
                    return count
        return 0

    def _extract_table_headers(self):
        """Extract column headers from the product table."""
        page = self._page
        header_selectors = [
            "thead th",
            "thead td",
            "tr:first-child th",
        ]
        for sel in header_selectors:
            try:
                cells = page.query_selector_all(sel)
                if cells and len(cells) > 3:
                    headers = []
                    for c in cells:
                        text = c.inner_text().strip()
                        if text:
                            headers.append(text)
                    if len(headers) > 3:
                        log.info("Found %d table headers", len(headers))
                        return headers
            except Exception:
                continue

        log.warning("Could not extract table headers.")
        return []

    def _extract_table_rows(self, headers, category_slug, subcategory):
        """Extract component data from all visible table rows."""
        page = self._page
        components = []

        row_selectors = [
            "tbody tr[data-testid]",
            "tbody tr.MuiTableRow-root",
            "tbody tr",
        ]

        rows = []
        for sel in row_selectors:
            try:
                rows = page.query_selector_all(sel)
                if rows:
                    log.debug("Found %d rows with selector: %s", len(rows), sel)
                    break
            except Exception:
                continue

        if not rows:
            log.warning("No table rows found.")
            return components

        for row_el in rows:
            try:
                cells = row_el.query_selector_all("td")
                if len(cells) < 3:
                    continue

                raw = {}
                for i, cell in enumerate(cells):
                    try:
                        text = cell.inner_text().strip()
                    except Exception:
                        text = ""
                    if i < len(headers):
                        raw[headers[i]] = text
                    else:
                        raw[f"_col{i}"] = text

                # Extract datasheet link
                ds_selectors = [
                    "a[href*='.pdf']",
                    "a[href*='datasheet']",
                    "a[title*='Datasheet']",
                ]
                for sel in ds_selectors:
                    try:
                        a = row_el.query_selector(sel)
                        if a:
                            href = a.get_attribute("href") or ""
                            if href:
                                if href.startswith("/"):
                                    href = DIGIKEY_BASE + href
                                raw["_datasheet_url"] = href
                                break
                    except Exception:
                        continue

                # Extract product detail link
                part_selectors = [
                    "a[href*='/en/products/detail/']",
                    "a[data-testid='part-number-link']",
                ]
                for sel in part_selectors:
                    try:
                        a = row_el.query_selector(sel)
                        if a:
                            href = a.get_attribute("href") or ""
                            if href:
                                if href.startswith("/"):
                                    href = DIGIKEY_BASE + href
                                raw["_product_url"] = href
                                break
                    except Exception:
                        continue

                comp = self._row_to_component(raw, category_slug, subcategory)
                if comp:
                    components.append(comp)

            except Exception as exc:
                log.debug("Error extracting row: %s", exc)
                continue

        return components

    def _click_next_page(self):
        """Click Next page button. Returns True if successful."""
        page = self._page
        next_selectors = [
            "button[data-testid='btn-next']",
            "button[aria-label='Next']",
            "a[aria-label='Next']",
            "button:has-text('Next')",
        ]
        for sel in next_selectors:
            try:
                btn = page.query_selector(sel)
                if not btn:
                    continue
                if btn.is_disabled():
                    log.debug("Next button is disabled.")
                    return False
                aria = btn.get_attribute("aria-disabled")
                if aria == "true":
                    return False
                cls = btn.get_attribute("class") or ""
                if "disabled" in cls.lower():
                    return False

                btn.scroll_into_view_if_needed()
                time.sleep(0.5)
                btn.click()
                log.info("Clicked Next page.")
                time.sleep(3)
                try:
                    page.wait_for_load_state("networkidle", timeout=15_000)
                except Exception:
                    pass
                self._polite_wait()
                return True
            except Exception as exc:
                log.debug("Next page click failed with %s: %s", sel, exc)
                continue

        log.debug("No working Next button found.")
        return False

    # ════════════════════════════════════════
    # ROW -> COMPONENT CONVERSION
    # ════════════════════════════════════════
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
        "stock": [
            "Quantity Available", "Stock", "Qty Available",
            "In Stock", "Qty",
        ],
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
        """Convert a {header: value} dict into a Component object."""
        def _find(field_keys):
            for k in field_keys:
                if k in raw and raw[k]:
                    return raw[k].strip()
            return ""

        mpn = _find(self._FIELD_MAP["manufacturer_part_number"])
        if not mpn:
            return None

        # Parse stock
        stock = 0
        stock_str = _find(self._FIELD_MAP["stock"])
        if stock_str:
            stock_clean = re.sub(r"[^\\d]", "", stock_str)
            stock = int(stock_clean) if stock_clean else 0

        # Parse price
        price = 0.0
        price_str = _find(self._FIELD_MAP["unit_price"])
        if price_str:
            price_clean = re.sub(r"[^\\d.]", "", price_str)
            try:
                price = float(price_clean)
            except ValueError:
                pass

        # All other columns become specs
        mapped_keys = set()
        for keys in self._FIELD_MAP.values():
            mapped_keys.update(keys)
        specs = {}
        for k, v in raw.items():
            if k not in mapped_keys and not k.startswith("_") and v:
                specs[k] = v

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

    # ════════════════════════════════════════
    # SCRAPE A SINGLE CATEGORY PAGE
    # ════════════════════════════════════════
    def _scrape_single_url(self, url, category_slug, subcategory, max_pages=None):
        """
        Scrape all products from one DigiKey filter page.
        Flow: navigate -> try CSV download -> fall back to HTML table -> paginate
        """
        full_url = url if url.startswith("http") else DIGIKEY_BASE + url
        self._goto(full_url)
        self._polite_wait()

        # Take a debug screenshot
        slug = url.rstrip("/").split("/")[-2] if "/" in url else "page"
        self._screenshot(f"page_{slug}")

        # ── Strategy 1: CSV Download ──
        csv_path = self._try_csv_download()
        if csv_path:
            return self._parse_csv_file(csv_path, category_slug, subcategory)

        # ── Strategy 2: HTML Table Scraping ──
        log.info("Falling back to HTML table scraping...")

        # Wait for table to appear
        if not self._wait_for_table(timeout=15):
            log.warning("No table found on page: %s", full_url)
            self._screenshot(f"no_table_{slug}")
            return []

        # Try to maximize results per page
        self._set_per_page_max()
        self._polite_wait()

        total = self._get_total_results()
        log.info("Total results on this page: %d", total)

        # Extract headers once
        headers = self._extract_table_headers()
        if not headers:
            log.warning("No headers found. Taking screenshot for debugging.")
            self._screenshot(f"no_headers_{slug}")
            return []

        log.info("Headers: %s", headers[:8])  # show first 8

        # Paginate and collect
        all_components = []
        page_num = 0

        while True:
            page_num += 1
            if max_pages and page_num > max_pages:
                log.info("Reached max_pages=%d, stopping pagination.", max_pages)
                break

            log.info("  Scraping page %d (collected %d so far)...", page_num, len(all_components))

            comps = self._extract_table_rows(headers, category_slug, subcategory)
            log.info("  Got %d components from page %d", len(comps), page_num)
            all_components.extend(comps)

            if not comps:
                log.info("  No components found on page %d, stopping.", page_num)
                break

            # Try to go to next page
            if not self._click_next_page():
                log.info("  No more pages available.")
                break

            # Re-check page is alive after navigation
            if not self._is_page_alive():
                log.warning("  Page crashed during pagination.")
                break

        log.info("Total from %s: %d components", subcategory, len(all_components))
        return all_components

    # ════════════════════════════════════════
    # MAIN ENTRY POINT
    # ════════════════════════════════════════
    def scrape_category(self, category_slug, *, max_pages=None):
        """
        Scrape ALL components for an IC category.
        Uses direct filter URLs, not search.
        """
        cat = CATEGORIES.get(category_slug)
        if not cat:
            log.error("Unknown category: %s", category_slug)
            return []

        log.info("=" * 60)
        log.info("SCRAPING CATEGORY: %s", cat.name)
        log.info("=" * 60)

        # Get the known URLs for this category
        urls = CATEGORY_URLS.get(category_slug, [])

        if not urls:
            # Fallback to search keywords
            log.warning("No known URLs for %s. Falling back to keyword search.", category_slug)
            for kw in cat.search_keywords[:3]:
                urls.append(f"/en/products/result?keywords={kw.replace(' ', '+')}")

        log.info("Will scrape %d subcategory pages for %s", len(urls), cat.name)

        all_components = []

        for i, url in enumerate(urls):
            # Extract subcategory name from URL
            parts = url.rstrip("/").split("/")
            # e.g. ".../pmic-voltage-regulators-linear/699" -> "pmic-voltage-regulators-linear"
            subcategory = parts[-2] if len(parts) >= 2 else f"subcat_{i}"

            log.info("")
            log.info("--- Subcategory %d/%d: %s ---", i + 1, len(urls), subcategory)

            try:
                self._ensure_page()
                comps = self._scrape_single_url(url, category_slug, subcategory, max_pages=max_pages)
                all_components.extend(comps)
                log.info("--- Got %d components from %s ---", len(comps), subcategory)
            except Exception as exc:
                log.error("Failed to scrape %s: %s", subcategory, exc, exc_info=True)
                self._screenshot(f"error_{subcategory}")
                # Try to recover for next URL
                try:
                    self._ensure_page()
                except Exception:
                    pass
                continue

        # Deduplicate by MPN
        seen = set()
        unique = []
        for c in all_components:
            if c.manufacturer_part_number not in seen:
                seen.add(c.manufacturer_part_number)
                unique.append(c)

        log.info("")
        log.info("=" * 60)
        log.info("%s COMPLETE: %d total, %d unique components", cat.name, len(all_components), len(unique))
        log.info("=" * 60)
        return unique
'''

with open(path, "w", encoding="utf-8") as f:
    f.write(content)

print(f"Fixed: {path}")
print()
print("Now run:")
print("  python main.py -v scrape --category power_ic --max-pages 1")