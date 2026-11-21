# syntax=docker/dockerfile:1

# SkyTripwire image: FastAPI backend serving the built web UI, SQLite in /data.
# Build: docker build -t skytripwire .
# Base images are pinned by tag and digest; Dependabot keeps both up to date.

# --- Web UI -------------------------------------------------------------------------------
# The build output is platform independent, so it always runs on the build host (no QEMU).
FROM --platform=$BUILDPLATFORM node:26.13.0-trixie-slim@sha256:5adad64f9a1fca2d51972caa65983634c8a774eb300d72b20f7f2a0f60368072 AS frontend
WORKDIR /src/frontend
COPY frontend/package.json frontend/package-lock.json frontend/.npmrc ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

# --- Python environment -------------------------------------------------------------------
FROM python:3.14.10-slim-trixie@sha256:9aaa474097d094040649f2162a627c0049b408f52138d980916788d80f04802f AS backend
ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_ROOT_USER_ACTION=ignore
# Runtime dependencies: exact versions from requirements.txt, prebuilt wheels only.
COPY backend/requirements.txt /tmp/requirements.txt
RUN python -m venv /opt/venv \
    && /opt/venv/bin/pip install --only-binary=:all: -r /tmp/requirements.txt
# The app itself. pip check fails the build if requirements.txt and pyproject.toml disagree.
COPY backend/pyproject.toml /src/backend/
COPY backend/src/ /src/backend/src/
RUN /opt/venv/bin/pip install --no-deps /src/backend \
    && /opt/venv/bin/pip check \
    && /opt/venv/bin/pip uninstall --yes pip

# --- Runtime ------------------------------------------------------------------------------
FROM python:3.14.10-slim-trixie@sha256:9aaa474097d094040649f2162a627c0049b408f52138d980916788d80f04802f

LABEL org.opencontainers.image.title="SkyTripwire" \
      org.opencontainers.image.description="Self-hosted flight filters and alerts with Telegram and e-mail notifications." \
      org.opencontainers.image.licenses="MIT"

# Unprivileged user. /data holds the database with channel credentials: owner only.
# pip is not needed at runtime: remove the copy that comes with the base image.
RUN rm -rf /usr/local/bin/pip* /usr/local/lib/python3.14/site-packages/pip \
        /usr/local/lib/python3.14/site-packages/pip-*.dist-info \
    && groupadd --system --gid 10001 skytripwire \
    && useradd --system --uid 10001 --gid 10001 --no-create-home \
        --home-dir /nonexistent --shell /usr/sbin/nologin skytripwire \
    && mkdir /data \
    && chown 10001:10001 /data \
    && chmod 700 /data

COPY --from=backend /opt/venv /opt/venv
COPY --from=frontend /src/frontend/dist /opt/skytripwire/web
# License notices: SkyTripwire itself here, the bundled web UI dependencies in
# web/third-party-licenses.txt, Python packages in their *.dist-info folders.
COPY LICENSE /opt/skytripwire/LICENSE

# Inside the container the app listens on all interfaces; the published port decides who
# can reach it (compose.yaml binds it to 127.0.0.1 on the host).
ENV PATH=/opt/venv/bin:$PATH \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    SKYTRIPWIRE_HOST=0.0.0.0 \
    SKYTRIPWIRE_PORT=8000 \
    SKYTRIPWIRE_DATA_DIR=/data \
    SKYTRIPWIRE_FRONTEND_DIR=/opt/skytripwire/web

USER 10001:10001
WORKDIR /opt/skytripwire
VOLUME ["/data"]
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD ["python", "-c", "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:' + os.environ['SKYTRIPWIRE_PORT'] + '/api/health', timeout=4)"]

CMD ["skytripwire"]
