"""
fix2.py - Fixes header-cell alignment, removes screenshots, skips slow CSV attempt.
Run:  python fix2.py
Then: python main.py -v scrape --category power_ic --max-pages 1
"""

import os

BASE = os.path.dirname(os.path.abspath(__file__))
path = os.path.join(BASE, "plugins", "digikey_playwright.py")

content = r'''"""Playwright + Edge scraper for DigiKey - v3."""

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
    CATEGORIES, DIGIKEY_BASE, DOWNLOAD_DIR,
    EDGE_CHANNEL, HEADLESS_MODE, MAX_RETRIES,
    PAGE_LOAD_TIMEOUT_MS, REQUEST_DELAY_SECONDS,
)

log = logging.getLogger(__name__)


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

    # ═══════════════════════════════════
    # LIFECYCLE
    # ═══════════════════════════════════
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

        log.info("Navigating to DigiKey homepage...")
        self._page.goto(DIGIKEY_BASE, wait_until="domcontentloaded")
        time.sleep(3)
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

    # ═══════════════════════════════════
    # POPUP HANDLING
    # ═══════════════════════════════════
    def _handle_initial_popups(self):
        """Handle region selector, cookie consent, and overlays."""
        page = self._page
        time.sleep(2)

        # Region / Country popup
        region_selectors = [
            "button:has-text('United States')",
            "a:has-text('United States')",
            "button:has-text('Confirm')",
            "button:has-text('OK')",
            "button:has-text('Go')",
            "[data-testid='region-confirm']",
            "[data-testid='country-confirm']",
            "button[data-testid='header-country-ok']",
            ".modal button.btn-primary",
            ".modal button:has-text('Continue')",
            "div[role='dialog'] button:has-text('Confirm')",
            "div[role='dialog'] button:has-text('OK')",
            "div[role='dialog'] button:has-text('Continue')",
        ]
        for sel in region_selectors:
            try:
                el = page.query_selector(sel)
                if el and el.is_visible():
                    log.info("Dismissing region popup: %s", sel)
                    el.click()
                    time.sleep(2)
                    break
            except Exception:
                continue

        # Cookie consent
        cookie_selectors = [
            "button#onetrust-accept-btn-handler",
            "button:has-text('Accept All Cookies')",
            "button:has-text('Accept All')",
            "button:has-text('Accept Cookies')",
            "button:has-text('Accept')",
            "button:has-text('I Agree')",
            "button:has-text('Got it')",
        ]
        for sel in cookie_selectors:
            try:
                el = page.query_selector(sel)
                if el and el.is_visible():
                    log.info("Dismissing cookie banner: %s", sel)
                    el.click()
                    time.sleep(1)
                    break
            except Exception:
                continue

        # Close any remaining modals
        close_selectors = [
            "button[aria-label='Close']",
            "button.close",
            "[data-testid='modal-close']",
        ]
        for sel in close_selectors:
            try:
                el = page.query_selector(sel)
                if el and el.is_visible():
                    el.click()
                    time.sleep(1)
            except Exception:
                continue

        log.info("Popup handling complete.")

    def _dismiss_popups_quick(self):
        """Quick popup check for subsequent pages."""
        page = self._page
        for sel in ["button#onetrust-accept-btn-handler",
                     "button:has-text('Accept')",
                     "button[aria-label='Close']"]:
            try:
                el = page.query_selector(sel)
                if el and el.is_visible():
                    el.click()
                    time.sleep(0.5)
            except Exception:
                continue

    # ═══════════════════════════════════
    # PAGE MANAGEMENT
    # ═══════════════════════════════════
    def _is_page_alive(self):
        try:
            if self._page and not self._page.is_closed():
                self._page.title()
                return True
        except Exception:
            pass
        return False

    def _ensure_page(self):
        if not self._is_page_alive():
            log.warning("Page crashed. Creating new page...")
            try:
                self._page = self._context.new_page()
                self._page.goto(DIGIKEY_BASE, wait_until="domcontentloaded")
                time.sleep(2)
                self._handle_initial_popups()
                log.info("New page ready.")
            except Exception as exc:
                log.error("Failed to recreate page: %s", exc)
                raise

    def _goto(self, url):
        self._ensure_page()
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                log.info("Navigating to: %s", url)
                self._page.goto(url, wait_until="domcontentloaded", timeout=PAGE_LOAD_TIMEOUT_MS)
                time.sleep(3)
                self._dismiss_popups_quick()
                return
            except Exception as exc:
                log.warning("Nav attempt %d failed: %s", attempt, exc)
                if attempt < MAX_RETRIES:
                    self._ensure_page()
                    time.sleep(3 * attempt)
                else:
                    raise

    # ═══════════════════════════════════
    # TABLE EXTRACTION (the core fix)
    # ═══════════════════════════════════
    def _wait_for_table(self, timeout=15):
        page = self._page
        deadline = time.time() + timeout
        while time.time() < deadline:
            for sel in ["table", "[data-testid='data-table']", ".MuiTable-root"]:
                try:
                    el = page.query_selector(sel)
                    if el and el.is_visible():
                        return True
                except Exception:
                    continue
            time.sleep(1)
        return False

    def _extract_headers_raw(self):
        """
        Get ALL header texts including empty ones.
        This preserves the 1:1 index mapping with td cells.
        """
        page = self._page
        for sel in ["thead th", "thead td"]:
            try:
                cells = page.query_selector_all(sel)
                if cells and len(cells) > 3:
                    headers = []
                    for c in cells:
                        try:
                            text = c.inner_text().strip()
                        except Exception:
                            text = ""
                        headers.append(text)
                    return headers
            except Exception:
                continue
        return []

    def _debug_first_row(self):
        """Print the first row's cell contents to understand the layout."""
        page = self._page
        rows = page.query_selector_all("tbody tr")
        if not rows:
            log.warning("DEBUG: No tbody tr found at all.")
            return

        first_row = rows[0]
        cells = first_row.query_selector_all("td")
        log.info("DEBUG: First row has %d cells:", len(cells))
        for i, cell in enumerate(cells):
            try:
                text = cell.inner_text().strip()[:60]
            except Exception:
                text = "(error)"
            log.info("  cell[%d] = %r", i, text)

    def _extract_rows_smart(self, category_slug, subcategory):
        """
        Extract rows by reading BOTH headers and cells with their
        actual indices preserved, then building key-value pairs.
        
        The trick: DON'T skip empty headers. Map header[i] -> cell[i].
        Then scan for known field names in the resulting dict.
        """
        page = self._page
        components = []

        # Get raw headers (including empty ones for alignment)
        raw_headers = self._extract_headers_raw()
        if not raw_headers:
            log.warning("No headers found.")
            return components

        log.info("Raw headers (%d total): %s", len(raw_headers), raw_headers[:10])

        # Debug: show first row
        self._debug_first_row()

        # Get all rows
        rows = page.query_selector_all("tbody tr")
        if not rows:
            log.warning("No tbody rows found.")
            return components

        log.info("Found %d rows to process.", len(rows))

        for row_idx, row_el in enumerate(rows):
            try:
                cells = row_el.query_selector_all("td")
                if len(cells) < 3:
                    continue

                # Build raw dict: map header[i] -> cell[i] text
                raw = {}
                for i, cell in enumerate(cells):
                    try:
                        text = cell.inner_text().strip()
                    except Exception:
                        text = ""

                    if i < len(raw_headers) and raw_headers[i]:
                        raw[raw_headers[i]] = text
                    else:
                        raw[f"_col{i}"] = text

                    # Also check for links in this cell
                    try:
                        links = cell.query_selector_all("a[href]")
                        for a in links:
                            href = a.get_attribute("href") or ""
                            if not href:
                                continue
                            if href.startswith("/"):
                                href = DIGIKEY_BASE + href
                            if ".pdf" in href.lower() or "datasheet" in href.lower():
                                raw["_datasheet_url"] = href
                            elif "/en/products/detail/" in href:
                                raw["_product_url"] = href
                    except Exception:
                        pass

                # Try to find MPN from raw dict
                comp = self._row_to_component(raw, category_slug, subcategory)
                if comp:
                    components.append(comp)
                    if row_idx < 3:
                        log.info("  Sample: %s | %s | %s",
                                 comp.manufacturer_part_number,
                                 comp.manufacturer,
                                 comp.description[:50] if comp.description else "")

            except Exception as exc:
                log.debug("Error on row %d: %s", row_idx, exc)
                continue

        return components

    def _get_total_results(self):
        page = self._page
        try:
            body_text = page.inner_text("body")
        except Exception:
            return 0

        patterns = [
            r"of\s+([\d,]+)\s",
            r"([\d,]+)\s+Products",
            r"([\d,]+)\s+Results",
            r"([\d,]+)\s+results",
            r"Showing.*?of\s+([\d,]+)",
        ]
        for pat in patterns:
            m = re.search(pat, body_text)
            if m:
                count = int(m.group(1).replace(",", ""))
                if count > 0:
                    return count
        return 0

    def _set_per_page_max(self):
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
                            return True
                        except Exception:
                            continue
            except Exception:
                continue
        log.debug("Could not set per-page dropdown.")
        return False

    def _click_next_page(self):
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
                time.sleep(REQUEST_DELAY_SECONDS)
                return True
            except Exception as exc:
                log.debug("Next click failed (%s): %s", sel, exc)
                continue
        return False

    # ═══════════════════════════════════
    # ROW -> COMPONENT
    # ═══════════════════════════════════
    _MPN_KEYS = [
        "Mfr Part #", "Manufacturer Part Number", "MPN",
        "Manufacturer Part #", "Part Number", "Mfr Part No",
        "Mfr Part#",
    ]
    _MFR_KEYS = ["Manufacturer", "Mfr", "Vendor"]
    _DESC_KEYS = ["Description", "Product Description", "Desc"]
    _DK_KEYS = ["Digi-Key Part Number", "DK Part #", "DigiKey Part #", "Digi-Key Part #"]
    _STOCK_KEYS = ["Quantity Available", "Stock", "Qty Available", "In Stock", "Qty"]
    _PRICE_KEYS = ["Unit Price", "Price", "Unit Price (USD)", "Price (USD)"]
    _PKG_KEYS = ["Package / Case", "Package", "Case", "Supplier Device Package"]
    _MOUNT_KEYS = ["Mounting Type", "Mount Type"]
    _STATUS_KEYS = ["Part Status", "Lifecycle", "Status", "Product Status"]

    def _find_value(self, raw, keys):
        for k in keys:
            if k in raw and raw[k]:
                return raw[k].strip()
        return ""

    def _row_to_component(self, raw, category_slug, subcategory):
        mpn = self._find_value(raw, self._MPN_KEYS)
        if not mpn:
            return None

        # Parse stock
        stock = 0
        stock_str = self._find_value(raw, self._STOCK_KEYS)
        if stock_str:
            stock_clean = re.sub(r"[^\d]", "", stock_str)
            stock = int(stock_clean) if stock_clean else 0

        # Parse price
        price = 0.0
        price_str = self._find_value(raw, self._PRICE_KEYS)
        if price_str:
            price_clean = re.sub(r"[^\d.]", "", price_str)
            try:
                price = float(price_clean)
            except ValueError:
                pass

        # Everything else becomes specs
        all_known_keys = set()
        for key_list in [self._MPN_KEYS, self._MFR_KEYS, self._DESC_KEYS,
                         self._DK_KEYS, self._STOCK_KEYS, self._PRICE_KEYS,
                         self._PKG_KEYS, self._MOUNT_KEYS, self._STATUS_KEYS]:
            all_known_keys.update(key_list)

        specs = {}
        for k, v in raw.items():
            if k not in all_known_keys and not k.startswith("_") and v:
                specs[k] = v

        return Component(
            manufacturer_part_number=mpn,
            manufacturer=self._find_value(raw, self._MFR_KEYS),
            digikey_part_number=self._find_value(raw, self._DK_KEYS),
            description=self._find_value(raw, self._DESC_KEYS),
            category=category_slug,
            subcategory=subcategory,
            datasheet_url=raw.get("_datasheet_url", ""),
            product_url=raw.get("_product_url", ""),
            stock=stock,
            unit_price=price,
            package=self._find_value(raw, self._PKG_KEYS),
            mounting_type=self._find_value(raw, self._MOUNT_KEYS),
            lifecycle_status=self._find_value(raw, self._STATUS_KEYS),
            source="digikey",
            raw_specs=specs,
        )

    # ═══════════════════════════════════
    # SCRAPE ONE URL
    # ═══════════════════════════════════
    def _scrape_single_url(self, url, category_slug, subcategory, max_pages=None):
        full_url = url if url.startswith("http") else DIGIKEY_BASE + url
        self._goto(full_url)
        time.sleep(REQUEST_DELAY_SECONDS)

        # Wait for table
        if not self._wait_for_table(timeout=15):
            log.warning("No table found on: %s", full_url)
            return []

        # Try to increase results per page
        self._set_per_page_max()
        time.sleep(2)

        total = self._get_total_results()
        log.info("Total results: %d", total)

        # Paginate and collect
        all_components = []
        page_num = 0

        while True:
            page_num += 1
            if max_pages and page_num > max_pages:
                log.info("Reached max_pages=%d, stopping.", max_pages)
                break

            log.info("  Page %d (collected %d so far)...", page_num, len(all_components))
            comps = self._extract_rows_smart(category_slug, subcategory)
            log.info("  Got %d components from page %d", len(comps), page_num)
            all_components.extend(comps)

            if not comps:
                log.info("  No components on page %d, stopping.", page_num)
                break

            if not self._click_next_page():
                log.info("  No more pages.")
                break

            if not self._is_page_alive():
                log.warning("  Page crashed during pagination.")
                break

        log.info("Total from %s: %d components", subcategory, len(all_components))
        return all_components

    # ═══════════════════════════════════
    # MAIN ENTRY POINT
    # ═══════════════════════════════════
    def scrape_category(self, category_slug, *, max_pages=None):
        cat = CATEGORIES.get(category_slug)
        if not cat:
            log.error("Unknown category: %s", category_slug)
            return []

        log.info("=" * 60)
        log.info("SCRAPING CATEGORY: %s", cat.name)
        log.info("=" * 60)

        urls = CATEGORY_URLS.get(category_slug, [])
        if not urls:
            log.warning("No known URLs for %s, using keyword search.", category_slug)
            for kw in cat.search_keywords[:3]:
                urls.append("/en/products/result?keywords=" + kw.replace(" ", "+"))

        log.info("Will scrape %d subcategory pages.", len(urls))

        all_components = []
        for i, url in enumerate(urls):
            parts = url.rstrip("/").split("/")
            subcategory = parts[-2] if len(parts) >= 2 else f"subcat_{i}"

            log.info("")
            log.info("--- [%d/%d] %s ---", i + 1, len(urls), subcategory)

            try:
                self._ensure_page()
                comps = self._scrape_single_url(url, category_slug, subcategory, max_pages=max_pages)
                all_components.extend(comps)
                log.info("--- Got %d from %s ---", len(comps), subcategory)
            except Exception as exc:
                log.error("Failed %s: %s", subcategory, exc, exc_info=True)
                try:
                    self._ensure_page()
                except Exception:
                    pass
                continue

        # Deduplicate
        seen = set()
        unique = []
        for c in all_components:
            if c.manufacturer_part_number not in seen:
                seen.add(c.manufacturer_part_number)
                unique.append(c)

        log.info("")
        log.info("=" * 60)
        log.info("%s COMPLETE: %d total, %d unique", cat.name, len(all_components), len(unique))
        log.info("=" * 60)
        return unique
'''

with open(path, "w", encoding="utf-8") as f:
    f.write(content)

print(f"Fixed: {path}")
print()
print("Now run:")
print("  python main.py -v scrape --category power_ic --max-pages 1")