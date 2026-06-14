# syntax=docker/dockerfile:1
# Veldra — single image that serves the Vue UI + the FastAPI API.

# ── stage 1: build the Vue SPA ──
FROM node:22-alpine AS web
WORKDIR /web
COPY apps/web/package.json apps/web/package-lock.json* ./
RUN npm install --no-fund --no-audit
COPY apps/web/ ./
RUN npm run build

# ── stage 2: python runtime (serves UI + API) ──
FROM python:3.12-slim AS app
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
RUN pip install --no-cache-dir uv
WORKDIR /app

# Install the workspace (editable so veldra_app can locate apps/web/dist at runtime).
COPY pyproject.toml README.md alembic.ini ./
COPY packages/ ./packages/
COPY services/ ./services/
COPY cli/ ./cli/
COPY evals/ ./evals/
COPY deploy/ ./deploy/
RUN uv pip install --system -e .

# Built front-end assets, served by FastAPI at "/".
COPY --from=web /web/dist ./apps/web/dist

EXPOSE 8000
# Apply migrations, then serve. Idempotent — safe on every boot.
CMD ["sh", "-c", "python -m veldra_app.db migrate && uvicorn veldra_app.main:app --host 0.0.0.0 --port 8000"]
