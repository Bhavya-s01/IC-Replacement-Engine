"""Playwright + Edge scraper for DigiKey - Final clean build."""

from __future__ import annotations
import logging, os, re, sys, time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from playwright.sync_api import sync_playwright
from plugins.base import PluginBase
from models import Component
from config import (CATEGORIES, DIGIKEY_BASE, DOWNLOAD_DIR, EDGE_CHANNEL,
                    HEADLESS_MODE, MAX_RETRIES, PAGE_LOAD_TIMEOUT_MS)
from utils.rate_limiter import AdaptiveRateLimiter
from utils.price_parser import parse_price_breaks, price_breaks_to_json

log = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════
# DigiKey filter page URLs per category
# Each URL goes directly to a parametric product table.
# ═══════════════════════════════════════════════════════
CATEGORY_URLS = {  # DigiKey selects the table by the numeric ID (slug is cosmetic); verified 2026-10
    "dcdc_converter": [
        "/en/products/filter/power-management-pmic/voltage-regulators-dc-dc-switching-regulators/739",
        "/en/products/filter/power-management-pmic/dc-dc-switching-controllers/715",
    ],
    "ldo_ic": [
        "/en/products/filter/power-management-pmic/voltage-regulators-linear-low-drop-out-ldo-regulators/699",
    ],
    "gate_driver": [
        "/en/products/filter/power-management-pmic/gate-drivers/730",
        "/en/products/filter/isolators-gate-drivers/906",
    ],
    "power_sequencer": [
        "/en/products/filter/power-management-pmic/supervisors/691",
        "/en/products/filter/power-management-pmic/power-management-specialized/761",
    ],
    "battery_management": [
        "/en/products/filter/power-management-pmic/battery-management/713",
        "/en/products/filter/power-management-pmic/battery-chargers/781",
    ],
    "usb_ic": [
        "/en/products/filter/interface/controllers/753",
        "/en/products/filter/interface/specialized/754",
        "/en/products/filter/interface/analog-switches-special-purpose/780",
    ],
    "video_interface": [
        "/en/products/filter/interface/serializers-deserializers/755",
        "/en/products/filter/interface/specialized/754",
    ],
    "serial_interface": [
        "/en/products/filter/interface/uarts-universal-asynchronous-receiver-transmitter/714",
        "/en/products/filter/interface/i-o-expanders/749",
        "/en/products/filter/interface/drivers-receivers-transceivers/710",
    ],
    "display_driver": [
        "/en/products/filter/power-management-pmic/led-drivers/745",
        "/en/products/filter/power-management-pmic/display-drivers/729",
    ],
    "tcon_video": [
        "/en/products/filter/linear/video-processing/684",
    ],
    "flash_memory": [
        "/en/products/filter/memory/memory/774",
    ],
    "eeprom": [
        "/en/products/filter/memory/memory/774",
    ],
    "fram_mram_sram": [
        "/en/products/filter/memory/memory/774",
    ],
    "audio_ic": [
        "/en/products/filter/audio-special-purpose/741",
        "/en/products/filter/interface/codecs/716",
    ],
    "ambient_light": [
        "/en/products/filter/optical-sensors/ambient-light-ir-uv-sensors/536",
        "/en/products/filter/proximity-sensors/524",
    ],
    "temp_sensor": [
        "/en/products/filter/temperature-sensors/analog-and-digital-output/518",
    ],
    "hall_sensor": [
        "/en/products/filter/magnetic-sensors/switches-solid-state/565",
    ],
    "protection_ic": [
        "/en/products/filter/tvs-diodes/144",
        "/en/products/filter/power-management-pmic/hot-swap-controllers/718",
        "/en/products/filter/power-management-pmic/power-distribution-switches-load-drivers/726",
        "/en/products/filter/surge-suppression-ics/152",
        "/en/products/filter/power-management-pmic/current-regulation-management/734",
    ],
    "clock_timing": [
        "/en/products/filter/clock-timing/clock-generators-plls-frequency-synthesizers/728",
        "/en/products/filter/clock-timing/clock-buffers-drivers/764",
        "/en/products/filter/clock-timing/programmable-timers-and-oscillators/689",
    ],
    "logic_mux": [
        "/en/products/filter/logic/buffers-drivers-receivers-transceivers/704",
        "/en/products/filter/logic/signal-switches-multiplexers-decoders/743",
        "/en/products/filter/logic/translators-level-shifters/732",
        "/en/products/filter/interface/analog-switches-multiplexers-demultiplexers/747",
    ],
    "mcu_soc": [
        "/en/products/filter/embedded-microcontrollers/685",
    ],
    "retimer_ic": [
        "/en/products/filter/interface/signal-buffers-repeaters-splitters/756",
    ],
    "opto_ic": [
        "/en/products/filter/optocouplers-optoisolators/logic-output-optoisolators/902",
        "/en/products/filter/optocouplers-optoisolators/transistor-photovoltaic-output-optoisolators/903",
        "/en/products/filter/optocouplers-optoisolators/triac-scr-output-optoisolators/904",
        "/en/products/filter/digital-isolators/901",
    ],
}
# Keyword search fallback for categories that return 0 from URL scraping


