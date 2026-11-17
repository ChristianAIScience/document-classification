"""Rule-based document type classification on Docling Markdown.

Only type-specific phrases count: an invoice also prints "Angebots-Nr." (its quote reference), and the
sample footer mentions both "Rechnung" and "Angebot", so bare words are not signals.
"""

import re
from dataclasses import dataclass

from docclass.schemas import Dokumententyp

_SIGNALS: dict[Dokumententyp, tuple[re.Pattern[str], ...]] = {
    "rechnung": tuple(re.compile(p, re.IGNORECASE) for p in (
        r"\bRechnung\s+Nr\b",
        r"\bRechnungs-?(nr|nummer)\b",
        r"\bRechnungsdatum\b",
        r"\bLeistungs(datum|zeitraum)\b",
        r"\bzahlbar\b",
        r"\babzurechnen\b",
    )),
    "angebot": tuple(re.compile(p, re.IGNORECASE) for p in (
        r"\bAngebot\s+Nr\b",
        r"\bg[üu]ltig\s+bis\b",
        r"\bbieten\s+wir\b",
        r"\bIhren\s+Auftrag\s+freuen\b",
    )),
}


@dataclass(frozen=True)
class Klassifikation:
    dokumententyp: Dokumententyp | None
    konfidenz: float  # share of matched signals belonging to the chosen type; 0.0 if undecided
    treffer: dict[str, int]


def classify(markdown: str) -> Klassifikation:
    treffer = {typ: sum(bool(p.search(markdown)) for p in patterns) for typ, patterns in _SIGNALS.items()}
    total = sum(treffer.values())
    if total == 0 or treffer["rechnung"] == treffer["angebot"]:
        return Klassifikation(None, 0.0, treffer)
    typ: Dokumententyp = max(treffer, key=treffer.__getitem__)
    return Klassifikation(typ, treffer[typ] / total, treffer)
