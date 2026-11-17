"""Shared document queries and writes, independent of HTTP routing."""

from typing import Any

from sqlalchemy import select, update
from sqlalchemy.orm import Session, selectinload

from docclass.db import models
from docclass.schemas import DokumentBase, Dokumententyp, LieferantBase


def list_dokumente(
    db: Session,
    *,
    dokumententyp: Dokumententyp | None = None,
    lieferant_id: int | None = None,
    nummer: str | None = None,
    angebot_nummer: str | None = None,
) -> list[models.Dokument]:
    """Load matching documents, their suppliers, and positions in stable order."""
    query = select(models.Dokument).options(
        selectinload(models.Dokument.lieferant),
        selectinload(models.Dokument.positionen),
    )
    filters = (
        (models.Dokument.dokumententyp, dokumententyp),
        (models.Dokument.lieferant_id, lieferant_id),
        (models.Dokument.nummer, nummer),
        (models.Dokument.angebot_nummer, angebot_nummer),
    )
    for column, value in filters:
        if value is not None:
            query = query.where(column == value)
    return list(db.scalars(query.order_by(models.Dokument.id)).all())


def get_or_create_lieferant(db: Session, data: LieferantBase) -> models.Lieferant:
    """Match by USt-ID first, then by company name; existing details are preserved."""
    lieferant = None
    if data.ust_id:
        lieferant = db.scalar(select(models.Lieferant).where(models.Lieferant.ust_id == data.ust_id))
    if lieferant is None:
        lieferant = db.scalar(
            select(models.Lieferant).where(models.Lieferant.firmenname == data.firmenname).limit(1)
        )
    if lieferant is None:
        lieferant = models.Lieferant(**data.model_dump())
        db.add(lieferant)
    return lieferant


def apply_dokument(db: Session, dokument: models.Dokument, data: DokumentBase) -> models.Dokument:
    """Write content, supplier and the complete position list onto `dokument` (create or replace)."""
    for field, value in data.model_dump(exclude={"lieferant", "positionen"}).items():
        setattr(dokument, field, value)
    dokument.lieferant = get_or_create_lieferant(db, data.lieferant)
    if dokument.id is not None:
        # Delete old positions first; otherwise the inserts hit UNIQUE(dokument_id, position).
        dokument.positionen.clear()
        db.flush()
    dokument.positionen = [models.DokumentPosition(**p.model_dump()) for p in data.positionen]
    db.add(dokument)
    db.flush()
    _link_angebot(db, dokument)
    return dokument


def create_dokument(db: Session, data: DokumentBase, **meta: Any) -> models.Dokument:
    """Create a document with processing metadata (quelldatei, datei_hash, markdown, ...)."""
    return apply_dokument(db, models.Dokument(**meta), data)


def _link_angebot(db: Session, dokument: models.Dokument) -> None:
    """Connect invoices and quotes of the same supplier via the quote number, in either upload order."""
    if dokument.dokumententyp == "rechnung":
        dokument.angebot_id = None
        if dokument.angebot_nummer:
            dokument.angebot_id = db.scalar(select(models.Dokument.id).where(
                models.Dokument.dokumententyp == "angebot",
                models.Dokument.lieferant_id == dokument.lieferant_id,
                models.Dokument.nummer == dokument.angebot_nummer,
            ))
    elif dokument.nummer:
        db.execute(update(models.Dokument).where(
            models.Dokument.dokumententyp == "rechnung",
            models.Dokument.lieferant_id == dokument.lieferant_id,
            models.Dokument.angebot_nummer == dokument.nummer,
            models.Dokument.angebot_id.is_(None),
        ).values(angebot_id=dokument.id))
