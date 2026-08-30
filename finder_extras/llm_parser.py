"""
llm_parser.py - LLM-powered datasheet spec + pin extraction.
Provider: NVIDIA NIM using Meta Llama 3.1 8B Instruct.

Features:
- Dynamically generates prompts from match_rules (ensures all specs extracted)
- Validates specs against category requirements
- Falls back to regex parser for missing specs
- Sanity checks to prevent hallucinations

Requires: pip install openai httpx pymupdf requests
"""

import os
import re
import json
import logging
from typing import Dict, Tuple, Optional, Set

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
# Import match_rules for dynamic prompts
# ═══════════════════════════════════════════
def _get_required_specs(category: str) -> Set[str]:
    """
    Load spec names from match_rules for this category.
    This ensures LLM only extracts specs that matter for scoring.
    """
    try:
        from match_rules import get_rules
        rules = get_rules(category)
        spec_names = set()
        for rule in rules.rules:
            spec_names.add(rule.spec_name)
            spec_names.update(rule.aliases)
        return spec_names
    except ImportError:
        log.debug("match_rules not available, using fallback specs")
        return set()


def _rule_spec_map(category: str) -> Dict[str, str]:
    """Map canonical names and aliases to their canonical match-rule name.

    The matcher reads canonical names.  Keeping LLM aliases in the database
    makes a part look enriched while silently reducing its match score.
    """
    try:
        from match_rules import get_rules
        result = {}
        for rule in get_rules(category).rules:
            for name in [rule.spec_name, *rule.aliases]:
                result[re.sub(r"\s+", " ", name).strip().casefold()] = rule.spec_name
        return result
    except (ImportError, AttributeError):
        return {}


def _canonical_spec_name(name: str, category: str) -> Optional[str]:
    clean = re.sub(r"\s+", " ", str(name or "")).strip()
    if not clean:
        return None
    rules = _rule_spec_map(category)
    return rules.get(clean.casefold())


