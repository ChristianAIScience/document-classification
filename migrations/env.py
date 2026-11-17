from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool

import docclass.db.models  # noqa: F401  registers all tables on Base.metadata
from docclass.core.config import settings
from docclass.db.session import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

# Tests pass a throwaway database via `Config.attributes["url"]`; normally the URL comes from .env.
database_url = config.attributes.get("url", settings.database_url)


def include_name(name, type_, parent_names) -> bool:
    """Only manage tables defined in our models; foreign/legacy tables are never touched or dropped."""
    if type_ == "table":
        return name in target_metadata.tables
    return True


def _configure(**kwargs) -> None:
    context.configure(
        target_metadata=target_metadata,
        include_name=include_name,
        compare_type=True,
        **kwargs,
    )


def run_migrations_offline() -> None:
    """Emit SQL without a database connection (`alembic upgrade head --sql`)."""
    _configure(
        url=database_url.render_as_string(hide_password=False),
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = create_engine(database_url, poolclass=pool.NullPool)
    with connectable.connect() as connection:
        _configure(connection=connection)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
