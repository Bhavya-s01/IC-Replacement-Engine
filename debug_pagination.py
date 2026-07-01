"""
debug_pagination.py - Find the actual pagination elements on DigiKey
Run: python debug_pagination.py
"""

import sys, os, logging, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(message)s")

from plugins.digikey_playwright import DigiKeyPlaywrightPlugin

plugin = DigiKeyPlaywrightPlugin()
plugin.setup()

try:
    plugin._goto("https://www.digikey.com/en/products/filter/integrated-circuits-ics/pmic-voltage-regulators-linear/699")    
    time.sleep(3)

    page = plugin._page

    # 1. Check current URL
    print("")
    print("=== CURRENT URL ===")
    print(page.url)

    # 2. Find all buttons and their text
    print("")
    print("=== ALL BUTTONS (looking for pagination) ===")
    buttons = page.query_selector_all("button")
    for i, btn in enumerate(buttons):
        try:
            text = btn.inner_text().strip().replace("\n", " ")
            aria = btn.get_attribute("aria-label") or ""
            testid = btn.get_attribute("data-testid") or ""
            disabled = btn.is_disabled()
            visible = btn.is_visible()
            if text or aria or testid:
                if any(kw in (text + aria + testid).lower() for kw in
                       ["next", "prev", "page", "last", "first", "forward", "back", ">"]):
                    print("  btn[{}] text={} aria={} testid={} disabled={} visible={}".format(
                        i, repr(text[:50]), repr(aria), repr(testid), disabled, visible))
        except Exception:
            pass

    # 3. Find all links with pagination hints
    print("")
    print("=== ALL LINKS (looking for pagination) ===")
    links = page.query_selector_all("a")
    for i, a in enumerate(links):
        try:
            text = a.inner_text().strip().replace("\n", " ")
            href = a.get_attribute("href") or ""
            aria = a.get_attribute("aria-label") or ""
            if any(kw in (text + aria + href).lower() for kw in
                   ["next", "page=", "prev", "last", "first", ">"]):
                print("  a[{}] text={} aria={} href={}".format(
                    i, repr(text[:30]), repr(aria), repr(href[:80])))
        except Exception:
            pass

    # 4. Find all <select> elements (per-page dropdown)
    print("")
    print("=== ALL SELECT ELEMENTS ===")
    selects = page.query_selector_all("select")
    for i, sel in enumerate(selects):
        try:
            options = sel.query_selector_all("option")
            vals = []
            for opt in options:
                v = opt.get_attribute("value") or ""
                t = opt.inner_text().strip()
                vals.append("{}/{}".format(v, t))
            aria = sel.get_attribute("aria-label") or ""
            name = sel.get_attribute("name") or ""
            testid = sel.get_attribute("data-testid") or ""
            visible = sel.is_visible()
            print("  select[{}] aria={} name={} testid={} visible={} options={}".format(
                i, repr(aria), repr(name), repr(testid), visible, vals))
        except Exception:
            pass

    # 5. Look for pagination container
    print("")
    print("=== PAGINATION CONTAINERS ===")
    for sel in ["nav[aria-label*='pagination']", "nav[aria-label*='Pagination']",
                "[data-testid*='pagination']", "[data-testid*='paging']",
                ".pagination", "[class*='pagination']", "[class*='paging']",
                "[role='navigation']"]:
        try:
            els = page.query_selector_all(sel)
            if els:
                for el in els:
                    html = el.inner_html()[:300]
                    print("  {} -> {}".format(sel, html[:200]))
        except Exception:
            pass

    # 6. Check page text for pagination info
    print("")
    print("=== PAGE TEXT (pagination hints) ===")
    try:
        body = page.inner_text("body")
        import re
        for pat in [r"Page \d+ of \d+", r"\d+ of [\d,]+", r"Showing \d+",
                    r"[\d,]+ Results", r"[\d,]+ Products", r"per page"]:
            matches = re.findall(pat, body, re.IGNORECASE)
            if matches:
                print("  Pattern '{}': {}".format(pat, matches[:3]))
    except Exception as exc:
        print("  Error: {}".format(exc))

    # 7. Try URL manipulation
    print("")
    print("=== URL PAGINATION TEST ===")
    current_url = page.url
    if "?" in current_url:
        test_url = current_url + "&page=2&pageSize=25"
    else:
        test_url = current_url + "?page=2&pageSize=25"
    print("  Would try: {}".format(test_url))

finally:
    plugin.teardown()

print("")
print("Done! Paste this output so we can fix pagination.")