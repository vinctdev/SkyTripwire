"""Alembic environment.

Used in two ways:
- From code (``skytripwire.db.migrate``): the engine is passed in ``config.attributes``.
- From the CLI (``alembic`` in ``backend/``): the URL comes from the app settings.
"""

from logging.config import fileConfig
from typing import Any, Literal

from alembic import context
from alembic.autogenerate.api import AutogenContext
from sqlalchemy import Engine
from sqlmodel import SQLModel
from sqlmodel.sql.sqltypes import AutoString

import skytripwire.db.models  # noqa: F401  (registers the tables)
from skytripwire.config import get_settings
from skytripwire.datadir import secure_data_dir
from skytripwire.db.engine import make_engine
from skytripwire.db.types import UTCDateTime

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)


def render_item(type_: str, obj: Any, autogen_context: AutogenContext) -> str | Literal[False]:
    # Render our and SQLModel's custom types as their plain storage types, so migrations
    # only depend on SQLAlchemy and never import app code.
    if type_ == "type" and isinstance(obj, UTCDateTime):
        return "sa.DateTime()"
    if type_ == "type" and isinstance(obj, AutoString):
        return "sa.String()"
    return False


def run_migrations() -> None:
    engine: Engine | None = config.attributes.get("engine")
    if engine is None:
        settings = get_settings()
        secure_data_dir(settings.data_dir)
        engine = make_engine(settings.database_url)
    with engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=SQLModel.metadata,
            render_as_batch=True,  # SQLite cannot ALTER most things in place
            render_item=render_item,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    raise RuntimeError("Offline migrations are not supported.")
run_migrations()
