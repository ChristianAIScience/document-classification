"""Translate database write conflicts into consistent API responses."""

from collections.abc import Iterator
from contextlib import contextmanager

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

DEFAULT_DETAIL = "Änderung konnte wegen eines Datenbankkonflikts nicht gespeichert werden."


@contextmanager
def write_or_conflict(db: Session, detail: str = DEFAULT_DETAIL) -> Iterator[None]:
    """Run writes (including intermediate flushes) and commit; integrity errors become 409 + rollback."""
    try:
        yield
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail=detail) from None


def commit_or_conflict(db: Session, detail: str = DEFAULT_DETAIL) -> None:
    with write_or_conflict(db, detail):
        pass
