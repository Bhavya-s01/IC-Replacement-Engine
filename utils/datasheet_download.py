"""Shared validated datasheet download adapter.

Callers receive a local PDF path only after the download helper has confirmed
both PDF content and plausible MPN identity. HTML wrappers are resolved by the
underlying downloader, but are never accepted as a datasheet URL result.
"""

from __future__ import annotations

from typing import Optional

from finder_extras.llm_parser import download_pdf


def download_validated_datasheet(
    url: str, mpn: str, download_dir: str = "datasheets"
) -> Optional[str]:
    """Return a validated local PDF path, or ``None`` for any invalid result."""
    path, file_type = download_pdf(url, mpn, download_dir=download_dir)
    return path if file_type == "pdf" else None
