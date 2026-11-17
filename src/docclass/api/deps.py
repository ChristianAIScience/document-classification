"""Shared database session dependency and resource lookups with HTTP errors."""

from typing import Annotated

from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session, selectinload

from docclass.db import models
from docclass.db.session import get_db

DbSession = Annotated[Session, Depends(get_db)]


def get_lieferant_or_404(lieferant_id: int, db: Session) -> models.Lieferant:
    lieferant = db.get(models.Lieferant, lieferant_id)
    if lieferant is None:
        raise HTTPException(status_code=404, detail="Lieferant wurde nicht gefunden.")
    return lieferant


def get_dokument_or_404(dokument_id: int, db: Session) -> models.Dokument:
    dokument = db.get(models.Dokument, dokument_id, options=(
        selectinload(models.Dokument.lieferant),
        selectinload(models.Dokument.positionen),
    ))
    if dokument is None:
        raise HTTPException(status_code=404, detail="Dokument wurde nicht gefunden.")
    return dokument
