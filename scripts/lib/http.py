"""HTTP client: retries, backoff, polite User-Agent, offline kill-switch.

Every network call in deep-research-os goes through this module, so the
offline switch (``RESEARCH_OS_OFFLINE=1``) reliably disables the network for
air-gapped runs and the eval suite.
"""

from __future__ import annotations

import hashlib
import ipaddress
import json as _json
import os
import random
import socket
import time
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlparse

import httpx

from lib import __version__ as _pkg_version

USER_AGENT = (
    f"deep-research-os/{_pkg_version} "
    "(research agent skill; +https://github.com/deep-research-os)"
)

DEFAULT_TIMEOUT = 15.0
DEFAULT_RETRIES = 2
DEFAULT_MAX_BYTES = 50 * 1024 * 1024
MAX_REDIRECTS = 5

FULLTEXT_CONTENT_TYPES = {
    "application/pdf", "application/x-pdf", "application/xml", "text/xml",
    "application/octet-stream", "text/html", "application/xhtml+xml", "text/plain",
}

BLOCKED_HOSTS = {
    "sci-hub.se", "sci-hub.st", "sci-hub.ru", "sci-hub.ren", "sci-hub.tw",
    "sci-hub.hkvisa.net", "libgen.is", "libgen.rs", "libgen.st", "libgen.li",
    "annas-archive.org", "annas-archive.se", "annas-archive.li", "z-lib.org",
    "zlibrary.to", "1lib.org", "b-ok.org", "booksc.org",
}


class OfflineError(RuntimeError):
    """Raised when a network call is attempted while offline mode is on."""


class HttpError(RuntimeError):
    def __init__(self, status: int, url: str, body: str = "", retry_after: Optional[float] = None):
        super().__init__(f"HTTP {status} for {url}: {body[:200]}")
        self.status = status
        self.url = url
        self.body = body
        self.retry_after = retry_after


def is_offline() -> bool:
    v = os.environ.get("RESEARCH_OS_OFFLINE", "").strip().lower()
    return v in {"1", "true", "yes", "on"}


def _guard_offline(url: str) -> None:
    if is_offline():
        raise OfflineError(f"offline mode is on — refusing network call to {url}")


def _headers(extra: Optional[dict] = None, mailto: Optional[str] = None) -> dict:
    h = {"User-Agent": USER_AGENT, "Accept-Language": "en;q=0.9,fa;q=0.8"}
    if mailto:
        h["From"] = mailto
    if extra:
        h.update(extra)
    return h


def request(
    method: str,
    url: str,
    *,
    params: Optional[dict] = None,
    headers: Optional[dict] = None,
    json_body: Any = None,
    data: Any = None,
    timeout: float = DEFAULT_TIMEOUT,
    retries: int = DEFAULT_RETRIES,
    mailto: Optional[str] = None,
    follow_redirects: bool = True,
) -> httpx.Response:
    """Single entry point with polite retry/backoff semantics."""
    _guard_offline(url)
    last_exc: Optional[Exception] = None
    for attempt in range(retries + 1):
        try:
            resp = httpx.request(
                method,
                url,
                params=params,
                headers=_headers(headers, mailto),
                json=json_body,
                data=data,
                timeout=timeout,
                follow_redirects=follow_redirects,
            )
            if resp.status_code == 429:
                wait = _retry_after(resp, attempt)
                last_exc = HttpError(429, url, resp.text[:200], retry_after=wait)
                time.sleep(wait)
                continue
            if 500 <= resp.status_code < 600:
                last_exc = HttpError(resp.status_code, url, resp.text[:200])
                time.sleep(_backoff(attempt))
                continue
            if resp.status_code >= 400:
                raise HttpError(resp.status_code, url, resp.text[:200])
            return resp
        except (httpx.TimeoutException, httpx.TransportError) as exc:
            last_exc = exc
            time.sleep(_backoff(attempt))
    assert last_exc is not None
    raise last_exc if isinstance(last_exc, Exception) else RuntimeError("request failed")


def _backoff(attempt: int) -> float:
    return min(8.0, (0.6 * (2 ** attempt)) + random.random() * 0.4)


def _retry_after(resp: httpx.Response, attempt: int) -> float:
    ra = resp.headers.get("Retry-After")
    if ra:
        try:
            return min(30.0, float(ra))
        except ValueError:
            pass
    return _backoff(attempt)



def is_blocked_host(host: str) -> bool:
    host = (host or "").strip().lower().rstrip(".")
    if not host:
        return True
    if host in BLOCKED_HOSTS:
        return True
    return any(host == b or host.endswith("." + b) for b in BLOCKED_HOSTS)


def _is_private_address(addr: str) -> bool:
    try:
        ip = ipaddress.ip_address(addr)
    except ValueError:
        return True
    return bool(ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast
                or ip.is_reserved or ip.is_unspecified)


