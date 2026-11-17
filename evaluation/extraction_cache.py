"""Disk cache for LLM extraction in evaluation runs, so Task A and Task B share one set of LLM calls.

The key covers model, PROMPT_VERSION, type hint and Markdown; changing any of them misses the cache.
Delete data/extraction_cache/ to force fresh calls (e.g. after editing schema descriptions without a version bump).
"""

import hashlib
from pathlib import Path

from docclass.core.config import settings
from docclass.pipeline.classification import Klassifikation, classify
from docclass.pipeline.conversion import pdf_to_markdown
from docclass.pipeline.extraction import PROMPT_VERSION, extract
from docclass.pipeline.service import resolve_typ
from docclass.schemas import ExtractedDokument

CACHE_DIR = settings.data_dir / "extraction_cache"


def cached_extract(markdown: str, *, dokumententyp_hint: str | None = None) -> ExtractedDokument:
    key = hashlib.sha256(
        f"{settings.llm_model}|{PROMPT_VERSION}|{dokumententyp_hint}|{markdown}".encode()
    ).hexdigest()
    path = CACHE_DIR / f"{key}.json"
    if path.exists():
        return ExtractedDokument.model_validate_json(path.read_text(encoding="utf-8"))
    dokument = extract(markdown, dokumententyp_hint=dokumententyp_hint)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path.write_text(dokument.model_dump_json(), encoding="utf-8")
    return dokument


def extract_pdf(pdf: Path) -> tuple[Klassifikation, ExtractedDokument, list[str]]:
    """Production pipeline steps for one PDF, with cached LLM extraction: (rules, document, type warnings)."""
    markdown = pdf_to_markdown(pdf)
    klassifikation = classify(markdown)
    dokument, warnungen = resolve_typ(
        klassifikation, cached_extract(markdown, dokumententyp_hint=klassifikation.dokumententyp),
    )
    return klassifikation, dokument, warnungen
