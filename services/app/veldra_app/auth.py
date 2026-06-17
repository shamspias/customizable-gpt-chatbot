"""Authentication primitives: password hashing, session tokens, and the request
`Context` that replaces the old hardcoded single tenant.

Design notes
------------
* Passwords are hashed with PBKDF2-HMAC-SHA256 (stdlib only — no native build
  dependency), stored as ``pbkdf2_sha256$rounds$salt_hex$hash_hex``.
* Sessions are opaque random bearer tokens; only their SHA-256 hash is stored, so
  the database never holds anything replayable.
* ``get_context`` is the single FastAPI dependency every protected handler depends
  on. When ``auth_enabled`` is False it resolves to the default workspace as a
  system admin, which keeps the CLI, evals, and trusted local automation working.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
from dataclasses import dataclass

from fastapi import Depends, HTTPException, Request

from veldra_app.config import DEFAULT_TENANT_ID, get_settings

# Roles, ordered weakest → strongest. A user satisfies a requirement if their role
# is at least as strong as the one required.
ROLES = ("viewer", "member", "admin")
_RANK = {r: i for i, r in enumerate(ROLES)}

_PBKDF2_ROUNDS = 240_000


# ───────────────────────── password hashing (stdlib PBKDF2) ─────────────────────────
def hash_password(password: str) -> str:
    if not password or len(password) < 8:
        raise ValueError("Password must be at least 8 characters.")
    salt = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, _PBKDF2_ROUNDS)
    return f"pbkdf2_sha256${_PBKDF2_ROUNDS}${salt.hex()}${dk.hex()}"


def verify_password(password: str, stored: str | None) -> bool:
    if not stored:
        return False
    try:
        algo, rounds_s, salt_hex, hash_hex = stored.split("$")
        if algo != "pbkdf2_sha256":
            return False
        dk = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), bytes.fromhex(salt_hex), int(rounds_s)
        )
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(dk.hex(), hash_hex)


# ───────────────────────── session tokens ─────────────────────────
def new_session_token() -> tuple[str, str]:
    """Return ``(plaintext, sha256_hash)``. The plaintext is shown once to the client;
    only the hash is persisted."""
    token = secrets.token_urlsafe(32)
    return token, hash_token(token)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


# ───────────────────────── request context ─────────────────────────
@dataclass(frozen=True)
class Context:
    """Everything a handler needs to know about who is calling and which workspace."""

    tenant_id: str
    user_id: str | None
    role: str
    email: str
    name: str
    authenticated: bool

    def can(self, required: str) -> bool:
        return _RANK.get(self.role, -1) >= _RANK.get(required, 99)


SYSTEM_CONTEXT = Context(
    tenant_id=DEFAULT_TENANT_ID,
    user_id=None,
    role="admin",
    email="system@veldra.local",
    name="System",
    authenticated=False,
)


def bearer_token(request: Request) -> str | None:
    header = request.headers.get("authorization") or ""
    if header.lower().startswith("bearer "):
        return header[7:].strip() or None
    return None


async def get_context(request: Request) -> Context:
    """Resolve the caller into a Context, or raise 401. The keystone dependency."""
    settings = get_settings()
    if not settings.auth_enabled:
        return SYSTEM_CONTEXT

    token = bearer_token(request)
    if not token:
        raise HTTPException(status_code=401, detail="Authentication required")

    # A configured service token acts as the system admin (used by the CLI).
    if settings.service_token and hmac.compare_digest(token, settings.service_token):
        return SYSTEM_CONTEXT

    from veldra_app import auth_repo
    from veldra_app.db import get_sessionmaker

    sm = get_sessionmaker()
    async with sm() as db:
        ctx = await auth_repo.resolve_session(db, token)
        await db.commit()  # persist last_seen bump
    if ctx is None:
        raise HTTPException(status_code=401, detail="Session expired or invalid")
    return ctx


def require_role(required: str):
    """Dependency factory: 403 unless the caller's role is >= `required`."""

    async def _dep(ctx: Context = Depends(get_context)) -> Context:
        if not ctx.can(required):
            raise HTTPException(status_code=403, detail=f"Requires {required} access")
        return ctx

    return _dep
