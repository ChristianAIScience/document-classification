"""Supplier endpoints and supplier-specific document listings."""

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import Response
from sqlalchemy import select

from docclass.api.deps import DbSession, get_lieferant_or_404
from docclass.api.errors import commit_or_conflict
from docclass.db import models
from docclass.db.repository import list_dokumente
from docclass.schemas import DokumentResponse, LieferantCreate, LieferantResponse

router = APIRouter(prefix="/lieferanten", tags=["Lieferanten"])


@router.post("", response_model=LieferantResponse, status_code=status.HTTP_201_CREATED)
def create_lieferant(lieferant: LieferantCreate, db: DbSession):
    existing = db.scalar(
        select(models.Lieferant.id).where(models.Lieferant.firmenname == lieferant.firmenname)
    )
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Firmenname existiert bereits.")
    new_lieferant = models.Lieferant(**lieferant.model_dump())
    db.add(new_lieferant)
    commit_or_conflict(db, detail="Lieferant konnte nicht erstellt werden. Die USt-ID existiert bereits.")
    db.refresh(new_lieferant)
    return new_lieferant


@router.get("", response_model=list[LieferantResponse])
def get_all_lieferanten(db: DbSession, firmenname: str | None = None, ust_id: str | None = None):
    """List suppliers with optional exact-match filters."""
    query = select(models.Lieferant).order_by(models.Lieferant.firmenname)
    if firmenname is not None:
        query = query.where(models.Lieferant.firmenname == firmenname)
    if ust_id is not None:
        query = query.where(models.Lieferant.ust_id == ust_id)
    return db.scalars(query).all()


@router.get("/{lieferant_id}", response_model=LieferantResponse)
def get_lieferant_by_id(lieferant_id: int, db: DbSession):
    return get_lieferant_or_404(lieferant_id, db)


@router.put("/{lieferant_id}", response_model=LieferantResponse)
def update_lieferant(lieferant_id: int, lieferant: LieferantCreate, db: DbSession):
    """Replace supplier details; omitted optional fields become None."""
    existing = get_lieferant_or_404(lieferant_id, db)
    for field, value in lieferant.model_dump().items():
        setattr(existing, field, value)
    commit_or_conflict(db)
    db.refresh(existing)
    return existing


@router.delete("/{lieferant_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_lieferant(lieferant_id: int, db: DbSession):
    lieferant = get_lieferant_or_404(lieferant_id, db)
    document_id = db.scalar(
        select(models.Dokument.id).where(models.Dokument.lieferant_id == lieferant_id).limit(1)
    )
    if document_id is not None:
        raise HTTPException(status_code=409, detail="Lieferant besitzt noch Dokumente.")
    db.delete(lieferant)
    commit_or_conflict(db)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{lieferant_id}/dokumente", response_model=list[DokumentResponse])
def get_lieferant_dokumente(lieferant_id: int, db: DbSession):
    get_lieferant_or_404(lieferant_id, db)
    return list_dokumente(db, lieferant_id=lieferant_id)
