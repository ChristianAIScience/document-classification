"""HTML entry page for the API."""

from html import escape

from fastapi import APIRouter
from fastapi.responses import HTMLResponse
from sqlalchemy import select

from docclass.api.deps import DbSession
from docclass.db import models

router = APIRouter()


@router.get("/", response_class=HTMLResponse, include_in_schema=False)
def home(db: DbSession):
    lieferanten = db.scalars(select(models.Lieferant).order_by(models.Lieferant.firmenname)).all()

    lieferanten_html = "".join(
        f"<li>{escape(lieferant.firmenname)}</li>"
        for lieferant in lieferanten
    )

    return f"""
    <html>
        <body>
            <h1>Document Classification Agent</h1>
            <h2>Alle Lieferanten ({len(lieferanten)})</h2>
            <ul>
                {lieferanten_html}
            </ul>
            <a href="/docs">API-Dokumentation</a>
        </body>
    </html>
    """
