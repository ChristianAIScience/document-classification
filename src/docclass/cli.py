"""Command line: uv run docclass process <pdf|ordner>... [--save]"""

import argparse
import json
import sys
from pathlib import Path

from sqlalchemy import select


def _pdfs(paths: list[Path]) -> list[Path]:
    return [p for path in paths for p in (sorted(path.glob("*.pdf")) if path.is_dir() else [path])]


def process(paths: list[Path], save: bool) -> None:
    from docclass.pipeline.service import process_pdf

    session = None
    if save:
        from docclass.db.session import SessionLocal
        session = SessionLocal()

    for pdf in _pdfs(paths):
        ergebnis = process_pdf(pdf)
        ausgabe = {
            "datei": pdf.name,
            "klassifikation": ergebnis.klassifikation.dokumententyp,
            "konfidenz": ergebnis.klassifikation.konfidenz,
            "warnungen": ergebnis.warnungen,
            "dokument": ergebnis.dokument.model_dump(mode="json"),
        }
        if session is not None:
            from docclass.db import models
            from docclass.db.repository import create_dokument
            vorhanden = session.scalar(
                select(models.Dokument.id).where(models.Dokument.datei_hash == ergebnis.datei_hash)
            )
            if vorhanden is None:
                dokument = create_dokument(session, ergebnis.dokument, **ergebnis.db_meta())
                session.commit()
                vorhanden = dokument.id
            ausgabe["dokument_id"] = vorhanden
        print(json.dumps(ausgabe, ensure_ascii=False, indent=2))

    if session is not None:
        session.close()


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(prog="docclass")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("process", help="PDF(s) verarbeiten und Ergebnis als JSON ausgeben")
    p.add_argument("paths", nargs="+", type=Path, help="PDF-Dateien oder Ordner")
    p.add_argument("--save", action="store_true", help="Ergebnis in PostgreSQL speichern")
    args = parser.parse_args()
    if args.command == "process":
        process(args.paths, args.save)


if __name__ == "__main__":
    main()
