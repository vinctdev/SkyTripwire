"""Run Alembic migrations from code (on application start)."""

from alembic import command
from alembic.config import Config
from sqlalchemy import Engine

SCRIPT_LOCATION = "skytripwire:db/migrations"


def alembic_config(engine: Engine | None = None) -> Config:
    config = Config()
    config.set_main_option("script_location", SCRIPT_LOCATION)
    if engine is not None:
        config.attributes["engine"] = engine
    return config


def upgrade(engine: Engine) -> None:
    """Bring the database schema to the newest revision."""
    command.upgrade(alembic_config(engine), "head")