def validate_url(url: str, *, allow_private: bool = False) -> None:
    """Reject non-HTTP(S), blocked piracy hosts, and SSRF targets."""
    parsed = urlparse(url or "")
    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"unsupported URL scheme: {parsed.scheme or '(none)'}")
    host = (parsed.hostname or "").strip().lower()
    if is_blocked_host(host):
        raise ValueError(f"blocked host: {host or '(none)'} — this client only uses legal full-text sources")
    if allow_private:
        return
    if host in ("localhost", "localhost.localdomain"):
        raise ValueError("private/loopback hosts are not allowed for full-text downloads")
    try:
        infos = socket.getaddrinfo(host, parsed.port or (443 if parsed.scheme == "https" else 80),
                                   type=socket.SOCK_STREAM)
    except OSError as exc:
        raise ValueError(f"cannot resolve host {host}: {exc}") from exc
    for info in infos:
        addr = info[4][0]
        if _is_private_address(addr):
            raise ValueError(f"private/loopback address not allowed: {host} -> {addr}")


def download(
    url: str,
    dest: str | Path,
    *,
    max_bytes: int = DEFAULT_MAX_BYTES,
    timeout: float = 60.0,
    retries: int = 1,
    allowed_content_types: Optional[set[str]] = None,
    headers: Optional[dict] = None,
    allow_private: bool = False,
) -> dict:
    """Stream a URL to ``dest`` with SSRF, size and content-type guards.

    Returns a descriptor with the final URL, content type, byte count and SHA-256.
    """
    _guard_offline(url)
    validate_url(url, allow_private=allow_private)
    allowed = {c.lower() for c in (allowed_content_types or FULLTEXT_CONTENT_TYPES)}
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    last_exc: Optional[Exception] = None
    for attempt in range(retries + 1):
        tmp = dest.with_name(dest.name + ".part")
        try:
            current = url
            for _hop in range(MAX_REDIRECTS + 1):
                with httpx.stream(
                    "GET", current, headers=_headers(headers), timeout=timeout,
                    follow_redirects=False,
                ) as resp:
                    if resp.is_redirect:
                        location = resp.headers.get("location")
                        if not location:
                            raise HttpError(resp.status_code, str(resp.url), "redirect without Location")
                        current = str(resp.url.join(location))
                        validate_url(current, allow_private=allow_private)
                        continue
                    if resp.status_code >= 400:
                        raise HttpError(resp.status_code, str(resp.url), resp.read()[:200])
                    ctype = (resp.headers.get("content-type") or "").split(";")[0].strip().lower()
                    if ctype and ctype not in allowed:
                        raise ValueError(f"unexpected content-type: {ctype}")
                    length = resp.headers.get("content-length")
                    if length and int(length) > max_bytes:
                        raise ValueError(f"content-length {length} exceeds max_bytes {max_bytes}")
                    total = 0
                    digest = hashlib.sha256()
                    with open(tmp, "wb") as fh:
                        for chunk in resp.iter_bytes(65536):
                            total += len(chunk)
                            if total > max_bytes:
                                raise ValueError(f"download exceeds max_bytes {max_bytes}")
                            digest.update(chunk)
                            fh.write(chunk)
                    tmp.replace(dest)
                    return {
                        "path": str(dest), "url": url, "final_url": str(resp.url),
                        "content_type": ctype or "application/octet-stream",
                        "bytes": total, "sha256": digest.hexdigest(),
                        "filename": dest.name, "status": resp.status_code,
                    }
            raise ValueError(f"too many redirects (>{MAX_REDIRECTS})")
        except (httpx.TimeoutException, httpx.TransportError) as exc:
            last_exc = exc
            try:
                tmp.unlink()
            except OSError:
                pass
            if attempt < retries:
                time.sleep(_backoff(attempt))
                continue
            raise
        except Exception:
            try:
                tmp.unlink()
            except OSError:
                pass
            raise
    raise last_exc if last_exc else RuntimeError("download failed")


def get_json(url: str, params: Optional[dict] = None, **kw) -> Any:
    r = request("GET", url, params=params, **kw)
    return r.json()


def post_json(url: str, body: Any, **kw) -> Any:
    r = request("POST", url, json_body=body, **kw)
    return r.json()


def get_text(url: str, params: Optional[dict] = None, **kw) -> str:
    r = request("GET", url, params=params, **kw)
    return r.text


def get_bytes(url: str, params: Optional[dict] = None, **kw) -> bytes:
    r = request("GET", url, params=params, **kw)
    return r.content


def url_alive(url: str, timeout: float = 10.0) -> tuple[bool, int]:
    """HEAD (fallback GET) liveness check. Returns (alive, status)."""
    try:
        r = request("HEAD", url, timeout=timeout, retries=1)
        return r.status_code < 400, r.status_code
    except HttpError as e:
        if e.status in (403, 405):  # many servers reject HEAD; try GET
            try:
                r = request("GET", url, timeout=timeout, retries=1)
                return r.status_code < 400, r.status_code
            except HttpError as e2:
                return False, e2.status
            except Exception:
                return False, -1
        return False, e.status
    except Exception:
        return False, -1
