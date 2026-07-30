"""
llm_parser.py - LLM-powered datasheet spec + pin extraction.
Uses NVIDIA NIM (free tier) with SSL bypass for corporate networks.

Requires: pip install openai httpx pymupdf requests
"""

import os
import re
import json
import logging
from typing import Dict, Tuple, Optional

log = logging.getLogger(__name__)

try:
    from openai import OpenAI
    OPENAI_OK = True
except ImportError:
    OPENAI_OK = False

try:
    import httpx
    HTTPX_OK = True
except ImportError:
    HTTPX_OK = False

try:
    import fitz
    PYMUPDF_OK = True
except ImportError:
    PYMUPDF_OK = False

try:
    import requests
    REQUESTS_OK = True
except ImportError:
    REQUESTS_OK = False

# ═══════════════════════════════════════════
# Configuration
# ═══════════════════════════════════════════
NVIDIA_API_KEY = os.environ.get(
    "NVIDIA_API_KEY",
    "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"
)
NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"
NVIDIA_MODEL = "meta/llama-3.1-70b-instruct"


# ═══════════════════════════════════════════
# Category prompts
# ═══════════════════════════════════════════
CATEGORY_PROMPTS = {
    "ldo_ic": """Extract these specs from the LDO regulator datasheet:
- Output Voltage (V)
- Input Voltage Min (V), Input Voltage Max (V)
- Output Current Max (mA)
- Dropout Voltage (mV) at rated current
- Quiescent Current / Ground Current (uA)
- PSRR in dB (at 1kHz if available)
- Output Noise RMS (uV)
- Load Regulation (mV or %), Line Regulation (mV or %/V)
- Enable Threshold Voltage (V)
- Current Limit (mA)
- Soft Start Time (ms or us)
- Thermal Shutdown Temperature (C)
- Thermal Resistance JA (C/W)
- ESD Rating HBM (kV)
Also extract PIN ASSIGNMENTS: pin number, name, function.""",

    "dcdc_converter": """Extract specs from this DC-DC converter datasheet:
- Input Voltage Min/Max (V)
- Output Voltage (V)
- Output Current Max (A or mA)
- Switching Frequency (kHz or MHz)
- Peak Efficiency (%)
- Quiescent Current (uA)
- Output Ripple (mV p-p)
- Duty Cycle Max (%)
- Enable Threshold (V)
- Soft Start Time (ms)
- Topology (Buck, Boost, Buck-Boost)
Also extract PIN ASSIGNMENTS.""",

    "audio_ic": """Extract specs from this audio IC datasheet:
- Supply Voltage Range (V)
- Supply Current (mA)
- Output Power (mW or W) at specified load
- THD+N (%) at specified conditions
- SNR (dB)
- PSRR (dB)
- Number of Channels
- Shutdown Current (uA)
Also extract PIN ASSIGNMENTS.""",

    "protection_ic": """Extract specs from this protection IC datasheet:
- Reverse Standoff Voltage VRWM (V)
- Breakdown Voltage VBR (V)
- Clamping Voltage VC (V) at specified current
- Peak Pulse Current IPP (A)
- Peak Pulse Power (W)
- Leakage Current (uA)
- Response Time (ns or ps)
- Capacitance (pF)
Also extract PIN ASSIGNMENTS.""",

    "flash_memory": """Extract specs from this flash memory datasheet:
- Memory Size (Mbit or Kbit)
- Interface Type (SPI, Dual SPI, Quad SPI)
- Max Clock Frequency (MHz)
- Supply Voltage Range (V)
- Page Program Time (ms or us)
- Sector Erase Time (ms)
- Standby Current (uA)
- Active Read Current (mA)
- Write Endurance (cycles)
- Data Retention (years)
Also extract PIN ASSIGNMENTS.""",
}

DEFAULT_PROMPT = """Extract ALL electrical specifications from this IC datasheet.
Include: voltages, currents, power, frequency, timing, temperature ratings,
noise, PSRR, efficiency, and any other measurable parameters.
Also extract PIN ASSIGNMENTS (pin number, name, function)."""


