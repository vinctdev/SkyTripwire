"""FastAPI application factory."""

import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from urllib.parse import urlsplit

import anyio
from fastapi import FastAPI, Request
from fastapi import status as status_codes
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from starlette.middleware.trustedhost import TrustedHostMiddleware

from skytripwire import __version__
from skytripwire.api import alerts, channels, filters, status
from skytripwire.config import Settings, get_settings
from skytripwire.datadir import secure_data_dir
from skytripwire.db import migrate
from skytripwire.db.engine import make_engine
from skytripwire.engine.worker import Worker
from skytripwire.notify.apprise_notifier import AppriseNotifier
from skytripwire.providers import build_providers
from skytripwire.web import find_frontend_dir, mount_frontend

log = logging.getLogger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        secure_data_dir(settings.data_dir)
        engine = make_engine(settings.database_url)
        await anyio.to_thread.run_sync(migrate.upgrade, engine)
        # Again for a database the migration has just created.
        secure_data_dir(settings.data_dir)
        providers = build_providers(settings)
        notifier = AppriseNotifier()
        worker = Worker(
            engine,
            providers,
            notifier,
            budgets=settings.daily_budgets(),
            min_interval=settings.poll_min_interval_seconds,
            max_alerts_per_filter=settings.max_alerts_per_filter_per_cycle,
        )
        app.state.engine = engine
        app.state.providers = providers
        app.state.notifier = notifier
        app.state.worker = worker
        try:
            async with anyio.create_task_group() as tg:
                if settings.worker_enabled:
                    tg.start_soon(worker.run)
                    log.info("Polling worker started with %s", [p.name for p in providers])
                else:
                    log.warning("Polling worker is disabled (SKYTRIPWIRE_WORKER_ENABLED=false)")
                yield
                tg.cancel_scope.cancel()
        finally:
            for provider in providers:
                await provider.aclose()
            engine.dispose()

    app = FastAPI(title="SkyTripwire", version=__version__, lifespan=lifespan)
    app.state.settings = settings
    # Both checks use the same list: the Host header against DNS rebinding, the Origin header
    # against cross-site requests (a POST without body needs no CORS preflight).
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.trusted_hosts)
    if "*" not in settings.trusted_hosts:
        app.middleware("http")(_same_origin_check(settings.trusted_hosts))
    for router in (status.router, filters.router, channels.router, alerts.router):
        app.include_router(router, prefix="/api")
    app.add_exception_handler(RequestValidationError, _validation_error)
    # Last: the web UI adds a catch-all route for client-side routing.
    frontend_dir = find_frontend_dir(settings.frontend_dir)
    if frontend_dir is not None:
        mount_frontend(app, frontend_dir)
    return app


_SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})

type _CallNext = Callable[[Request], Awaitable[Response]]


def _same_origin_check(
    allowed_hosts: list[str],
) -> Callable[[Request, _CallNext], Awaitable[Response]]:
    """Reject state-changing browser requests from other sites.

    Browsers send ``Origin`` with every cross-origin POST, PUT and DELETE. Clients like curl
    send none and are not affected.
    """
    allowed = {host.lower() for host in allowed_hosts}
    # "*.example.org", as TrustedHostMiddleware understands it.
    suffixes = tuple(host[1:] for host in allowed if host.startswith("*."))

    async def check(request: Request, call_next: _CallNext) -> Response:
        origin = request.headers.get("origin")
        if request.method not in _SAFE_METHODS and origin is not None:
            host = urlsplit(origin).hostname
            if host is None or not (host in allowed or host.endswith(suffixes)):
                return JSONResponse(
                    {"detail": "cross-site request rejected"},
                    status_code=status_codes.HTTP_403_FORBIDDEN,
                )
        return await call_next(request)

    return check


async def _validation_error(request: Request, exc: Exception) -> JSONResponse:
    """Like FastAPI's default, but without echoing the input: it may contain channel secrets."""
    errors = exc.errors() if isinstance(exc, RequestValidationError) else []
    detail = [
        {key: value for key, value in error.items() if key in {"type", "loc", "msg"}}
        for error in errors
    ]
    return JSONResponse({"detail": detail}, status_code=status_codes.HTTP_422_UNPROCESSABLE_CONTENT)
