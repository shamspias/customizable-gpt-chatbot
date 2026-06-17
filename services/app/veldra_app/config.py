"""Runtime configuration, loaded from environment / .env (see example.env)."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Deterministic default tenant id (matches deploy/alembic/versions/0001_initial.py).
DEFAULT_TENANT_ID = "00000000-0000-0000-0000-000000000001"


def _bootstrap_dotenv(path: str = ".env") -> None:
    """Export .env into os.environ (without overriding real env vars).

    pydantic-settings reads .env into the Settings model, but the leaf provider
    layer (veldra_llm) reads os.getenv directly — so we mirror .env into the process
    environment once, at import, before any provider is constructed.
    """
    p = Path(path)
    if not p.exists():
        return
    for raw in p.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key, val = key.strip(), val.strip()
        if val[:1] in ('"', "'"):  # quoted value
            q = val[0]
            end = val.find(q, 1)
            val = val[1:end] if end > 0 else val[1:]
        else:  # strip inline `# comment`
            hashidx = val.find(" #")
            if hashidx >= 0:
                val = val[:hashidx].rstrip()
        if key and key not in os.environ:
            os.environ[key] = val


_bootstrap_dotenv()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore", populate_by_name=True
    )

    # ── LLM ──
    llm_provider: str = Field(default="anthropic", alias="VELDRA_LLM_PROVIDER")  # anthropic | ollama
    anthropic_api_key: str = Field(default="", alias="ANTHROPIC_API_KEY")
    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    orchestrator_model: str = Field(default="claude-opus-4-8", alias="VELDRA_ORCHESTRATOR_MODEL")
    worker_model: str = Field(default="claude-sonnet-4-6", alias="VELDRA_WORKER_MODEL")
    cheap_model: str = Field(default="claude-haiku-4-5", alias="VELDRA_CHEAP_MODEL")
    ollama_model: str = Field(default="qwen3.5:0.8b", alias="VELDRA_OLLAMA_MODEL")  # local agent model
    ollama_orchestrator_model: str = Field(
        default="", alias="VELDRA_OLLAMA_ORCHESTRATOR_MODEL"  # blank => same as ollama_model
    )

    # ── embeddings ──
    embed_provider: Literal["auto", "openai", "ollama"] = Field(
        default="auto", alias="VELDRA_EMBED_PROVIDER"
    )
    openai_embed_model: str = Field(default="text-embedding-3-small", alias="VELDRA_OPENAI_EMBED_MODEL")
    ollama_embed_model: str = Field(default="nomic-embed-text", alias="VELDRA_OLLAMA_EMBED_MODEL")
    ollama_base_url: str = Field(default="http://localhost:11434", alias="VELDRA_OLLAMA_BASE_URL")
    embed_dim: int = Field(default=1536, alias="VELDRA_EMBED_DIM")

    # ── datastores ──
    database_url: str = Field(
        default="postgresql://veldra:veldra@localhost:5432/veldra", alias="DATABASE_URL"
    )
    redis_url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")
    s3_endpoint_url: str = Field(default="http://localhost:9000", alias="S3_ENDPOINT_URL")
    s3_access_key: str = Field(default="veldra", alias="S3_ACCESS_KEY")
    s3_secret_key: str = Field(default="veldrasecret", alias="S3_SECRET_KEY")
    s3_bucket: str = Field(default="veldra-documents", alias="S3_BUCKET")
    s3_region: str = Field(default="us-east-1", alias="S3_REGION")

    # ── app ──
    env: str = Field(default="local", alias="VELDRA_ENV")
    api_host: str = Field(default="0.0.0.0", alias="VELDRA_API_HOST")
    api_port: int = Field(default=8000, alias="VELDRA_API_PORT")
    api_base_url: str = Field(default="http://localhost:8000", alias="VELDRA_API_BASE_URL")
    default_tenant_slug: str = Field(default="default", alias="VELDRA_DEFAULT_TENANT")
    log_level: str = Field(default="INFO", alias="VELDRA_LOG_LEVEL")

    # ── auth / access (multi-user, single workspace) ──
    # When False, requests resolve to the default workspace as a system admin (no
    # token needed) — used by the CLI, evals, and trusted local automation.
    auth_enabled: bool = Field(default=True, alias="VELDRA_AUTH_ENABLED")
    session_ttl_days: int = Field(default=30, alias="VELDRA_SESSION_TTL_DAYS")
    invite_ttl_days: int = Field(default=7, alias="VELDRA_INVITE_TTL_DAYS")
    # Comma-separated allowed browser origins (CORS). Empty => derive sensible
    # defaults (api_base_url + the Vite dev server) instead of the wildcard.
    cors_origins: str = Field(default="", alias="VELDRA_CORS_ORIGINS")
    # Optional shared token the CLI can send (Authorization: Bearer <token>) to act
    # as the system admin without an interactive login. Blank => disabled.
    service_token: str = Field(default="", alias="VELDRA_SERVICE_TOKEN")

    # ── observability ──
    otel_service_name: str = Field(default="veldra", alias="OTEL_SERVICE_NAME")
    otel_exporter_otlp_endpoint: str = Field(default="", alias="OTEL_EXPORTER_OTLP_ENDPOINT")

    @property
    def async_database_url(self) -> str:
        """SQLAlchemy async URL (asyncpg driver)."""
        url = self.database_url
        if url.startswith("postgresql+"):
            return url
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)

    @property
    def cors_origin_list(self) -> list[str]:
        """Allowed browser origins. Explicit list wins; otherwise the app's own
        base URL plus the local Vite dev server (so dev works out of the box)."""
        if self.cors_origins.strip():
            return [o.strip() for o in self.cors_origins.split(",") if o.strip()]
        origins = {self.api_base_url.rstrip("/")}
        if self.env == "local":
            origins.update({"http://localhost:5173", "http://127.0.0.1:5173"})
        return sorted(origins)


@lru_cache
def get_settings() -> Settings:
    return Settings()
