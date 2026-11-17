"""Disk cache for LLM extraction in evaluation runs, so Task A and Task B share one set of LLM calls.

Use it as the extractor of the production pipeline: `process_pdf(pdf, extractor=cached_extract)`.
The key covers everything that shapes the LLM output (model, system prompt, output schema, prompt version,
type hint, Markdown), so editing any of them misses the cache instead of returning stale results.
"""

import hashlib
import json
import os

from docclass.core.config import settings
from docclass.pipeline import extraction
from docclass.pipeline.extraction import extract
from docclass.schemas import ExtractedDokument

CACHE_DIR = settings.data_dir / "extraction_cache"


def cache_key(markdown: str, dokumententyp_hint: str | None) -> str:
    teile = [
        settings.llm_model,
        extraction.PROMPT_VERSION,
        extraction.SYSTEM_PROMPT,
        json.dumps(ExtractedDokument.model_json_schema(), sort_keys=True, ensure_ascii=False),
        str(dokumententyp_hint),
        markdown,
    ]
    return hashlib.sha256("\x1f".join(teile).encode()).hexdigest()


def cached_extract(markdown: str, *, dokumententyp_hint: str | None = None) -> ExtractedDokument:
    path = CACHE_DIR / f"{cache_key(markdown, dokumententyp_hint)}.json"
    if path.exists():
        return ExtractedDokument.model_validate_json(path.read_text(encoding="utf-8"))
    dokument = extract(markdown, dokumententyp_hint=dokumententyp_hint)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    # Write-then-rename: an interrupted run never leaves a truncated entry under the final name.
    tmp = path.with_suffix(f".{os.getpid()}.tmp")
    tmp.write_text(dokument.model_dump_json(), encoding="utf-8")
    try:
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)
    return dokument
