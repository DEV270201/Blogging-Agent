# ---- Stage 1: install production dependencies ----
# The uv base image ships with uv and a full Python; we use it only to build
# the virtualenv so nothing from it leaks into the runtime image.
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder

WORKDIR /app

# Copy only the dependency manifest and lockfile first so Docker can cache this
# layer and skip re-installing packages when only source code changes.
COPY pyproject.toml uv.lock ./

# --frozen       : fail if lockfile is out of sync (reproducible builds)
# --no-dev       : skip test/dev dependency groups
# --no-install-project : don't install the project itself as a package —
#                        we COPY source directly and run from WORKDIR
RUN uv sync --frozen --no-dev --no-install-project

# ---- Stage 2: minimal runtime image ----
# Use an explicit Debian Bookworm base and apply the latest OS security patches
# during the image build so the final runtime image does not ship with known
# vulnerabilities from stale package metadata.
FROM python:3.12-slim-bookworm AS runtime

WORKDIR /app

# Apply Debian security updates before copying the app into the final image.
RUN apt-get update \
    && apt-get upgrade -y --no-install-recommends \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Pull the pre-built virtualenv from the builder — no uv or build tools needed
# at runtime, which keeps this layer small and the attack surface minimal.
COPY --from=builder /app/.venv /app/.venv

# Application source only — client/, tests/, .env, blogs/ are excluded via .dockerignore
COPY Server/ ./Server/

# Blank blogs directory — config.py also creates this on startup, but having it
# here ensures the mount point exists even before the app initialises.
RUN mkdir -p Server/blogs

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

EXPOSE 8000

CMD ["uvicorn", "Server.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
