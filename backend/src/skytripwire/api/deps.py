"""FastAPI dependencies. Everything lives on ``app.state`` (set up in the lifespan)."""

from collections.abc import Iterator
from typing import Annotated, cast

from fastapi import Depends, Request
from sqlalchemy import Engine
from sqlmodel import Session

from skytripwire.config import Settings
from skytripwire.engine.worker import Worker
from skytripwire.notify.apprise_notifier import AppriseNotifier
from skytripwire.providers.base import Provider


def get_session(request: Request) -> Iterator[Session]:
    with Session(cast(Engine, request.app.state.engine)) as session:
        yield session


def get_settings(request: Request) -> Settings:
    return cast(Settings, request.app.state.settings)


def get_providers(request: Request) -> list[Provider]:
    return cast(list[Provider], request.app.state.providers)


def get_worker(request: Request) -> Worker:
    return cast(Worker, request.app.state.worker)


def get_notifier(request: Request) -> AppriseNotifier:
    return cast(AppriseNotifier, request.app.state.notifier)


SessionDep = Annotated[Session, Depends(get_session)]
SettingsDep = Annotated[Settings, Depends(get_settings)]
ProvidersDep = Annotated[list[Provider], Depends(get_providers)]
WorkerDep = Annotated[Worker, Depends(get_worker)]
NotifierDep = Annotated[AppriseNotifier, Depends(get_notifier)]
