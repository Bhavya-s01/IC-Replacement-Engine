"""Gap 12: Download and extract specs from PDF datasheets."""

import os
import re
import logging

log = logging.getLogger(__name__)

try:
    import fitz
    PYMUPDF_OK = True
except ImportError:
    PYMUPDF_OK = False

SPEC_PATTERNS = {
    "Efficiency": r"efficiency[:\s]+(\d+\.?\d*)\s*%",
    "Switching Frequency": r"switching\s+frequency[:\s]+([\d.]+)\s*(k?Hz|MHz)",
    "Output Ripple": r"output\s+ripple[:\s]+([\d.]+)\s*(mV|V)",
    "Thermal Resistance JA": r"(?:theta|\\u03b8)\s*JA[:\s]+([\d.]+)\s*C/W",
    "PSRR": r"PSRR[:\s]+([\d.]+)\s*dB",
    "Quiescent Current": r"quiescent\s+current[:\s]+([\d.]+)\s*(uA|mA)",
    "Dropout Voltage": r"dropout\s+voltage[:\s]+([\d.]+)\s*(mV|V)",
}


class DatasheetParser:
    def __init__(self, download_dir="downloads/datasheets"):
        self.download_dir = download_dir
        os.makedirs(download_dir, exist_ok=True)

    def download(self, url, mpn):
        if not url:
            return None
        safe_name = re.sub(r"[^\w\-.]", "_", mpn) + ".pdf"
        path = os.path.join(self.download_dir, safe_name)
        if os.path.exists(path):
            return path
        try:
            import requests
            resp = requests.get(url, timeout=30, verify=False,
                                headers={"User-Agent": "Mozilla/5.0"})
            ct = resp.headers.get("content-type", "")
            if resp.status_code == 200 and ("pdf" in ct or url.endswith(".pdf")):
                with open(path, "wb") as f:
                    f.write(resp.content)
                log.info("Downloaded datasheet for %s (%d KB)", mpn, len(resp.content) // 1024)
                return path
        except Exception as exc:
            log.debug("Download failed for %s: %s", mpn, exc)
        return None

    def extract_specs(self, pdf_path, max_pages=5):
        if not PYMUPDF_OK:
            log.warning("PyMuPDF not installed. Run: pip install pymupdf")
            return {}
        specs = {}
        try:
            doc = fitz.open(pdf_path)
            text = ""
            for page_num in range(min(max_pages, len(doc))):
                text += doc[page_num].get_text()
            doc.close()
        except Exception as exc:
            log.debug("PDF parse failed for %s: %s", pdf_path, exc)
            return specs

        for spec_name, pattern in SPEC_PATTERNS.items():
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                value = match.group(1)
                unit = match.group(2) if match.lastindex >= 2 else ""
                specs[spec_name] = "{}{}".format(value, unit)
        return specs

    def enrich_component(self, db, component_id):
        conn = db._get_conn()
        row = conn.execute(
            "SELECT manufacturer_part_number, datasheet_url FROM components WHERE id = ?",
            (component_id,)
        ).fetchone()
        if not row or not row[1]:
            return {}
        mpn, url = row[0], row[1]
        pdf_path = self.download(url, mpn)
        if not pdf_path:
            return {}
        specs = self.extract_specs(pdf_path)
        for spec_name, spec_value in specs.items():
            existing = conn.execute(
                "SELECT 1 FROM specifications WHERE component_id = ? AND spec_name = ?",
                (component_id, spec_name)
            ).fetchone()
            if not existing:
                conn.execute(
                    "INSERT INTO specifications (component_id, spec_name, spec_value) VALUES (?, ?, ?)",
                    (component_id, spec_name, spec_value)
                )
        conn.commit()
        log.info("Enriched %s with %d datasheet specs", mpn, len(specs))
        return specs