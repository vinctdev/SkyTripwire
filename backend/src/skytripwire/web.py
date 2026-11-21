"""Serve the built frontend (single page app) from the same process as the API.

- ``/assets/*`` are content-hashed by Vite and cached for a year.
- Any other path that is a file in the build directory is served as is (e.g. a favicon).
- Every other path returns ``index.html`` (never cached), so client-side routes like
  ``/filters/7`` work on reload. ``/api/*`` is excluded: unknown API paths stay JSON 404s.

Register this after the API routers, it adds a catch-all route.
"""

import logging
from pathlib import Path

from fastapi import FastAPI, HTTPException, status
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.types import Scope

log = logging.getLogger(__name__)

PACKAGED_FRONTEND_DIR = Path(__file__).parent / "static"

# Only for the HTML page. Not for /docs, which loads Swagger UI from a CDN.
# Map tiles come from OpenStreetMap; React and Leaflet set styles through the DOM.
CONTENT_SECURITY_POLICY = "; ".join(
    [
        "default-src 'self'",
        "img-src 'self' data: https://tile.openstreetmap.org",
        "style-src 'self' 'unsafe-inline'",
        "connect-src 'self'",
        "object-src 'none'",
        "base-uri 'self'",
        "form-action 'self'",
        "frame-ancestors 'none'",
    ]
)

INDEX_HEADERS = {
    "Cache-Control": "no-cache",
    "Content-Security-Policy": CONTENT_SECURITY_POLICY,
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "X-Frame-Options": "DENY",
}


class _ImmutableStaticFiles(StaticFiles):
    async def get_response(self, path: str, scope: Scope) -> Response:
        response = await super().get_response(path, scope)
        if response.status_code == status.HTTP_200_OK:
            response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response


def find_frontend_dir(configured: Path | None) -> Path | None:
    """The configured directory, else the one bundled with the package, if it holds a build."""
    candidate = configured or PACKAGED_FRONTEND_DIR
    if (candidate / "index.html").is_file():
        return candidate.resolve()
    if configured is not None:
        log.warning("No index.html in %s, the web UI is not served", configured)
    return None


def mount_frontend(app: FastAPI, directory: Path) -> None:
    index = directory / "index.html"
    assets = directory / "assets"
    if assets.is_dir():
        app.mount("/assets", _ImmutableStaticFiles(directory=assets), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str) -> FileResponse:
        if path == "api" or path.startswith("api/"):
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Not Found")
        if path:
            file = (directory / path).resolve()
            if file.is_relative_to(directory) and file.is_file() and file != index:
                return FileResponse(file, headers={"X-Content-Type-Options": "nosniff"})
        return FileResponse(index, headers=INDEX_HEADERS)

    log.info("Serving the web UI from %s", directory)
