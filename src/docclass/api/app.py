"""Create the FastAPI application and register its routers.

Run: uv run uvicorn docclass.api.app:app --reload
"""

from fastapi import FastAPI

from docclass.api.routers import dokumente, home, lieferanten, positionen

app = FastAPI(title="Document Classification Agent")
app.include_router(home.router)
app.include_router(lieferanten.router, prefix="/api")
app.include_router(dokumente.router, prefix="/api")
app.include_router(positionen.router, prefix="/api")