# One JS call extracts the entire table
JS_EXTRACT = """
() => {
    const r = { headers: [], rows: [], total: 0 };
    const m = document.body.innerText.match(/of\\s+([\\d,]+)/);
    if (m) r.total = parseInt(m[1].replace(/,/g, ''));
    document.querySelectorAll('thead th').forEach(th => r.headers.push(th.innerText.trim()));
    document.querySelectorAll('tbody tr').forEach(tr => {
        const row = { cells: [], links: [] };
        tr.querySelectorAll('td').forEach(td => {
            row.cells.push(td.innerText.trim());
            td.querySelectorAll('a[href]').forEach(a => {
                const h = a.getAttribute('href') || '';
                if (h.includes('.pdf') || h.includes('datasheet'))
                    row.links.push({ t: 'ds', h: h });
                else if (h.includes('/en/products/detail/'))
                    row.links.push({ t: 'pd', h: h });
            });
        });
        if (row.cells.length > 3) r.rows.push(row);
    });
    return r;
}
"""


class DigiKeyPlaywrightPlugin(PluginBase):
    name = "digikey_playwright"

    def __init__(self):
        self._pw = self._browser = self._context = self._page = self._engine = None
        self._limiter = AdaptiveRateLimiter(base_delay=1.0, max_delay=30.0, cooldown=120.0)

    @property
    def _should_stop(self):
        return getattr(self._engine, 'should_stop', False) if self._engine else False

    # ── LIFECYCLE ──────────────────────────────────────
    def setup(self):
        log.info("Launching Edge (headless=%s)...", HEADLESS_MODE)
        os.makedirs(DOWNLOAD_DIR, exist_ok=True)
        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch(
            channel=EDGE_CHANNEL, headless=HEADLESS_MODE,
            args=["--disable-blink-features=AutomationControlled",
                  "--no-first-run", "--no-default-browser-check"])
        self._context = self._browser.new_context(
            accept_downloads=True, viewport={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/125.0 Safari/537.36 Edg/125.0")
        self._context.set_default_timeout(PAGE_LOAD_TIMEOUT_MS)
        self._page = self._context.new_page()
        log.info("Opening DigiKey...")
        self._page.goto(DIGIKEY_BASE, wait_until="domcontentloaded")
        time.sleep(4)
        self._handle_popups()
        log.info("Ready.")

    def teardown(self):
        log.info("Closing browser...")
        for o in [self._context, self._browser, self._pw]:
            try:
                if o: (o.close if hasattr(o, 'close') else o.stop)()
            except Exception:
                pass

    # ── POPUPS ─────────────────────────────────────────
    def _handle_popups(self):
        p = self._page
        self._limiter.wait()
        # Region
        for s in ["button:has-text('SG')", "a:has-text('SG')",
                   "button:has-text('Singapore')", "button:has-text('OK')",
                   "button:has-text('Confirm')", "button:has-text('Go')",
                   "[data-testid='region-confirm']",
                   "div[role='dialog'] button:has-text('OK')",
                   "div[role='dialog'] button:has-text('Confirm')"]:
            try:
                e = p.query_selector(s)
                if e and e.is_visible():
                    self._limiter.wait()
            except Exception: continue
        # Cookie
        for s in ["button:has-text('Confirm My Choices')",
                   "button:has-text('Confirm my Choices')",
                   "button#onetrust-pc-btn-handler",
                   "button#onetrust-accept-btn-handler",
                   "button:has-text('Accept All')", "button:has-text('Accept')"]:
            try:
                e = p.query_selector(s)
                if e and e.is_visible():
                    self._limiter.wait()
            except Exception: continue
        # Close
        for s in ["button[aria-label='Close']", "button.close"]:
            try:
                e = p.query_selector(s)
                self._limiter.wait()
            except Exception: continue
        log.info("Popups done.")

    def _clear(self):
        try:
            self._page.evaluate("""
                document.querySelectorAll('#auto-modal-mask,.dk-site__mask,[class*="mask visible"]').forEach(e=>e.remove());
                document.querySelectorAll('#onetrust-banner-sdk').forEach(e=>e.style.display='none');
            """)
        except Exception: pass
        for s in ["button:has-text('SG')", "button:has-text('OK')",
                   "button:has-text('Confirm My Choices')", "button:has-text('Confirm')",
                   "button#onetrust-accept-btn-handler", "button[aria-label='Close']"]:
            try:
                e = self._page.query_selector(s)
                if e and e.is_visible(): e.click(); time.sleep(0.5); break
            except Exception: continue

    # ── PAGE MANAGEMENT ────────────────────────────────
    def _alive(self):
        try: return self._page and not self._page.is_closed() and bool(self._page.title())
        except Exception: return False

    def _ensure(self):
        if not self._alive():
            log.warning("Page dead. Recreating...")
            self._page = self._context.new_page()
            self._page.goto(DIGIKEY_BASE, wait_until="domcontentloaded")
            self._limiter.wait()

    def _goto(self, url):
        self._ensure()
        full = url if url.startswith("http") else DIGIKEY_BASE + url
        for a in range(1, MAX_RETRIES + 1):
            try:
                self._page.goto(full, wait_until="domcontentloaded", timeout=PAGE_LOAD_TIMEOUT_MS)
                self._limiter.wait()
                return True
            except Exception as x:
                log.warning("Nav %d: %s", a, str(x)[:60])
                if a < MAX_RETRIES: self._ensure(); time.sleep(3 * a)
        return False

    def _wait_table(self, t=15):
        end = time.time() + t
        while time.time() < end:
            try:
                e = self._page.query_selector("table")
                if e and e.is_visible(): return True
            except Exception: pass
            self._limiter.wait()
        return False

    # ── SET 100 PER PAGE ───────────────────────────────
    def _set_100(self):
        p = self._page
        log.info("Setting 100/page...")
        self._clear(); time.sleep(0.5)
        try: p.evaluate("document.querySelectorAll('#auto-modal-mask,.dk-site__mask').forEach(e=>e.remove());")
        except Exception: pass
        time.sleep(0.5)

        # Click dropdown
        dd = None
        for s in ["[data-testid='per-page-selector'] [role='button']",
                   "[data-testid='per-page-selector'] [aria-haspopup='listbox']",
                   "[data-testid='per-page-selector']"]:
            try:
                e = p.query_selector(s)
                if e and e.is_visible(): dd = e; break
            except Exception: continue
        if not dd:
            log.debug("No dropdown."); return False
        try: dd.click(force=True)
        except Exception:
            try: p.evaluate("document.querySelector(\"[data-testid='per-page-selector'] [role='button']\")?.click();")
            except Exception: return False
        self._limiter.wait()

        # Click 100
        ok = False
        for _ in range(3):
            for strat in [
                lambda: self._click_option_by_role(p, "100"),
                lambda: self._click_option_by_dv(p, "100"),
                lambda: self._click_option_by_li(p, "100"),
                lambda: self._click_option_by_js(p, "100"),
            ]:
                ok = strat()
                if ok: break
            if ok: break
            self._limiter.wait()

        if not ok:
            log.warning("Could not select 100.")
            try: p.keyboard.press("Escape")
            except Exception: pass
            return False

        log.info("Selected 100. Reloading...")
        self._limiter.wait()
        try: p.wait_for_load_state("networkidle", timeout=20_000)
        except Exception: pass
        self._limiter.wait()
        try:
            n = len(p.evaluate(JS_EXTRACT).get("rows", []))
            log.info("Rows on page: %d", n); return n > 25
        except Exception: return True

    def _click_option_by_role(self, p, val):
        try:
            for o in p.query_selector_all("[role='option']"):
                if o.inner_text().strip() == val and o.is_visible():
                    o.click(force=True); return True
        except Exception: pass
        return False

    def _click_option_by_dv(self, p, val):
        try:
            o = p.query_selector("li[data-value='{}']".format(val))
            if o and o.is_visible(): o.click(force=True); return True
        except Exception: pass
        return False

    def _click_option_by_li(self, p, val):
        try:
            for li in p.query_selector_all("li"):
                if li.inner_text().strip() == val and li.is_visible():
                    li.click(force=True); return True
        except Exception: pass
        return False

    def _click_option_by_js(self, p, val):
        try:
            r = p.evaluate("""(val) => {
                for (const el of document.querySelectorAll('li,[role="option"]')) {
                    if (el.innerText.trim() === val && el.offsetParent !== null) {
                        el.click(); return 'ok';
                    }
                } return 'no';
            }""", val)
            return r == 'ok'
        except Exception: return False

    # ── PAGINATION ─────────────────────────────────────
    def _click_next(self):
        p = self._page
        self._clear(); time.sleep(0.3)
        try:
            b = p.query_selector("[data-testid='btn-next-page']")
            if b and b.is_visible() and not b.is_disabled():
                cls = b.get_attribute("class") or ""
                if "Mui-disabled" in cls: return False
                b.scroll_into_view_if_needed(); time.sleep(0.3)
                self._limiter.wait()
                b.click()
                try: p.wait_for_load_state("networkidle", timeout=15_000)
                except Exception: pass
                self._limiter.wait(); self._clear()
                return True
        except Exception: pass
        # Fallback: numbered button
        try:
            for i in range(1, 500):
                b = p.query_selector("[data-testid='btn-page-{}']".format(i))
                if b and b.is_disabled():
                    n = p.query_selector("[data-testid='btn-page-{}']".format(i+1))
                    if n and n.is_visible() and not n.is_disabled():
                        n.scroll_into_view_if_needed(); time.sleep(0.3)
                        self._limiter.wait()
                        n.click()
                        try: p.wait_for_load_state("networkidle", timeout=15_000)
                        except Exception: pass
                        self._limiter.wait(); self._clear()
                        log.info("Page %d.", i+1); return True
                    return False
        except Exception: pass
        return False

    # ── EXTRACT & PARSE ────────────────────────────────
    def _extract(self):
        self._clear()
        try: return self._page.evaluate(JS_EXTRACT)
        except Exception: return {"headers": [], "rows": [], "total": 0}

    def _parse_row(self, headers, row, cat, subcat):
        cells = row.get("cells", [])
        links = row.get("links", [])
        if len(cells) < 3: return None
        raw = {}
        for i, t in enumerate(cells):
            raw[headers[i] if i < len(headers) else "_c{}".format(i)] = t
        for lnk in links:
            h = lnk.get("h", "")
            if h.startswith("//"):
                h = "https:" + h
            elif h.startswith("/"):
                h = DIGIKEY_BASE + h
            raw["_ds" if lnk["t"] == "ds" else "_pd"] = h

        mc = raw.get("Mfr Part #", "")
        if not mc: return None
        ln = [l.strip() for l in mc.split("\n") if l.strip()]
        if not ln: return None
        mpn, desc, mfr = ln[0], (ln[1] if len(ln)>1 else ""), (ln[2] if len(ln)>2 else "")

        stk = 0
        sq = raw.get("Quantity Available", "")
        if sq:
            sc = re.sub(r"[^\d]", "", sq.split("\n")[0])
            stk = int(sc) if sc else 0
        prc = 0.0
        price_breaks_json = "[]"
        pq = raw.get("Price", "")
        if pq:
            breaks = parse_price_breaks(pq)
            if breaks:
                prc = breaks[0][1]
                price_breaks_json = price_breaks_to_json(breaks)
            else:
                pm = re.search(r"\$([\d.]+)", pq)
                if pm:
                    try: prc = float(pm.group(1))
                    except ValueError: pass
        pkg = raw.get("Package / Case") or raw.get("Package") or ""
        if pkg and any(k in pkg.lower() for k in ["tape","reel","tube","bulk","digi-reel"]): pkg = ""
        mnt = ""
        for k in ["Mounting Type","Mount Type"]:
            if k in raw and raw[k]: mnt = raw[k]; break
        sts = ""
        for k in ["Product Status","Part Status"]:
            if k in raw and raw[k]: sts = raw[k]; break
        skip = {"","Mfr Part #","Manufacturer","Description","Digi-Key Part Number",
                "Quantity Available","Stock","Unit Price","Price","Package / Case",
                "Package","Supplier Device Package","Mounting Type","Mount Type",
                "Product Status","Part Status","Lifecycle","Status","Tariff Status"}
        specs = {k: v for k, v in raw.items() if k not in skip and not k.startswith("_") and v and v != "-"}
        return Component(
            manufacturer_part_number=mpn, manufacturer=mfr,
            digikey_part_number="", description=desc,
            category=cat, subcategory=subcat,
            datasheet_url=raw.get("_ds",""), product_url=raw.get("_pd",""),
            stock=stk, unit_price=prc, package=pkg,
            price_breaks=price_breaks_json,
            mounting_type=mnt, lifecycle_status=sts,
            source="digikey", raw_specs=specs)

    # ── SCRAPE ONE SUBCATEGORY ─────────────────────────
    def _scrape_url(self, url, cat, subcat, max_pages=None):
        if not self._goto(url): return []
        if not self._wait_table(): return []
        self._set_100()

        data = self._extract()
        headers = data.get("headers", [])
        total = data.get("total", 0)
        rows = data.get("rows", [])
        per = len(rows) if rows else 25
        tp = (total // per) + 1 if total else 0
        log.info("  Total: %d | %d/page | ~%d pages", total, per, tp)

        all_c = []
        pg = errs = 0
        while True:
            pg += 1
            if self._should_stop:
                log.warning("Stop. Saving %d.", len(all_c)); break
            if max_pages and pg > max_pages:
                log.info("max_pages=%d.", max_pages); break
            if pg > 1:
                data = self._extract()
                headers = data.get("headers", headers)
                rows = data.get("rows", [])
            if not rows:
                errs += 1
                if errs >= 3: break
                self._limiter.wait()
            errs = 0
            comps = [c for r in rows for c in [self._parse_row(headers, r, cat, subcat)] if c]
            log.info("  Page %d: %d parts (total %d)", pg, len(comps), len(all_c)+len(comps))
            if pg == 1 and comps:
                for c in comps[:2]:
                    log.info("    -> %s | %s | stk=%d", c.manufacturer_part_number, c.manufacturer, c.stock)
            all_c.extend(comps)
            self._limiter.report_success()
            if total > 0 and len(all_c) >= total: break
            if len(comps) < per: break
            if not self._click_next(): break
            if not self._alive(): break
        log.info("  %s: %d parts / %d pages", subcat, len(all_c), pg)
        return all_c

    # ── MAIN ───────────────────────────────────────────
    

    def scrape_category(self, category_slug, *, max_pages=None):
            cat = CATEGORIES.get(category_slug)
            if not cat: log.error("Unknown: %s", category_slug); return []
            log.info("=" * 60)
            log.info("SCRAPING: %s", cat.name)
            log.info("=" * 60)
            urls = CATEGORY_URLS.get(category_slug, [])
            if not urls:
                for kw in cat.search_keywords[:3]:
                    urls.append("/en/products/result?keywords=" + kw.replace(" ", "+"))
            log.info("%d subcats. Ctrl+C = safe stop.", len(urls))
            from database import Database
            db = Database()
            all_c, saved = [], 0
            for i, url in enumerate(urls):
                if self._should_stop: break
                parts = url.rstrip("/").split("/")
                sub = parts[-2] if len(parts) >= 2 else "s{}".format(i)
                log.info("\n[%d/%d] %s", i+1, len(urls), sub)
                try:
                    self._ensure()
                    comps = self._scrape_url(url, category_slug, sub, max_pages=max_pages)
                    if comps:
                        s = db.bulk_upsert(comps); saved += s
                        log.info("[%d/%d] %s -> %d scraped, %d saved (total %d)", i+1, len(urls), sub, len(comps), s, saved)
                    all_c.extend(comps)
                    self._limiter.report_success()
                except Exception as x:
                    log.error("FAIL %s: %s", sub, str(x)[:80])
                    try: self._ensure()
                    except Exception: pass
            # Reclassify memory parts into correct subcategory
            if category_slug in ("eeprom", "flash_memory", "fram_mram_sram"):
                from utils.memory_classifier import classify_memory_part
                for comp in all_c:
                    comp.category = classify_memory_part(comp)
                log.info("Reclassified %d memory parts by type.", len(all_c))  
            seen = set()
            uniq = [c for c in all_c if c.manufacturer_part_number not in seen and not seen.add(c.manufacturer_part_number)]
            log.info("\n" + "=" * 60)
            log.info("DONE: %s -> %d unique, %d saved", cat.name, len(uniq), saved)
            log.info("=" * 60)
            db.close()
            return uniq
