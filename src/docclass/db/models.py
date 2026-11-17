"""ORM models for incoming documents: Lieferant → Dokument (Angebot/Rechnung) → Positionen.

Every schema change needs an Alembic migration (`uv run alembic revision --autogenerate -m "..."`).
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    JSON,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from docclass.db.session import Base

DOKUMENTENTYPEN = ("angebot", "rechnung")

Geld = Numeric(12, 2)
Menge = Numeric(12, 3)


class Lieferant(Base):
    """Absender eines Angebots oder einer Rechnung."""

    __tablename__ = "lieferanten"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    firmenname: Mapped[str] = mapped_column(String(200), index=True)
    strasse: Mapped[str | None] = mapped_column(String(200))
    plz: Mapped[str | None] = mapped_column(String(15))
    ort: Mapped[str | None] = mapped_column(String(100))
    steuernummer: Mapped[str | None] = mapped_column(String(50))
    ust_id: Mapped[str | None] = mapped_column(String(20), unique=True)
    iban: Mapped[str | None] = mapped_column(String(42))
    bic: Mapped[str | None] = mapped_column(String(11))
    telefon: Mapped[str | None] = mapped_column(String(50))
    email: Mapped[str | None] = mapped_column(String(120))

    dokumente: Mapped[list[Dokument]] = relationship(back_populates="lieferant")


class Dokument(Base):
    __tablename__ = "dokumente"
    __table_args__ = (
        CheckConstraint(
            f"dokumententyp IN {DOKUMENTENTYPEN}", name="dokumententyp",
        ),
        UniqueConstraint("lieferant_id", "dokumententyp", "nummer"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    lieferant_id: Mapped[int] = mapped_column(
        ForeignKey("lieferanten.id", ondelete="RESTRICT"), index=True,
    )
    dokumententyp: Mapped[str] = mapped_column(String(20))
    nummer: Mapped[str | None] = mapped_column(String(50), index=True)
    datum: Mapped[date | None] = mapped_column(Date)
    kundennummer: Mapped[str | None] = mapped_column(String(50))  # unsere Nr. beim Lieferanten

    # Angebot
    gueltig_bis: Mapped[date | None] = mapped_column(Date)

    # Rechnung
    leistung_beginn: Mapped[date | None] = mapped_column(Date)
    leistung_ende: Mapped[date | None] = mapped_column(Date)
    faellig_am: Mapped[date | None] = mapped_column(Date)
    angebot_nummer: Mapped[str | None] = mapped_column(String(50), index=True)
    angebot_datum: Mapped[date | None] = mapped_column(Date)
    angebot_id: Mapped[int | None] = mapped_column(
        ForeignKey("dokumente.id", ondelete="SET NULL"), index=True,
    )

    betreff: Mapped[str | None] = mapped_column(Text)
    leistungsort: Mapped[str | None] = mapped_column(String(200))

    netto: Mapped[Decimal | None] = mapped_column(Geld)
    mwst: Mapped[Decimal | None] = mapped_column(Geld)
    brutto: Mapped[Decimal | None] = mapped_column(Geld)
    skonto_betrag: Mapped[Decimal | None] = mapped_column(Geld)

    # Herkunft und Verarbeitung
    quelldatei: Mapped[str | None] = mapped_column(String(255))
    datei_hash: Mapped[str | None] = mapped_column(String(64), unique=True)
    markdown: Mapped[str | None] = mapped_column(Text)
    klassifikation_konfidenz: Mapped[float | None] = mapped_column(Float)
    extraktion_modell: Mapped[str | None] = mapped_column(String(100))
    prompt_version: Mapped[str | None] = mapped_column(String(20))
    warnungen: Mapped[list[str]] = mapped_column(JSON, default=list)  # Validierungswarnungen
    erstellt_am: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(),
    )

    lieferant: Mapped[Lieferant] = relationship(back_populates="dokumente")
    angebot: Mapped[Dokument | None] = relationship(remote_side=[id])
    positionen: Mapped[list[DokumentPosition]] = relationship(
        back_populates="dokument",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="DokumentPosition.position",
    )


class DokumentPosition(Base):
    __tablename__ = "dokument_positionen"
    __table_args__ = (UniqueConstraint("dokument_id", "position"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    dokument_id: Mapped[int] = mapped_column(
        ForeignKey("dokumente.id", ondelete="CASCADE"), index=True,
    )
    position: Mapped[int]
    beschreibung: Mapped[str | None] = mapped_column(Text)
    menge: Mapped[Decimal | None] = mapped_column(Menge)
    einheit: Mapped[str | None] = mapped_column(String(50))
    einzelpreis: Mapped[Decimal | None] = mapped_column(Geld)
    gesamtpreis: Mapped[Decimal | None] = mapped_column(Geld)

    dokument: Mapped[Dokument] = relationship(back_populates="positionen")
