"""HTTP client: retries, backoff, polite User-Agent, offline kill-switch.

Every network call in deep-research-os goes through this module, so the
offline switch (``RESEARCH_OS_OFFLINE=1``) reliably disables the network for
air-gapped runs and the eval suite.
"""

from __future__ import annotations

import json as _json
import os
import random
import time
from typing import Any, Optional

import httpx

from lib import __version__ as _pkg_version

USER_AGENT = (
    f"deep-research-os/{_pkg_version} "
    "(research agent skill; +https://github.com/deep-research-os)"
)

DEFAULT_TIMEOUT = 15.0
DEFAULT_RETRIES = 2


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
