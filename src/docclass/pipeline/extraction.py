"""LLM field extraction from Docling Markdown into `ExtractedDokument`.

Bump PROMPT_VERSION whenever the prompt or the schema descriptions change; it is stored per document and
logged with every evaluation run.
"""

from functools import cache

from langchain_core.runnables import Runnable
from langchain_openai import ChatOpenAI

from docclass.core.config import settings
from docclass.schemas import ExtractedDokument

PROMPT_VERSION = "v1"

SYSTEM_PROMPT = """\
Du extrahierst strukturierte Daten aus einem deutschen Angebot oder einer Rechnung.
Der Text wurde per OCR/Docling aus einem PDF erzeugt und kann doppelte oder abgeschnittene Passagen enthalten.

Regeln:
- Der Lieferant ist der ABSENDER des Dokuments (Briefkopf, Fußzeile mit IBAN/USt-IdNr.), nicht der Empfänger.
- Übernimm Werte exakt wie gedruckt. Erfinde nichts; fehlende oder nicht zutreffende Felder sind null.
- Beträge und Mengen als Dezimalzahl mit Punkt ohne Tausendertrennzeichen (z. B. "4297.23", "1.5").
- Datumswerte im Format YYYY-MM-DD.
- Positionen: eine pro Tabellenzeile mit Positionsnummer; Summenzeilen (Netto, USt., Gesamt) sind keine Positionen.
- Bei einer Rechnung: angebot_nummer/angebot_datum sind das referenzierte Angebot, leistung_ende ist das
  Leistungsdatum (bzw. Ende des Leistungszeitraums), leistung_beginn nur bei einem Zeitraum.
- Bei einem Angebot bleiben Rechnungsfelder null.
"""


@cache
def _chain() -> Runnable:
    if settings.openai_api_key is None:
        raise RuntimeError("OPENAI_API_KEY ist nicht gesetzt; die LLM-Extraktion ist nicht verfügbar.")
    llm = ChatOpenAI(model=settings.llm_model, temperature=0, api_key=settings.openai_api_key)
    return llm.with_structured_output(ExtractedDokument, method="json_schema")


def extract(markdown: str, *, dokumententyp_hint: str | None = None) -> ExtractedDokument:
    """Extract all fields; an optional rule-based type hint is passed to the model as context."""
    user = markdown
    if dokumententyp_hint:
        user = f"Vorklassifikation (regelbasiert): {dokumententyp_hint}\n\n{markdown}"
    return _chain().invoke([("system", SYSTEM_PROMPT), ("user", user)])