# ═══════════════════════════════════════════
# PDF handling
# ═══════════════════════════════════════════
def download_pdf(url, mpn, download_dir="downloads/datasheets"):
    """Download a datasheet. Handles LCSC HTML wrappers by extracting real PDF URL."""
    if not url or not REQUESTS_OK:
        return None, None
    os.makedirs(download_dir, exist_ok=True)
    safe = re.sub(r"[^\w\-.]", "_", mpn)

    pdf_path = os.path.join(download_dir, safe + ".pdf")
    html_path = os.path.join(download_dir, safe + ".html")

    # Check for cached files
    if os.path.exists(pdf_path) and os.path.getsize(pdf_path) > 5000:
        with open(pdf_path, "rb") as f:
            if f.read(5) == b"%PDF-":
                return pdf_path, "pdf"

    if os.path.exists(html_path) and os.path.getsize(html_path) > 1000:
        return html_path, "html"

    try:
        resp = requests.get(url, timeout=30, verify=False,
                            headers={"User-Agent": "Mozilla/5.0"})
        if resp.status_code != 200:
            return None, None

        content = resp.content

        # Check if it's actually a PDF
        if content[:5] == b"%PDF-":
            with open(pdf_path, "wb") as f:
                f.write(content)
            log.info("  Downloaded %s.pdf (%d KB)", safe, len(content) // 1024)
            return pdf_path, "pdf"

        # It's HTML — try to extract the real PDF URL from LCSC wrapper
        if b"<!doctype" in content[:50].lower() or b"<html" in content[:50].lower():
            text = content.decode("utf-8", errors="replace")

            # LCSC embeds the real PDF URL in the page
            real_pdf_patterns = [
                r'(https?://wmsc\.lcsc\.com/[^"\']+\.pdf)',
                r'"pdfUrl"\s*:\s*"(https?://[^"]+\.pdf)"',
                r'src="(https?://[^"]+\.pdf[^"]*)"',
                r'href="(https?://[^"]+\.pdf[^"]*)"',
            ]

            for pattern in real_pdf_patterns:
                match = re.search(pattern, text)
                if match:
                    real_url = match.group(1)
                    log.info("  Found real PDF URL: %s", real_url[:70])
                    try:
                        pdf_resp = requests.get(real_url, timeout=30, verify=False,
                                                headers={"User-Agent": "Mozilla/5.0"})
                        if pdf_resp.status_code == 200 and pdf_resp.content[:5] == b"%PDF-":
                            with open(pdf_path, "wb") as f:
                                f.write(pdf_resp.content)
                            log.info("  Downloaded real PDF (%d KB)", len(pdf_resp.content) // 1024)
                            return pdf_path, "pdf"
                    except Exception:
                        pass

            # No real PDF found — save HTML for text extraction
            with open(html_path, "wb") as f:
                f.write(content)
            log.info("  Downloaded %s.html (%d KB)", safe, len(content) // 1024)
            return html_path, "html"

        # Unknown content type
        with open(pdf_path, "wb") as f:
            f.write(content)
        return pdf_path, "pdf"

    except Exception as exc:
        log.debug("Download failed %s: %s", mpn, exc)
        return None, None


def extract_pdf_text(pdf_path, max_pages=12):
    if not PYMUPDF_OK:
        return ""
    try:
        doc = fitz.open(pdf_path)
        pages = [doc[i].get_text() for i in range(min(max_pages, len(doc)))]
        doc.close()
        text = "\n\n".join(pages)
        if len(text) > 12000:
            text = text[:12000]
        return text
    except Exception:
        return ""

def extract_html_text(html_content):
    """Extract readable text from HTML content."""
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html_content, "html.parser")
        # Remove script and style elements
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()
        text = soup.get_text(separator="\n", strip=True)
        # Truncate to fit LLM context
        if len(text) > 12000:
            text = text[:12000]
        return text
    except ImportError:
        # Fallback: strip tags with regex
        import re
        text = re.sub(r'<[^>]+>', ' ', html_content)
        text = re.sub(r'\s+', ' ', text).strip()
        return text[:12000]


# ═══════════════════════════════════════════
# LLM Client — NVIDIA NIM with SSL bypass
# ═══════════════════════════════════════════
def _get_client():
    """
    Create OpenAI client pointing to NVIDIA NIM.
    Uses httpx with verify=False to bypass corporate SSL inspection.
    """
    if not OPENAI_OK:
        log.warning("openai package not installed. Run: python -m pip install openai")
        return None, None

    key = NVIDIA_API_KEY
    if not key:
        log.warning("No NVIDIA_API_KEY set")
        return None, None

    try:
        if HTTPX_OK:
            http_client = httpx.Client(verify=False, timeout=60.0)
            client = OpenAI(
                base_url=NVIDIA_BASE_URL,
                api_key=key,
                http_client=http_client,
            )
        else:
            client = OpenAI(
                base_url=NVIDIA_BASE_URL,
                api_key=key,
            )
        return client, NVIDIA_MODEL
    except Exception as e:
        log.warning("Failed to create LLM client: %s", e)
        return None, None


# ═══════════════════════════════════════════
# LLM Extraction
# ═══════════════════════════════════════════
def extract_with_llm(text, mpn, category="", package=""):
    """
    Use NVIDIA NIM LLM to extract specs and pinout from datasheet text.
    Returns (specs_dict, pins_dict).
    """
    client, model = _get_client()
    if not client:
        return {}, {}

    cat_prompt = CATEGORY_PROMPTS.get(category, DEFAULT_PROMPT)

    system_msg = (
        "You are a technical datasheet parser. Extract electrical "
        "specifications and pin assignments from IC datasheet text. "
        "Return ONLY valid JSON with no markdown.\n\n"
        "Format:\n"
        '{\n'
        '  "specs": {"Spec Name": "numeric_value_only", ...},\n'
        '  "pins": {"1": {"name": "PIN_NAME", '
        '"function": "power_input|power_output|ground|enable|'
        'feedback|no_connect|signal|other"}, ...}\n'
        '}\n\n'
        "Rules:\n"
        "- Return numeric values WITHOUT units "
        '(e.g. "160" not "160mV")\n'
        "- Use typical values when both typical and max exist\n"
        "- Pin functions must be one of: power_input, power_output, "
        "ground, enable, feedback, no_connect, signal, other\n"
        "- If a spec is not found, omit it entirely\n"
        "- Do NOT guess or hallucinate values not in the text"
    )

    user_msg = (
        "Part: {}\nCategory: {}\nPackage: {}\n\n"
        "{}\n\nDATASHEET TEXT:\n{}"
    ).format(mpn, category, package, cat_prompt, text)

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": user_msg},
            ],
            temperature=0.1,
            max_tokens=2000,
        )

        raw = response.choices[0].message.content.strip()

        # Strip markdown code blocks if present
        if "```" in raw:
            match = re.search(r"```(?:json)?\s*(.*?)```", raw, re.DOTALL)
            if match:
                raw = match.group(1).strip()

        data = json.loads(raw)
        specs = {}
        for k, v in data.get("specs", {}).items():
            if v is not None and str(v).strip():
                specs[k] = str(v).strip()
        pins = data.get("pins", {})

        log.info("LLM extracted %d specs, %d pins for %s",
                 len(specs), len(pins), mpn)
        return specs, pins

    except json.JSONDecodeError as e:
        log.warning("LLM returned invalid JSON for %s: %s", mpn, e)
        return {}, {}
    except Exception as e:
        log.warning("LLM extraction failed for %s: %s", mpn, e)
        return {}, {}


