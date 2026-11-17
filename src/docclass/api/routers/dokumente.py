"""Document creation, upload, replacement, and retrieval, including offers and invoices."""

import hashlib

import openai
from fastapi import APIRouter, HTTPException, UploadFile, status
from fastapi.responses import Response
from pydantic import ValidationError
from sqlalchemy import select

from docclass.api.deps import DbSession, get_dokument_or_404
from docclass.api.errors import commit_or_conflict, write_or_conflict
from docclass.core.config import settings
from docclass.db import models
from docclass.db.repository import apply_dokument, create_dokument, list_dokumente
from docclass.pipeline.deviation import find_abweichungen
from docclass.schemas import Abweichung, DokumentCreate, Dokumententyp, DokumentResponse, PositionBase

router = APIRouter(tags=["Dokumente"])

DUPLIKAT = "Dokument existiert bereits (gleiche Nummer beim selben Lieferanten oder gleiche Datei)."


@router.post("/dokumente", response_model=DokumentResponse, status_code=status.HTTP_201_CREATED)
def create_dokument_manual(dokument: DokumentCreate, db: DbSession):
    """Create a document from already structured data; the supplier is matched or created."""
    with write_or_conflict(db, detail=DUPLIKAT):
        new_dokument = create_dokument(db, dokument)
    db.refresh(new_dokument)
    return new_dokument


@router.post("/dokumente/upload", response_model=DokumentResponse, status_code=status.HTTP_201_CREATED)
def upload_dokument(datei: UploadFile, db: DbSession):
    """Convert, classify, extract and store a PDF. Uploading the same file twice returns 409.

    Synchronous on purpose: Docling is CPU-bound and FastAPI runs sync endpoints in a thread pool.
    """
    inhalt = datei.file.read()
    if not inhalt.startswith(b"%PDF"):
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="Nur PDF-Dateien.")

    datei_hash = hashlib.sha256(inhalt).hexdigest()
    vorhanden = db.scalar(select(models.Dokument.id).where(models.Dokument.datei_hash == datei_hash))
    if vorhanden is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Datei wurde bereits verarbeitet (Dokument {vorhanden}).",
        )

    settings.uploads_dir.mkdir(parents=True, exist_ok=True)
    pfad = settings.uploads_dir / f"{datei_hash}.pdf"
    pfad.write_bytes(inhalt)

    from docclass.pipeline import service  # lazy: Docling import takes seconds

    try:
        ergebnis = service.process_pdf(pfad, quelldatei=datei.filename)
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Extraktion ungültig: {exc.error_count()} Fehler.",
        ) from exc
    except RuntimeError as exc:  # e.g. missing API key
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    except openai.APIError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail=f"LLM-Extraktion fehlgeschlagen: {exc.message}",
        ) from exc

    with write_or_conflict(db, detail=DUPLIKAT):
        new_dokument = create_dokument(db, ergebnis.dokument, **ergebnis.db_meta())
    db.refresh(new_dokument)
    return new_dokument


@router.get("/dokumente", response_model=list[DokumentResponse])
def get_all_dokumente(
    db: DbSession,
    dokumententyp: Dokumententyp | None = None,
    lieferant_id: int | None = None,
    nummer: str | None = None,
    angebot_nummer: str | None = None,
):
    """List documents with optional exact-match filters."""
    return list_dokumente(
        db, dokumententyp=dokumententyp, lieferant_id=lieferant_id,
        nummer=nummer, angebot_nummer=angebot_nummer,
    )


@router.get("/dokumente/{dokument_id}", response_model=DokumentResponse)
def get_dokument_by_id(dokument_id: int, db: DbSession):
    return get_dokument_or_404(dokument_id, db)


@router.get("/dokumente/{dokument_id}/abweichungen", response_model=list[Abweichung])
def get_abweichungen(dokument_id: int, db: DbSession):
    """Compare an invoice with its linked quote; computed from the stored positions on every call."""
    rechnung = get_dokument_or_404(dokument_id, db)
    if rechnung.dokumententyp != "rechnung":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Abweichungen gibt es nur für Rechnungen.")
    if rechnung.angebot_id is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Kein Angebot mit Nummer '{rechnung.angebot_nummer}' für diesen Lieferanten gespeichert.",
        )
    angebot = get_dokument_or_404(rechnung.angebot_id, db)
    return find_abweichungen(
        [PositionBase.model_validate(p) for p in angebot.positionen],
        [PositionBase.model_validate(p) for p in rechnung.positionen],
    )


@router.put("/dokumente/{dokument_id}", response_model=DokumentResponse)
def update_dokument(dokument_id: int, dokument: DokumentCreate, db: DbSession):
    """Replace document content and all positions (e.g. manual correction); metadata is kept."""
    with write_or_conflict(db, detail=DUPLIKAT):
        existing = apply_dokument(db, get_dokument_or_404(dokument_id, db), dokument)
    db.refresh(existing)
    return existing


@router.delete("/dokumente/{dokument_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_dokument(dokument_id: int, db: DbSession):
    db.delete(get_dokument_or_404(dokument_id, db))
    commit_or_conflict(db)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/angebote", response_model=list[DokumentResponse])
def get_all_angebote(db: DbSession):
    return list_dokumente(db, dokumententyp="angebot")


@router.get("/angebote/{nummer}", response_model=list[DokumentResponse])
def get_angebote_by_nummer(nummer: str, db: DbSession):
    """Quote numbers are only unique per supplier, so return every match."""
    return list_dokumente(db, dokumententyp="angebot", nummer=nummer)


@router.get("/rechnungen", response_model=list[DokumentResponse])
def get_all_rechnungen(db: DbSession):
    return list_dokumente(db, dokumententyp="rechnung")


@router.get("/rechnungen/{nummer}", response_model=list[DokumentResponse])
def get_rechnungen_by_nummer(nummer: str, db: DbSession):
    """Invoice numbers are only unique per supplier, so return every match."""
    return list_dokumente(db, dokumententyp="rechnung", nummer=nummer)
