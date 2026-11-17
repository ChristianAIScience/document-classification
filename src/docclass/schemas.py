"""API and extraction schemas.

`ExtractedDokument` is also the structured-output schema for the LLM, so field descriptions double as
extraction instructions. Money and quantities are `Decimal`, exposed as strings in the JSON schema;
German formats (`4.297,23`, `25.06.2026`) are normalized on input.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, WithJsonSchema

Dokumententyp = Literal["angebot", "rechnung"]


def parse_decimal(value):
    """Accept `1234.56`, `1.234,56` and `1234,56` (also with € and spaces)."""
    if isinstance(value, str):
        text = value.replace("€", "").replace("EUR", "").replace(" ", "").strip()
        if "," in text:
            text = text.replace(".", "").replace(",", ".")
        return text
    return value


def parse_date(value):
    """Accept ISO dates and German `DD.MM.YYYY`."""
    if isinstance(value, str) and value.count(".") == 2:
        day, month, year = value.strip().split(".")
        return f"{year}-{int(month):02d}-{int(day):02d}"
    return value


Betrag = Annotated[
    Decimal,
    BeforeValidator(parse_decimal),
    WithJsonSchema({"type": "string", "description": "Dezimalzahl mit Punkt, z. B. 4297.23"}),
]
Datum = Annotated[
    date,
    BeforeValidator(parse_date),
    WithJsonSchema({"type": "string", "description": "Datum im Format YYYY-MM-DD"}),
]


class LieferantBase(BaseModel):
    """Absender des Dokuments (nicht der Empfänger)."""

    firmenname: str = Field(min_length=1, max_length=200)
    strasse: str | None = Field(default=None, max_length=200)
    plz: str | None = Field(default=None, max_length=15)
    ort: str | None = Field(default=None, max_length=100)
    steuernummer: str | None = Field(default=None, max_length=50)
    ust_id: str | None = Field(default=None, max_length=20, description="USt-IdNr., z. B. DE123456789")
    iban: str | None = Field(default=None, max_length=42, description="IBAN wie gedruckt")
    bic: str | None = Field(default=None, max_length=11)
    telefon: str | None = Field(default=None, max_length=50)
    email: str | None = Field(default=None, max_length=120)


class LieferantCreate(LieferantBase):
    pass


class LieferantResponse(LieferantBase):
    id: int

    model_config = ConfigDict(from_attributes=True)


class PositionBase(BaseModel):
    position: int = Field(ge=1, description="Positionsnummer wie im Dokument gedruckt")
    beschreibung: str | None = None
    menge: Betrag | None = None
    einheit: str | None = Field(default=None, max_length=50, description="z. B. Std., Stk., m², Pauschale")
    einzelpreis: Betrag | None = None
    gesamtpreis: Betrag | None = None

    model_config = ConfigDict(from_attributes=True)


class PositionResponse(PositionBase):
    pass


class DokumentBase(BaseModel):
    """Inhalt eines Angebots oder einer Rechnung; nicht zutreffende Felder bleiben null."""

    dokumententyp: Dokumententyp
    nummer: str | None = Field(default=None, max_length=50, description="Angebots- bzw. Rechnungsnummer")
    datum: Datum | None = Field(default=None, description="Angebots- bzw. Rechnungsdatum")
    kundennummer: str | None = Field(default=None, max_length=50)

    gueltig_bis: Datum | None = Field(default=None, description="Nur Angebot: gültig bis")

    leistung_beginn: Datum | None = Field(
        default=None, description="Nur Rechnung: Beginn des Leistungszeitraums, falls ein Zeitraum angegeben ist",
    )
    leistung_ende: Datum | None = Field(
        default=None, description="Nur Rechnung: Leistungsdatum bzw. Ende des Leistungszeitraums",
    )
    faellig_am: Datum | None = Field(default=None, description="Nur Rechnung: Zahlungsziel/fällig am")
    angebot_nummer: str | None = Field(
        default=None, max_length=50, description="Nur Rechnung: Nummer des referenzierten Angebots",
    )
    angebot_datum: Datum | None = Field(default=None, description="Nur Rechnung: Datum des referenzierten Angebots")

    betreff: str | None = Field(default=None, description="Bauvorhaben / Betreff")
    leistungsort: str | None = None

    netto: Betrag | None = None
    mwst: Betrag | None = None
    brutto: Betrag | None = None
    skonto_betrag: Betrag | None = Field(default=None, description="Skontobetrag, falls Skonto angeboten wird")

    lieferant: LieferantBase
    positionen: list[PositionBase] = Field(default_factory=list)


class ExtractedDokument(DokumentBase):
    """Extraction output without database IDs."""


class DokumentCreate(DokumentBase):
    pass


class DokumentResponse(DokumentBase):
    id: int
    lieferant_id: int
    lieferant: LieferantResponse
    angebot_id: int | None
    quelldatei: str | None
    klassifikation_konfidenz: float | None
    extraktion_modell: str | None
    prompt_version: str | None
    warnungen: list[str]
    erstellt_am: datetime
    positionen: list[PositionResponse] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)
