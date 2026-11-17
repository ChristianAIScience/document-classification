"""Create the configured PostgreSQL database if missing: uv run python -m docclass.db.create_database.

Tables are managed by Alembic afterwards (`uv run alembic upgrade head`).
"""

import logging

import psycopg
from psycopg import sql

from docclass.core.config import settings

logger = logging.getLogger(__name__)


def create_postgresql_db() -> None:
    """Create the configured database if missing; propagate setup failures."""
    # CREATE DATABASE must run outside a transaction.
    with psycopg.connect(
        dbname="postgres",
        user=settings.DB_USER,
        password=settings.DB_PASSWORD.get_secret_value(),
        host=settings.DB_HOST,
        port=settings.DB_PORT,
        autocommit=True,
    ) as conn:
        exists = conn.execute(
            "SELECT 1 FROM pg_database WHERE datname = %s", (settings.DB_NAME,)
        ).fetchone()
        if exists:
            logger.info("Database '%s' already exists.", settings.DB_NAME)
            return
        conn.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(settings.DB_NAME)))
        logger.info("Created database '%s'.", settings.DB_NAME)


if __name__ == "__main__":
    logging.basicConfig(format="[%(levelname)s]: %(message)s", level=logging.INFO)
    create_postgresql_db()
