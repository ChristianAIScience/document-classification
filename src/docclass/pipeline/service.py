"""End-to-end processing of one PDF: convert → classify → extract → validate. No database access."""

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from docclass.core.config import settings
from docclass.pipeline.classification import Klassifikation, classify
from docclass.pipeline.conversion import pdf_to_markdown, sha256_file
from docclass.pipeline.extraction import PROMPT_VERSION, extract
from docclass.pipeline.validation import validate
from docclass.schemas import ExtractedDokument

# Ab dieser Regel-Konfidenz gewinnt die regelbasierte Klassifikation gegen das LLM.
REGEL_KONFIDENZ_SCHWELLE = 0.75


@dataclass
class ProcessingResult:
    quelldatei: str
    datei_hash: str
    markdown: str
    klassifikation: Klassifikation
    dokument: ExtractedDokument
    warnungen: list[str]

    def db_meta(self) -> dict:
        """Processing metadata for `repository.create_dokument`."""
        return {
            "quelldatei": self.quelldatei,
            "datei_hash": self.datei_hash,
            "markdown": self.markdown,
            "klassifikation_konfidenz": self.klassifikation.konfidenz,
            "extraktion_modell": settings.llm_model,
            "prompt_version": PROMPT_VERSION,
            "warnungen": self.warnungen,
        }


def resolve_typ(klassifikation: Klassifikation, dokument: ExtractedDokument) -> tuple[ExtractedDokument, list[str]]:
    """Combine rule-based and LLM document type; disagreements become warnings."""
    regel = klassifikation.dokumententyp
    if regel is None or regel == dokument.dokumententyp:
        return dokument, []
    warnung = f"Klassifikation uneinig: Regeln={regel} ({klassifikation.konfidenz:.2f}), LLM={dokument.dokumententyp}"
    if klassifikation.konfidenz >= REGEL_KONFIDENZ_SCHWELLE:
        dokument = dokument.model_copy(update={"dokumententyp": regel})
    return dokument, [warnung]


def process_pdf(
    path: Path, *, quelldatei: str | None = None, extractor: Callable[..., ExtractedDokument] = extract,
) -> ProcessingResult:
    """`extractor` lets evaluation inject a cached LLM call while running exactly the production steps."""
    markdown = pdf_to_markdown(path)
    klassifikation = classify(markdown)
    dokument = extractor(markdown, dokumententyp_hint=klassifikation.dokumententyp)
    dokument, warnungen = resolve_typ(klassifikation, dokument)
    return ProcessingResult(
        quelldatei=quelldatei or path.name,
        datei_hash=sha256_file(path),
        markdown=markdown,
        klassifikation=klassifikation,
        dokument=dokument,
        warnungen=warnungen + validate(dokument),
    )
