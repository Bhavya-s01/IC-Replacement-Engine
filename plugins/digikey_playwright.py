"""Playwright + Edge scraper for DigiKey - v5 pagination fixed."""

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
        page = self._page
        time.sleep(2)

        for sel in [
            "button:has-text('United States')",
            "a:has-text('United States')",
            "button:has-text('Confirm')",
            "button:has-text('OK')",
            "button:has-text('Go')",
            "[data-testid='region-confirm']",
            "button[data-testid='header-country-ok']",
            ".modal button.btn-primary",
            "div[role='dialog'] button:has-text('OK')",
            "div[role='dialog'] button:has-text('Continue')",
        ]:
            try:
                el = page.query_selector(sel)
                if el and el.is_visible():
                    log.info("Dismissing region popup: %s", sel)
                    el.click()
                    time.sleep(2)
                    break
            except Exception:
                continue

        for sel in [
            "button#onetrust-accept-btn-handler",
            "button:has-text('Accept All Cookies')",
            "button:has-text('Accept All')",
            "button:has-text('Accept')",
            "button:has-text('I Agree')",
        ]:
            try:
                el = page.query_selector(sel)
                if el and el.is_visible():
                    log.info("Dismissing cookie banner: %s", sel)
                    el.click()
                    time.sleep(1)
                    break
            except Exception:
                continue

        for sel in ["button[aria-label='Close']", "button.close"]:
            try:
                el = page.query_selector(sel)
                if el and el.is_visible():
                    el.click()
                    time.sleep(1)
            except Exception:
                continue

        log.info("Popup handling complete.")

    def _dismiss_popups_quick(self):
        """Aggressively dismiss any popup that appears - region, cookie, modal."""
        page = self._page

        # Region / Location popups (these keep coming back)
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
            "div[role='dialog'] button:has-text('OK')",
            "div[role='dialog'] button:has-text('Confirm')",
            "div[role='dialog'] button:has-text('Continue')",
            "div[role='dialog'] button:has-text('Go')",
            # Location / shipping popup
            "button:has-text('Submit')",
            "button:has-text('Save')",
            "button:has-text('Done')",
        ]
        for sel in region_selectors:
            try:
                el = page.query_selector(sel)
                if el and el.is_visible():
                    log.info("Dismissing popup: %s", sel)
                    el.click()
                    time.sleep(1)
                    break
            except Exception:
                continue

        # Cookie consent
        for sel in ["button#onetrust-accept-btn-handler",
                     "button:has-text('Accept All')",
                     "button:has-text('Accept')"]:
            try:
                el = page.query_selector(sel)
                if el and el.is_visible():
                    el.click()
                    time.sleep(0.5)
                    break
            except Exception:
                continue

        # Close any modal/overlay
        for sel in ["button[aria-label='Close']",
                     "button.close",
                     "[data-testid='modal-close']",
                     "button[aria-label='close']",
                     ".modal-close"]:
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
            log.warning("Page crashed. Recreating...")
            try:
                self._page = self._context.new_page()
                self._page.goto(DIGIKEY_BASE, wait_until="domcontentloaded")
                time.sleep(2)
                self._handle_initial_popups()
            except Exception as exc:
                log.error("Failed to recreate page: %s", exc)
                raise

    def _goto(self, url):
        self._ensure_page()
        full_url = url if url.startswith("http") else DIGIKEY_BASE + url
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                self._page.goto(full_url, wait_until="domcontentloaded", timeout=PAGE_LOAD_TIMEOUT_MS)
                time.sleep(3)
                self._dismiss_popups_quick()
                time.sleep(1)
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
    # TABLE DETECTION
    # ═══════════════════════════════════
    def _wait_for_table(self, timeout=15):
        page = self._page
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                el = page.query_selector("table")
                if el and el.is_visible():
                    return True
            except Exception:
                pass
            time.sleep(1)
        return False

    # ═══════════════════════════════════
    # PAGINATION (FIXED - using actual DigiKey selectors)
    #
    # DigiKey uses:
    #   data-testid="btn-page-1"  (page 1, disabled when current)
    #   data-testid="btn-page-2"  (page 2)
    #   data-testid="btn-next-page"  (next arrow)
    #   data-testid="btn-last-page"  (last page arrow)
    #   Container: [data-testid*="pagination"]
    #
    # No per-page dropdown exists. Fixed at 25 per page.
    # ═══════════════════════════════════
    def _get_total_results(self):
        page = self._page
        try:
            body_text = page.inner_text("body")
        except Exception:
            return 0

        for pat in [r"of\s+([\d,]+)\s", r"([\d,]+)\s+Products",
                    r"([\d,]+)\s+Results", r"Showing.*?of\s+([\d,]+)"]:
            m = re.search(pat, body_text)
            if m:
                count = int(m.group(1).replace(",", ""))
                if count > 0:
                    return count
        return 0

    def _get_current_page_number(self):
        """Find which page button is currently disabled (= current page)."""
        page = self._page
        for i in range(1, 200):
            testid = "btn-page-{}".format(i)
            try:
                btn = page.query_selector("[data-testid='{}']".format(testid))
                if btn and btn.is_disabled():
                    return i
            except Exception:
                break
        return 1

    def _click_next_page(self):
        """Click the Next Page button using DigiKey's actual data-testid."""
        page = self._page

        # Primary: use the exact next-page button
        try:
            btn = page.query_selector("[data-testid='btn-next-page']")
            if btn and btn.is_visible():
                if btn.is_disabled():
                    log.info("Next page button is disabled - on last page.")
                    return False

                # Check Mui disabled class
                cls = btn.get_attribute("class") or ""
                if "Mui-disabled" in cls:
                    log.info("Next page button has Mui-disabled class - on last page.")
                    return False

                btn.scroll_into_view_if_needed()
                time.sleep(0.5)
                btn.click()
                log.info("Clicked next page button.")
                time.sleep(3)

                # Wait for page to load
                try:
                    page.wait_for_load_state("networkidle", timeout=15_000)
                except Exception:
                    pass

                # Dismiss any popups that appeared after navigation
                time.sleep(1)
                self._dismiss_popups_quick()
                time.sleep(REQUEST_DELAY_SECONDS)
                return True
        except Exception as exc:
            log.debug("btn-next-page click failed: %s", exc)

        # Fallback: click the next numbered page button
        current = self._get_current_page_number()
        next_num = current + 1
        try:
            next_btn = page.query_selector("[data-testid='btn-page-{}']".format(next_num))
            if next_btn and next_btn.is_visible() and not next_btn.is_disabled():
                next_btn.scroll_into_view_if_needed()
                time.sleep(0.5)
                next_btn.click()
                log.info("Clicked page %d button.", next_num)
                time.sleep(3)
                try:
                    page.wait_for_load_state("networkidle", timeout=15_000)
                except Exception:
                    pass
                time.sleep(1)
                self._dismiss_popups_quick()
                time.sleep(REQUEST_DELAY_SECONDS)
                return True
        except Exception as exc:
            log.debug("btn-page-%d click failed: %s", next_num, exc)

        log.info("No more pages available.")
        return False

    # ═══════════════════════════════════
    # TABLE EXTRACTION
    # ═══════════════════════════════════
    def _extract_headers_raw(self):
        """Get ALL header texts including empty ones for alignment."""
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

    def _extract_rows(self, headers, category_slug, subcategory):
        """
        Extract components from table rows.
        
        DigiKey's "Mfr Part #" cell contains 3 lines:
            Line 1: MPN
            Line 2: Description
            Line 3: Manufacturer
        """
        page = self._page
        components = []

        rows = page.query_selector_all("tbody tr")
        if not rows:
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

                    header_name = headers[i] if i < len(headers) else "_col{}".format(i)
                    raw[header_name] = text

                    # Extract links
                    try:
                        for a in cell.query_selector_all("a[href]"):
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

                # Parse multi-line "Mfr Part #" cell
                mpn_cell = raw.get("Mfr Part #", "")
                if mpn_cell:
                    lines = [l.strip() for l in mpn_cell.split("\n") if l.strip()]
                    if len(lines) >= 1:
                        raw["_parsed_mpn"] = lines[0]
                    if len(lines) >= 2:
                        raw["_parsed_description"] = lines[1]
                    if len(lines) >= 3:
                        raw["_parsed_manufacturer"] = lines[2]

                # Parse multi-line stock
                qty_cell = raw.get("Quantity Available", "")
                if qty_cell:
                    lines = [l.strip() for l in qty_cell.split("\n") if l.strip()]
                    if lines:
                        raw["_parsed_stock"] = lines[0]

                # Parse price
                price_cell = raw.get("Price", "")
                if price_cell:
                    price_match = re.search(r"\$([\d.]+)", price_cell)
                    if price_match:
                        raw["_parsed_price"] = price_match.group(1)

                comp = self._row_to_component(raw, category_slug, subcategory)
                if comp:
                    components.append(comp)

            except Exception as exc:
                log.debug("Row extraction error: %s", exc)
                continue

        return components

    # ═══════════════════════════════════
    # ROW -> COMPONENT
    # ═══════════════════════════════════
    def _row_to_component(self, raw, category_slug, subcategory):
        mpn = (raw.get("_parsed_mpn") or
               raw.get("Manufacturer Part Number") or
               raw.get("MPN") or "").strip()
        if not mpn:
            return None

        manufacturer = (raw.get("_parsed_manufacturer") or
                       raw.get("Manufacturer") or "").strip()

        description = (raw.get("_parsed_description") or
                      raw.get("Description") or "").strip()

        # Stock
        stock = 0
        stock_str = raw.get("_parsed_stock") or raw.get("Quantity Available") or ""
        if stock_str:
            stock_clean = re.sub(r"[^\d]", "", stock_str)
            stock = int(stock_clean) if stock_clean else 0

        # Price
        price = 0.0
        price_str = raw.get("_parsed_price") or raw.get("Unit Price") or raw.get("Price") or ""
        if price_str:
            price_clean = re.sub(r"[^\d.]", "", price_str)
            try:
                price = float(price_clean)
            except ValueError:
                pass

        # Package - skip if it says Tape/Reel/Tube (that's packaging, not IC package)
        package = raw.get("Package / Case") or raw.get("Package") or ""
        if package and any(kw in package.lower() for kw in ["tape", "reel", "tube", "digi-reel", "bulk"]):
            package = ""

        # Mounting
        mounting = ""
        for k in ["Mounting Type", "Mount Type"]:
            if k in raw and raw[k]:
                mounting = raw[k]
                break

        # Lifecycle
        lifecycle = ""
        for k in ["Product Status", "Part Status", "Lifecycle", "Status"]:
            if k in raw and raw[k]:
                lifecycle = raw[k]
                break

        # Everything else -> specs
        skip_keys = {
            "", "Mfr Part #", "Manufacturer Part Number", "MPN",
            "Manufacturer", "Mfr", "Vendor",
            "Description", "Product Description",
            "Digi-Key Part Number", "DK Part #",
            "Quantity Available", "Stock", "In Stock",
            "Unit Price", "Price",
            "Package / Case", "Package", "Supplier Device Package",
            "Mounting Type", "Mount Type",
            "Product Status", "Part Status", "Lifecycle", "Status",
            "Tariff Status",
            "_parsed_mpn", "_parsed_description", "_parsed_manufacturer",
            "_parsed_stock", "_parsed_price",
            "_datasheet_url", "_product_url",
        }

        specs = {}
        for k, v in raw.items():
            if k not in skip_keys and not k.startswith("_col") and v and v != "-":
                specs[k] = v

        return Component(
            manufacturer_part_number=mpn,
            manufacturer=manufacturer,
            digikey_part_number="",
            description=description,
            category=category_slug,
            subcategory=subcategory,
            datasheet_url=raw.get("_datasheet_url", ""),
            product_url=raw.get("_product_url", ""),
            stock=stock,
            unit_price=price,
            package=package,
            mounting_type=mounting,
            lifecycle_status=lifecycle,
            source="digikey",
            raw_specs=specs,
        )

    # ═══════════════════════════════════
    # SCRAPE ONE URL
    # ═══════════════════════════════════
    def _scrape_single_url(self, url, category_slug, subcategory, max_pages=None):
        self._goto(url)
        time.sleep(REQUEST_DELAY_SECONDS)

        if not self._wait_for_table(timeout=15):
            log.warning("No table found on: %s", url)
            return []

        total = self._get_total_results()
        log.info("Total results: %d (25 per page, ~%d pages)", total, (total // 25) + 1 if total else 0)

        # Get headers
        headers = self._extract_headers_raw()
        if not headers:
            log.warning("No headers found.")
            return []

        useful = [h for h in headers if h]
        log.info("Columns: %s", useful[:6])

        # Paginate and collect
        all_components = []
        page_num = 0

        while True:
            page_num += 1
            if max_pages and page_num > max_pages:
                log.info("Reached max_pages=%d, stopping.", max_pages)
                break

            current = self._get_current_page_number()
            log.info("  Page %d (DigiKey page %d) - collected %d so far...",
                     page_num, current, len(all_components))

            comps = self._extract_rows(headers, category_slug, subcategory)
            log.info("  Extracted %d components from this page.", len(comps))

            if comps and page_num == 1:
                for c in comps[:2]:
                    log.info("    Sample: %s | %s | stock=%d",
                             c.manufacturer_part_number,
                             c.manufacturer,
                             c.stock)

            all_components.extend(comps)

            if not comps:
                log.info("  Empty page, stopping.")
                break

            if total > 0 and len(all_components) >= total:
                log.info("  Collected all %d results.", total)
                break

            # NEXT PAGE
            if not self._click_next_page():
                break

            if not self._is_page_alive():
                log.warning("  Page crashed during pagination.")
                break

            # Wait for table to reload with new data
            self._wait_for_table(timeout=10)

            # Re-read headers in case columns differ
            new_headers = self._extract_headers_raw()
            if new_headers:
                headers = new_headers

        log.info("Subcategory %s: %d components from %d pages", subcategory, len(all_components), page_num)
        return all_components

    # ═══════════════════════════════════
    # MAIN ENTRY
    # ═══════════════════════════════════
    def scrape_category(self, category_slug, *, max_pages=None):
        cat = CATEGORIES.get(category_slug)
        if not cat:
            log.error("Unknown category: %s", category_slug)
            return []

        log.info("=" * 60)
        log.info("SCRAPING: %s", cat.name)
        log.info("=" * 60)

        urls = CATEGORY_URLS.get(category_slug, [])
        if not urls:
            for kw in cat.search_keywords[:3]:
                urls.append("/en/products/result?keywords=" + kw.replace(" ", "+"))

        log.info("%d subcategories to scrape.", len(urls))

        all_components = []
        for i, url in enumerate(urls):
            parts = url.rstrip("/").split("/")
            subcategory = parts[-2] if len(parts) >= 2 else "subcat_{}".format(i)

            log.info("")
            log.info("[%d/%d] %s", i + 1, len(urls), subcategory)

            try:
                self._ensure_page()
                comps = self._scrape_single_url(url, category_slug, subcategory, max_pages=max_pages)
                all_components.extend(comps)
                log.info("[%d/%d] %s -> %d components", i + 1, len(urls), subcategory, len(comps))
            except Exception as exc:
                log.error("FAILED %s: %s", subcategory, exc)
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
        log.info("DONE: %s -> %d total, %d unique", cat.name, len(all_components), len(unique))
        log.info("=" * 60)
        return unique
