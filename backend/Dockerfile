FROM ghcr.io/astral-sh/uv:python3.11-bookworm-slim AS builder

ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy

ENV UV_PYTHON_DOWNLOADS=0 DEBIAN_FRONTEND=noninteractive

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    && rm -rf /var/lib/apt/lists/*

RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=backend/uv.lock,target=uv.lock \
    --mount=type=bind,source=backend/pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-install-project --no-dev --compile-bytecode
COPY backend /app
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev


FROM python:3.11-slim-bookworm

ENV DEBIAN_FRONTEND=noninteractive

# Install Node.js 22.x, ffmpeg, and curl for pnpm installation
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    gnupg \
    ffmpeg \
    && mkdir -p /etc/apt/keyrings \
    && curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key | gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg \
    && echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_22.x nodistro main" | tee /etc/apt/sources.list.d/nodesource.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

# Install pnpm
RUN npm install -g pnpm

# Install wrangler globally for Cloudflare Pages deployments
RUN npm install -g wrangler

COPY --from=builder --chown=app:app /app /app

# Copy frontend-static for Next.js builds
COPY frontend-static /frontend-static
WORKDIR /frontend-static
RUN pnpm install --frozen-lockfile

WORKDIR /app

# Set environment variables
ENV PATH="/app/.venv/bin:$PATH"
ENV FANTASY_COURT_FRONTEND_STATIC_PATH="/frontend-static"

# Note: CLOUDFLARE_PAGES_PROJECT_NAME, CLOUDFLARE_API_TOKEN, and CLOUDFLARE_ACCOUNT_ID
# should be set at runtime via docker run -e or docker-compose environment
