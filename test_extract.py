# Save as test_extract.py, run: python test_extract.py

import os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from finder_extras.datasheet_parser import DatasheetParser

parser = DatasheetParser()

# Download the MIC5501 datasheet
pdf = parser.download(
    "https://ww1.microchip.com/downloads/en/DeviceDoc/MIC550x.pdf",
    "MIC5501"
)

if not pdf:
    print("Download failed")
    exit()

# Extract raw text from first 5 pages
pages = parser._get_page_texts(pdf, max_pages=5)
text = "\n".join(pages)

# Show what keywords appear in the text
print("=== KEYWORD SCAN (first 5 pages) ===\n")
keywords = [
    "PSRR", "psrr", "power supply rejection",
    "dropout", "drop-out", "drop out",
    "quiescent", "ground current", "supply current",
    "output noise", "noise density",
    "load regulation", "line regulation",
    "output voltage accuracy", "voltage accuracy",
    "enable", "shutdown", "SHDN",
    "thermal shutdown", "thermal protection",
    "output current", "current limit",
]

for kw in keywords:
    count = text.lower().count(kw.lower())
    if count > 0:
        # Show the context around the first match
        idx = text.lower().find(kw.lower())
        snippet = text[max(0, idx-30):idx+80].replace("\n", " ").strip()
        print("  Found '{}' ({} times): ...{}...".format(kw, count, snippet))

# Also try extracting with all patterns and show what matched vs didn't
print("\n=== PATTERN RESULTS ===\n")
specs, pinout = parser.parse_datasheet(
    "https://ww1.microchip.com/downloads/en/DeviceDoc/MIC550x.pdf",
    "MIC5501",
    package="SOT-23-5",
    category="ldo_ic"
)

print("Specs found ({}):".format(len(specs)))
for name, val in sorted(specs.items()):
    print("  {}: {}".format(name, val))

print("\nPinout: {} pins (valid={}, confidence={:.0f}%)".format(
    pinout.total_pins, pinout.is_valid(), pinout.confidence * 100))