# ═══════════════════════════════════════════
# Main Parser Class
# ═══════════════════════════════════════════
class LLMDatasheetParser:
    def __init__(self, download_dir="downloads/datasheets"):
        self.download_dir = download_dir

    def parse_datasheet(self, url, mpn, package="", category=""):
        from finder_extras.datasheet_parser import PinoutInfo

        pinout = PinoutInfo(mpn=mpn, package=package)

        # Download — handles both PDF and HTML
        file_path, file_type = download_pdf(url, mpn, self.download_dir)
        if not file_path:
            return {}, pinout

        # Extract text based on file type
        if file_type == "pdf":
            text = extract_pdf_text(file_path)
        elif file_type == "html":
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                html_content = f.read()
            text = extract_html_text(html_content)
        else:
            return {}, pinout

        if not text or len(text) < 100:
            log.warning("  Insufficient text from %s (%s)", mpn, file_type)
            return {}, pinout

        log.info("  Extracted %d chars from %s (%s)", len(text), mpn, file_type)

        # Use LLM to extract specs (same call for PDF or HTML text)
        specs, pins = extract_with_llm(text, mpn, category, package)

        # Build pinout from LLM output
        if pins:
            for pin_num_str, pin_data in pins.items():
                try:
                    num = int(pin_num_str)
                    name = pin_data.get("name", "")
                    if name:
                        pinout.add_pin(num, name, pin_data.get("function", ""))
                except (ValueError, TypeError):
                    pass
            if pinout.is_valid():
                pinout.confidence = 0.9
                pinout.source = "llm_extraction"

            # Store pin count as a spec directly from LLM extraction
            if pinout.total_pins > 0:
                specs["Pin Count"] = str(pinout.total_pins)

        return specs, pinout