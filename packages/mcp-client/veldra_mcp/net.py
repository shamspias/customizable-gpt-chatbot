"""SSRF-safe HTTP for user/agent-controlled URLs.

Any tool or node that fetches a URL chosen by an agent (the `http.fetch` builtin,
the workflow `http` node, KB URL ingestion) MUST go through here so a
self-modifying or workflow agent can't reach 169.254.169.254 (cloud metadata),
loopback, or other internal services. We refuse hosts that resolve to
private/loopback/link-local/reserved ranges, do NOT auto-follow redirects, and
re-validate the peer IP on every hop (closes the DNS-rebinding window).

Lives in the leaf veldra_mcp package so both the builtin tools (veldra_mcp_servers)
and the app (veldra_app) can share exactly one implementation.
"""

from __future__ import annotations

import ipaddress
import socket
from dataclasses import dataclass
from urllib.parse import urlparse

import httpx

_BLOCKED_FLAGS = (
    "is_private", "is_loopback", "is_link_local",
    "is_reserved", "is_multicast", "is_unspecified",
)
BYTE_CAP = 2_000_000  # hard read ceiling (memory / zip-bomb guard)


def _is_blocked(ip: ipaddress._BaseAddress) -> bool:
    return any(getattr(ip, flag) for flag in _BLOCKED_FLAGS)


def guard_url(url: str) -> None:
    """Allow only http(s) to a public host. Raises ValueError otherwise."""
    p = urlparse(url)
    if p.scheme not in ("http", "https") or not p.hostname:
        raise ValueError("only http(s) URLs are allowed")
    try:
        infos = socket.getaddrinfo(p.hostname, p.port or (443 if p.scheme == "https" else 80))
    except socket.gaierror as e:
        raise ValueError(f"cannot resolve host: {p.hostname}") from e
    for info in infos:
        if _is_blocked(ipaddress.ip_address(info[4][0])):
            raise ValueError("refusing to fetch a private/internal address")


def check_peer(resp: httpx.Response) -> None:
    """Re-validate the IP actually connected to (defeats DNS rebinding)."""
    try:
        stream = resp.extensions.get("network_stream")
        addr = stream.get_extra_info("server_addr") if stream else None
        ip = ipaddress.ip_address(addr[0]) if addr else None
    except Exception:
        ip = None
    if ip is not None and _is_blocked(ip):
        raise ValueError("refusing to fetch a private/internal address")


@dataclass
class SafeResponse:
    status_code: int
    text: str
    headers: dict


async def safe_request(
    method: str,
    url: str,
    *,
    headers: dict | None = None,
    content: str | bytes | None = None,
    timeout: float = 20.0,
    cap: int = 16_000,
    max_hops: int = 5,
) -> SafeResponse:
    """SSRF-safe HTTP request: validates the host + every redirect hop + the peer IP,
    streams the body with a hard byte ceiling, returns text truncated to `cap`."""
    guard_url(url)
    cur, hop = url, 0
    async with httpx.AsyncClient(
        timeout=timeout, follow_redirects=False, max_redirects=0,
        headers={"User-Agent": "Veldra/0.1"},
    ) as client:
        while True:
            async with client.stream(method, cur, headers=headers, content=content) as r:
                check_peer(r)
                if r.is_redirect and hop < max_hops:
                    loc = r.headers.get("location")
                    if not loc:
                        r.raise_for_status()
                    cur = str(r.url.join(loc))
                    guard_url(cur)
                    await r.aclose()
                    hop += 1
                    if r.status_code in (301, 302, 303):  # method/body reset on these
                        method, content = "GET", None
                    continue
                buf: list[bytes] = []
                total = 0
                async for blk in r.aiter_bytes():
                    total += len(blk)
                    if total > BYTE_CAP:
                        break
                    buf.append(blk)
                body = b"".join(buf).decode("utf-8", errors="replace")[:cap]
                return SafeResponse(r.status_code, body, dict(r.headers))
