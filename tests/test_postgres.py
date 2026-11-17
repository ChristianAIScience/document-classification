"""Integration tests against a real PostgreSQL. Opt-in: `uv run pytest -m postgres`.

Creates a throwaway database `docclass_test_<random>` on the server from .env, migrates it with Alembic, runs
the API tests from test_api.py on it plus PostgreSQL-specific checks, and drops it at the end. The development
database is never touched. Skips when PostgreSQL is unreachable.
"""

import uuid

import psycopg
import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from psycopg import sql
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

import docclass.db.models  # noqa: F401  registers tables on Base.metadata
from docclass.core.config import BASE_DIR, settings
from docclass.db.session import Base
from tests.test_api import *  # the same API tests, collected again here against PostgreSQL
from tests.test_api import payload
from tests.test_review_fixes import (  # noqa: F401
    test_changing_quote_number_unlinks_invoice,
    test_invoice_without_quote_number_has_clear_message,
)

pytestmark = pytest.mark.postgres


def _admin_connection() -> psycopg.Connection:
    return psycopg.connect(
        dbname="postgres", user=settings.DB_USER, password=settings.DB_PASSWORD.get_secret_value(),
        host=settings.DB_HOST, port=settings.DB_PORT, autocommit=True, connect_timeout=3,
    )


def _alembic_config(url) -> Config:
    config = Config()  # no ini file → env.py leaves pytest's logging alone
    config.set_main_option("script_location", str(BASE_DIR / "migrations"))
    config.attributes["url"] = url
    return config


@pytest.fixture(scope="session")
def pg_url():
    try:
        admin = _admin_connection()
    except psycopg.OperationalError as exc:
        pytest.skip(f"PostgreSQL nicht erreichbar: {exc}")
    name = f"docclass_test_{uuid.uuid4().hex[:8]}"
    with admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
    yield settings.database_url.set(database=name)
    with _admin_connection() as admin:
        admin.execute(sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(name)))


@pytest.fixture(scope="session")
def pg_engine(pg_url):
    command.upgrade(_alembic_config(pg_url), "head")
    engine = create_engine(pg_url, poolclass=NullPool)
    yield engine
    engine.dispose()


@pytest.fixture
def session_factory(pg_engine):
    """Overrides the SQLite fixture from conftest.py, so `client` talks to PostgreSQL. Empty tables per test."""
    yield sessionmaker(bind=pg_engine, autoflush=False)
    with pg_engine.begin() as conn:
        conn.execute(text("TRUNCATE dokument_positionen, dokumente, lieferanten RESTART IDENTITY CASCADE"))


# --- Migration --- #

def test_migration_matches_models(pg_engine):
    with pg_engine.connect() as conn:
        diff = compare_metadata(MigrationContext.configure(conn, opts={"compare_type": True}), Base.metadata)
    assert diff == []


def test_downgrade_and_upgrade_roundtrip(pg_url, pg_engine):
    config = _alembic_config(pg_url)
    command.downgrade(config, "base")
    with pg_engine.connect() as conn:
        tabellen = conn.scalars(text("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")).all()
    assert set(tabellen) <= {"alembic_version"}
    command.upgrade(config, "head")


# --- Constraints that SQLite does not enforce the same way --- #

def _insert_dokument(conn, typ: str = "angebot") -> int:
    lieferant_id = conn.scalar(text("INSERT INTO lieferanten (firmenname) VALUES ('Test GmbH') RETURNING id"))
    return conn.scalar(text(
        "INSERT INTO dokumente (lieferant_id, dokumententyp, warnungen) VALUES (:l, :t, '[]') RETURNING id"
    ), {"l": lieferant_id, "t": typ})


def test_check_constraint_rejects_unknown_type(pg_engine, session_factory):
    with pytest.raises(IntegrityError, match="ck_dokumente_dokumententyp"), pg_engine.begin() as conn:
        _insert_dokument(conn, typ="lieferschein")


def test_supplier_with_documents_cannot_be_deleted(pg_engine, session_factory):
    with pg_engine.begin() as conn:
        _insert_dokument(conn)
    with pytest.raises(IntegrityError, match="fk_dokumente_lieferant_id_lieferanten"), pg_engine.begin() as conn:
        conn.execute(text("DELETE FROM lieferanten"))


def test_deleting_document_cascades_to_positions(pg_engine, session_factory):
    with pg_engine.begin() as conn:
        dokument_id = _insert_dokument(conn)
        conn.execute(text("INSERT INTO dokument_positionen (dokument_id, position) VALUES (:d, 1)"), {"d": dokument_id})
        conn.execute(text("DELETE FROM dokumente WHERE id = :d"), {"d": dokument_id})
        assert conn.scalar(text("SELECT count(*) FROM dokument_positionen")) == 0


def test_decimal_and_json_roundtrip(client):
    """Numeric(12,2)/(12,3) keep exact values; JSON warnings come back as a list."""
    body = payload("rechnung_0003")
    created = client.post("/api/dokumente", json=body).json()
    assert created["netto"] == "5617.52"
    assert [p["menge"] for p in created["positionen"]][:2] == ["16.500", "4.000"]
    assert created["warnungen"] == []
