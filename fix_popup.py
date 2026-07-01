"""
fix_popup.py - Adds aggressive popup dismissal after every page change.
Run: python fix_popup.py
Then: python test_scrape.py
"""

import os

BASE = os.path.dirname(os.path.abspath(__file__))
path = os.path.join(BASE, "plugins", "digikey_playwright.py")

# Read current file
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

# Replace the _click_next_page method and enhance popup handling
old_popups_quick = '''    def _dismiss_popups_quick(self):
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
                continue'''

new_popups_quick = '''    def _dismiss_popups_quick(self):
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
                continue'''

content = content.replace(old_popups_quick, new_popups_quick)

# Also update _click_next_page to dismiss popups after clicking
old_next_click = '''                log.info("Clicked next page button.")
                time.sleep(3)

                # Wait for table to reload
                try:
                    page.wait_for_load_state("networkidle", timeout=15_000)
                except Exception:
                    pass
                time.sleep(REQUEST_DELAY_SECONDS)

                # Verify page actually changed
                return True'''

new_next_click = '''                log.info("Clicked next page button.")
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
                return True'''

content = content.replace(old_next_click, new_next_click)

# Also update the numbered page fallback
old_num_click = '''                log.info("Clicked page %d button.", next_num)
                time.sleep(3)
                try:
                    page.wait_for_load_state("networkidle", timeout=15_000)
                except Exception:
                    pass
                time.sleep(REQUEST_DELAY_SECONDS)
                return True'''

new_num_click = '''                log.info("Clicked page %d button.", next_num)
                time.sleep(3)
                try:
                    page.wait_for_load_state("networkidle", timeout=15_000)
                except Exception:
                    pass
                time.sleep(1)
                self._dismiss_popups_quick()
                time.sleep(REQUEST_DELAY_SECONDS)
                return True'''

content = content.replace(old_num_click, new_num_click)

# Also add popup dismissal in _goto after navigation
old_goto_return = '''                self._page.goto(full_url, wait_until="domcontentloaded", timeout=PAGE_LOAD_TIMEOUT_MS)
                time.sleep(3)
                self._dismiss_popups_quick()
                return'''

new_goto_return = '''                self._page.goto(full_url, wait_until="domcontentloaded", timeout=PAGE_LOAD_TIMEOUT_MS)
                time.sleep(3)
                self._dismiss_popups_quick()
                time.sleep(1)
                self._dismiss_popups_quick()
                return'''

content = content.replace(old_goto_return, new_goto_return)

with open(path, "w", encoding="utf-8") as f:
    f.write(content)

print("Fixed: {}".format(path))
print("")
print("Popup dismissal now runs after EVERY navigation and page change.")
print("Run: python test_scrape.py")