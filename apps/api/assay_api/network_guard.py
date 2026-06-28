from __future__ import annotations

import ipaddress
import os
import socket
from typing import Any
from urllib.parse import urlsplit

HTTP_CANDIDATE_ALLOW_PRIVATE_ENV = "ASSAY_HTTP_CANDIDATE_ALLOW_PRIVATE"

_BLOCKED_NETWORKS = tuple(
    ipaddress.ip_network(cidr)
    for cidr in (
        "127.0.0.0/8",
        "10.0.0.0/8",
        "172.16.0.0/12",
        "192.168.0.0/16",
        "169.254.0.0/16",
        "::1/128",
        "fc00::/7",
        "fe80::/10",
    )
)


def _truthy(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


def private_http_candidates_allowed() -> bool:
    return _truthy(os.environ.get(HTTP_CANDIDATE_ALLOW_PRIVATE_ENV))


def validate_http_candidate_endpoint(url: Any) -> None:
    """Reject server-side candidate endpoints that resolve to non-public IPs."""

    scheme, host, port = _url_parts(url)
    if scheme not in {"http", "https"}:
        raise ValueError("HTTP candidate endpoint must use http or https")
    if not host:
        raise ValueError("HTTP candidate endpoint must include a host")
    if private_http_candidates_allowed():
        return

    addresses = _resolve_host(host, port)
    blocked = [ip for ip in addresses if _is_blocked_address(ip)]
    if blocked:
        blocked_hosts = ", ".join(str(ip) for ip in blocked)
        raise ValueError(
            "HTTP candidate endpoint must resolve only to public IP addresses; "
            f"blocked {blocked_hosts}"
        )


def _url_parts(url: Any) -> tuple[str, str, int | None]:
    if hasattr(url, "scheme") and hasattr(url, "host"):
        return str(url.scheme).lower(), str(url.host), getattr(url, "port", None)

    parsed = urlsplit(str(url))
    return parsed.scheme.lower(), parsed.hostname or "", parsed.port


def _resolve_host(host: str, port: int | None) -> set[ipaddress._BaseAddress]:
    try:
        infos = socket.getaddrinfo(host, port or 443, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise ValueError(f"HTTP candidate endpoint host could not be resolved: {host}") from exc

    addresses: set[ipaddress._BaseAddress] = set()
    for info in infos:
        raw = info[4][0].split("%", 1)[0]
        try:
            addresses.add(ipaddress.ip_address(raw))
        except ValueError as exc:
            raise ValueError(f"HTTP candidate endpoint resolved to invalid IP: {raw}") from exc
    if not addresses:
        raise ValueError(f"HTTP candidate endpoint host could not be resolved: {host}")
    return addresses


def _is_blocked_address(address: ipaddress._BaseAddress) -> bool:
    if any(address in network for network in _BLOCKED_NETWORKS):
        return True
    return not address.is_global
