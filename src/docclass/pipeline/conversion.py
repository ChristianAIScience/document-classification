"""PDF → Markdown with Docling, cached on disk by file hash.

Uses the pypdfium2 backend: the default docling-parse backend ships a native DLL that Windows Smart App
Control blocks on this machine. Page header/footer ("furniture") is exported too, because the footer holds
IBAN, BIC, tax number and VAT ID.
"""

import hashlib
import re
from functools import cache
from pathlib import Path

from docling.backend.pypdfium2_backend import PyPdfiumDocumentBackend
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling_core.types.doc import ContentLayer

from docclass.core.config import settings

_WATERMARK = re.compile(r"^\s*MUSTER\s*$", re.MULTILINE)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@cache
def _converter(ocr: bool) -> DocumentConverter:
    # Building the converter loads layout models (slow); reuse it per process.
    options = PdfPipelineOptions(do_ocr=ocr)
    return DocumentConverter(format_options={
        InputFormat.PDF: PdfFormatOption(pipeline_options=options, backend=PyPdfiumDocumentBackend),
    })


def strip_watermark(markdown: str) -> str:
    """Remove the standalone "MUSTER" watermark line of the sample documents."""
    return _WATERMARK.sub("", markdown)


def pdf_to_markdown(path: Path, *, ocr: bool | None = None, use_cache: bool = True) -> str:
    ocr = settings.ocr_enabled if ocr is None else ocr
    cache_file = settings.markdown_cache_dir / f"{sha256_file(path)}{'-ocr' if ocr else ''}.md"
    if use_cache and cache_file.exists():
        return cache_file.read_text(encoding="utf-8")

    document = _converter(ocr).convert(path).document
    markdown = strip_watermark(document.export_to_markdown(
        included_content_layers={ContentLayer.BODY, ContentLayer.FURNITURE},
    ))
    if use_cache:
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        cache_file.write_text(markdown, encoding="utf-8")
    return markdown