def _load_local_env() -> None:
    """Load only LLM credentials from a project-local .env file.

    Codex and an interactive PowerShell normally run in different processes;
    this makes a user-configured key available to the batch runner without
    printing it or requiring an additional package.
    """
    env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
    try:
        with open(env_path, encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key = key.strip()
                if key == "NVIDIA_API_KEY" and not os.environ.get(key):
                    os.environ[key] = value.strip().strip('"').strip("'")
    except FileNotFoundError:
        pass


_load_local_env()

NVIDIA_API_KEY = os.environ.get("NVIDIA_API_KEY", "")
NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"
# NVIDIA's documented OpenAI-compatible model identifier. It can be
# overridden for a self-hosted compatible NIM deployment when required.
NVIDIA_MODEL = os.environ.get("NVIDIA_MODEL", "meta/llama-3.1-8b-instruct")

# Validation bounds are keyed by spec-name fragments and unit, which keeps the
# checks aligned with the current canonical match-rule names and avoids the old
# exact-key lookup bug where shorter aliases were ignored.
_SPEC_VALIDATION_RULES = (
    (("dropout voltage",), "mV", 1, 1000),
    (("output noise",), "uV", 1, 100000),
    (("output ripple",), "mV", 1, 1000),
    (("switching frequency",), "kHz", 10, 10000),
    (("clock frequency",), "MHz", 1, 1000),
    (("thermal resistance",), "C/W", 0.1, 500),
    (("current - output",), "mA", 0.001, 100000),
    (("current - quiescent",), "mA", 0.001, 10000),
    (("voltage - output", "voltage - input", "voltage - supply"), "V", 0.1, 100),
    (("memory size",), "bits", 1, 1e9),
    (("data rate",), "Mbps", 1, 10000),
    (("frequency",), "Hz", 1e-3, 1e9),
    (("psrr",), "dB", 10, 120),
    (("s/n ratio",), "dB", 10, 150),
    (("thd + noise",), "%", 0.001, 100),
    (("efficiency",), "%", 1, 100),
)


# ═══════════════════════════════════════════
# Dynamic Prompt Generation from match_rules
# ═══════════════════════════════════════════
def _build_category_prompt(category: str) -> str:
    """
    Build extraction prompt from match_rules specs for this category.
    This replaces hardcoded prompts and ensures ALL required specs are extracted.
    """
    required_specs = _get_required_specs(category)

    if not required_specs:
        # Fallback to generic prompt if match_rules unavailable
        return """Extract ALL electrical specifications from this IC datasheet.
Include: voltages, currents, power, frequency, timing, temperature ratings,
noise, PSRR, efficiency, and any other measurable parameters.
Also extract PIN ASSIGNMENTS (pin number, name, function)."""

    # Build spec list for prompt
    spec_list = "\n".join(f"- {spec}" for spec in sorted(required_specs))

    return f"""Extract ONLY these specs from the {category} datasheet:
{spec_list}

Rules:
- Return ONLY specs that exist in the datasheet
- Preserve the value WITH its unit (e.g., "160 mV", "32 Mbit")
- Use typical values when typical, min, and max are available
- For ranges, extract both min and max as separate specs if labeled differently
- DO NOT guess or invent specs not explicitly in the datasheet
- DO NOT include specs not in the list above
- Also extract PIN ASSIGNMENTS (pin number, name, function)"""


# ═══════════════════════════════════════════
# Validation Layer
# ═══════════════════════════════════════════
def _try_parse_numeric(val_str: str, target_unit: str = "") -> Optional[float]:
    """Extract a number and normalize common SI prefixes to target_unit."""
    if not val_str or not isinstance(val_str, str):
        return None

    match = re.search(
        r'([-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)\s*([µunmkKMG]?)([A-Za-zΩ%]+)?',
        val_str,
    )
    if match:
        try:
            value = float(match.group(1))
            source_prefix = match.group(2) or ""
            source_base = (match.group(3) or "").casefold().rstrip("s")
            target_prefix = target_unit[:1] if target_unit[:1] in "µunmkKMG" else ""
            target_base = target_unit[len(target_prefix):].casefold().rstrip("s")
            factors = {
                "": 1.0, "m": 1e-3, "µ": 1e-6, "u": 1e-6,
                "n": 1e-9, "k": 1e3, "K": 1e3,
                "M": 1e6, "G": 1e9,
            }
            source_factor = factors.get(source_prefix, 1.0)
            target_factor = factors.get(target_prefix, 1.0)
            if target_unit and source_base and source_base == target_base:
                return value * source_factor / target_factor
            return value * source_factor
        except ValueError:
            return None
    return None


def _validate_spec(spec_name: str, spec_value: str) -> Tuple[bool, Optional[str]]:
    """
    Validate extracted spec against sanity checks.
    Returns (is_valid, error_message_or_none)
    """
    if not spec_value or not isinstance(spec_value, str):
        return False, "Empty or invalid value"

    normalized_name = re.sub(r"\s+", " ", spec_name).casefold()
    validation_rule = next(
        (rule for rule in _SPEC_VALIDATION_RULES
         if any(fragment in normalized_name for fragment in rule[0])),
        None,
    )
    target_unit = validation_rule[1] if validation_rule else ""
    numeric_val = _try_parse_numeric(spec_value, target_unit)
    if numeric_val is None:
        # Some specs can be non-numeric (strings like "SPI", "Buck", etc)
        return True, None

    if validation_rule:
        _, _, min_val, max_val = validation_rule
        if not (min_val <= numeric_val <= max_val):
            return False, f"Value {numeric_val} outside valid range {min_val}-{max_val} {target_unit}".strip()

    # Generic sanity: value should not be obviously wrong (e.g., -500V)
    if numeric_val < 0 and "negative" not in spec_name.lower():
        # Allowed for some specs: negative temps, offset voltages
        if "temperature" not in spec_name.lower() and "offset" not in spec_name.lower():
            return False, f"Unexpected negative value: {numeric_val}"

    return True, None


def _fill_missing_specs_with_regex(category: str, specs: Dict, datasheet_text: str) -> Dict:
    """
    For specs missing from LLM extraction, try regex fallback.
    """
    try:
        from finder_extras.datasheet_parser import DatasheetParser
        parser = DatasheetParser()

        # Parse as pages (simple split for now)
        page_texts = datasheet_text.split("\n\n")
        regex_specs = parser.extract_specs(page_texts, category=category)

        # Add specs that LLM missed
        for spec_name, value in regex_specs.items():
            canonical = _canonical_spec_name(spec_name, category)
            if canonical and canonical not in specs:
                is_valid, _ = _validate_spec(canonical, value)
                if is_valid:
                    specs[canonical] = value
                    log.debug("  Filled missing spec %s=%s via regex", canonical, value)
    except ImportError:
        log.debug("Regex fallback unavailable")
    except Exception as e:
        log.debug("Regex fallback failed: %s", e)

    return specs


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
                if _is_valid_datasheet(pdf_path, mpn):
                    return pdf_path, "pdf"
                log.warning("  Removing invalid cached datasheet: %s", pdf_path)
        try:
            os.remove(pdf_path)
        except OSError:
            pass

    if os.path.exists(html_path) and os.path.getsize(html_path) > 1000:
        with open(html_path, "r", encoding="utf-8", errors="replace") as handle:
            cached_html = handle.read()
        cached_pdf = _download_embedded_pdf(cached_html, pdf_path, mpn)
        if cached_pdf:
            return cached_pdf, "pdf"
        if len(extract_html_text(cached_html)) >= 100:
            return html_path, "html"
        log.warning("  Removing unusable cached HTML: %s", html_path)
        try:
            os.remove(html_path)
        except OSError:
            pass

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
            if not _is_valid_datasheet(pdf_path, mpn):
                log.warning("  Rejecting non-datasheet PDF for %s: %s", mpn, url)
                os.remove(pdf_path)
                return None, None
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
                            if not _is_valid_datasheet(pdf_path, mpn):
                                os.remove(pdf_path)
                                continue
                            log.info("  Downloaded real PDF (%d KB)", len(pdf_resp.content) // 1024)
                            return pdf_path, "pdf"
                    except Exception:
                        pass

            # Embedded PDFs existed but were not for this MPN. Do not feed
            # the wrapper page to the LLM; the caller must find another URL.
            log.warning("  No matching datasheet PDF found in HTML for %s", mpn)
            return None, None

        # Unknown content type
        with open(pdf_path, "wb") as f:
            f.write(content)
        return pdf_path, "pdf"

    except Exception as exc:
        log.debug("Download failed %s: %s", mpn, exc)
        return None, None


def _download_embedded_pdf(html_text, pdf_path, mpn):
    """Resolve and validate a PDF URL embedded in a cached HTML wrapper."""
    patterns = [
        r'(https?://wmsc\.lcsc\.com/[^"\']+\.pdf)',
        r'"pdfUrl"\s*:\s*"(https?://[^"]+\.pdf)"',
        r'src="(https?://[^"\']+\.pdf[^"\']*)"',
        r'href="(https?://[^"\']+\.pdf[^"\']*)"',
    ]
    for pattern in patterns:
        match = re.search(pattern, html_text, re.IGNORECASE)
        if not match:
            continue
        try:
            response = requests.get(
                match.group(1), timeout=30, verify=False,
                headers={"User-Agent": "Mozilla/5.0"},
            )
            if response.status_code == 200 and response.content[:5] == b"%PDF-":
                with open(pdf_path, "wb") as handle:
                    handle.write(response.content)
                if _is_valid_datasheet(pdf_path, mpn):
                    log.info("  Resolved cached HTML to validated PDF for %s", mpn)
                    return pdf_path
                os.remove(pdf_path)
        except Exception as exc:
            log.debug("Embedded PDF resolution failed for %s: %s", mpn, exc)
    return None


def _is_valid_datasheet(pdf_path, mpn):
    """Reject compliance sheets, cover pages, and empty/scanned PDFs."""
    if not PYMUPDF_OK:
        return True
    try:
        doc = fitz.open(pdf_path)
        text = "\n".join(page.get_text() for page in doc)
        pages = len(doc)
        doc.close()
    except Exception:
        return False

    normalized = re.sub(r"[^a-z0-9]+", " ", text.lower())
    raw_tokens = [token for token in re.findall(r"[a-z0-9]+", mpn.lower()) if len(token) >= 3]
    mpn_tokens = set()
    if raw_tokens:
        # Use only the first MPN token; later tokens are often package suffixes.
        family = raw_tokens[0]
        mpn_tokens.add(family)
        core = re.match(r"[a-z]+[0-9]+", family)
        if core:
            mpn_tokens.add(core.group(0))
        for suffix in ("k", "a", "b", "c"):
            if family.endswith(suffix) and len(family) > len(suffix) + 3:
                mpn_tokens.add(family[:-1])
    has_mpn = any(token in normalized for token in mpn_tokens)
    compliance_only = any(term in normalized for term in (
        "environmental compliance statement",
        "material declaration",
        "rohs declaration",
        "reach declaration",
    )) and not any(term in normalized for term in (
        "electrical characteristics", "absolute maximum", "pin configuration",
        "application circuit", "block diagram", "output voltage",
    ))
    electrical_terms = sum(normalized.count(term) for term in (
        "electrical characteristics", "absolute maximum", "input voltage",
        "output voltage", "operating temperature", "pin configuration",
        "application circuit", "typical characteristics", "ordering information",
    ))
    valid = (
        pages >= 1
        and len(text) >= 1000
        and has_mpn
        and not compliance_only
        and electrical_terms >= 1
    )
    if not valid:
        log.warning(
            "  Invalid datasheet candidate %s: pages=%d chars=%d has_mpn=%s "
            "electrical_terms=%d compliance_only=%s",
            mpn, pages, len(text), has_mpn, electrical_terms, compliance_only,
        )
    return valid


def extract_pdf_text(pdf_path, max_pages=80):
    if not PYMUPDF_OK:
        return ""
    try:
        doc = fitz.open(pdf_path)
        pages = [doc[i].get_text() for i in range(min(max_pages, len(doc)))]
        doc.close()
        return "\n\n".join(pages)
    except Exception:
        return ""


def _datasheet_context(text: str, mpn: str, category: str, limit: int = 10000) -> str:
    """Keep the pages most likely to contain rated specs, not just page one.

    Many datasheets place electrical-characteristics tables after application
    notes, so a first-N-character truncation was systematically omitting the
    fields required by the replacement rules.
    """
    if len(text) <= limit:
        return text
    labels = {"electrical characteristics", "recommended operating",
              "absolute maximum", "ordering information", "pin configuration"}
    labels.update(name.casefold() for name in _get_required_specs(category))
    pages = re.split(r"\n\s*\n", text)
    selected = []
    used = 0
    for page in pages:
        normalized = page.casefold()
        if any(label in normalized for label in labels):
            excerpt = page[:5000]
            if used + len(excerpt) > limit:
                break
            selected.append(excerpt)
            used += len(excerpt)
    if not selected:
        return text[:limit]
    return "\n\n".join(selected)


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
# LLM Client — NVIDIA NIM
# ═══════════════════════════════════════════
def _get_clients():
    """
    Return the configured NVIDIA NIM OpenAI-compatible client.
    """
    if not OPENAI_OK:
        log.warning("openai package not installed. Run: python -m pip install openai")
        return []

    providers = []
    if NVIDIA_API_KEY:
        providers.append(("nvidia", NVIDIA_BASE_URL, NVIDIA_API_KEY, NVIDIA_MODEL))

    clients = []
    for provider, base_url, key, model in providers:
        try:
            kwargs = {
                "base_url": base_url,
                "api_key": key,
                "max_retries": 0,
                "timeout": 30.0,
            }
            if HTTPX_OK:
                kwargs["http_client"] = httpx.Client(verify=False, timeout=30.0)
            clients.append((provider, OpenAI(**kwargs), model))
        except Exception as exc:
            log.warning("Failed to create %s client: %s", provider, exc)
    if not clients:
        log.warning("Set NVIDIA_API_KEY")
    return clients


# ═══════════════════════════════════════════
# LLM Extraction
# ═══════════════════════════════════════════
def extract_with_llm(text, mpn, category="", package=""):
    """Use NVIDIA NIM to extract specs and pin assignments from datasheet text."""
    clients = _get_clients()
    if not clients:
        return {}, {}

    # Use dynamic prompt from match_rules
    cat_prompt = _build_category_prompt(category)

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
        "- Preserve every numeric value's unit "
        '(e.g. "160 mV", not just "160")\n'
        "- Use typical values when both typical and max exist\n"
        "- Pin functions must be one of: power_input, power_output, "
        "ground, enable, feedback, no_connect, signal, other\n"
        "- If a spec is not found, omit it entirely\n"
        "- Do NOT guess or hallucinate values not in the text\n"
        "- Do NOT invent specs not explicitly listed"
    )

    user_msg = (
        "Part: {}\nCategory: {}\nPackage: {}\n\n"
        "{}\n\nDATASHEET TEXT:\n{}"
    ).format(mpn, category, package, cat_prompt, text)

    for provider, client, model in clients:
        try:
            request_args = {
                "model": model,
                "messages": [
                    {"role": "system", "content": system_msg},
                    {"role": "user", "content": user_msg},
                ],
                "temperature": 0.1,
            }
            request_args["max_tokens"] = 700

            response = client.chat.completions.create(**request_args)

            raw = response.choices[0].message.content
            if raw is None:
                log.warning("%s returned no content for %s (finish_reason=%s)",
                            provider, mpn, response.choices[0].finish_reason)
                continue
            raw = raw.strip()
            log.info("  RAW %s RESPONSE for %s: %s", provider, mpn, raw[:800])

            if not raw:
                log.warning("%s returned an empty response for %s", provider, mpn)
                continue

            # Strip markdown code blocks if present
            if "```" in raw:
                match = re.search(r"```(?:json)?\s*(.*?)```", raw, re.DOTALL)
                if match:
                    raw = match.group(1).strip()

            data = json.loads(raw)
            specs = {}
            for k, v in data.get("specs", {}).items():
                if v is not None and str(v).strip():
                    canonical = _canonical_spec_name(k, category)
                    # Do not allow a model to create arbitrary database keys.
                    # A value may only be stored when it maps to a current
                    # replacement-rule field for this category.
                    if not canonical:
                        log.debug("  Ignored non-rule LLM spec %s for %s", k, category)
                        continue
                    val_str = str(v).strip()
                    is_valid, error_msg = _validate_spec(canonical, val_str)
                    if is_valid:
                        specs[canonical] = val_str
                    else:
                        log.debug("  Rejected spec %s=%s: %s", canonical, val_str, error_msg)

            pins = data.get("pins", {})

            log.info("%s extracted %d specs, %d pins for %s",
                     provider, len(specs), len(pins), mpn)
            return specs, pins

        except json.JSONDecodeError as exc:
            log.warning("%s returned invalid JSON for %s: %s", provider, mpn, exc)
        except Exception as exc:
            log.warning("%s extraction failed for %s: %s", provider, mpn, exc)

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

        text = _datasheet_context(text, mpn, category)
        log.info("  Extracted %d selected chars from %s (%s)", len(text), mpn, file_type)
        log.info("  --- TEXT PREVIEW for %s ---\n%s\n  --- END PREVIEW ---", mpn, text[:1500])
        if file_type == "pdf" and len(text) < 3000:
            log.warning(
                "  Suspicious datasheet for %s: only %d text chars; "
                "the URL may point to a cover/compliance or scanned PDF",
                mpn, len(text),
            )

        # Use LLM to extract specs (same call for PDF or HTML text)
        specs, pins = extract_with_llm(text, mpn, category, package)

        # Always attempt deterministic extraction for fields missed by the
        # model.  The previous <3 threshold left partly enriched components
        # permanently missing required match fields.
        specs = _fill_missing_specs_with_regex(category, specs, text)

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
