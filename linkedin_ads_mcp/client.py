"""Minimal HTTP client for LinkedIn's `/rest/*` Marketing API.

Handles:
  - Auto-refresh of access token via refresh_token + client_id/secret
  - Restli URL encoding rules:
      - literal commas in `fields=...`
      - literal colons inside `(year:Y,month:M,day:D)` tuples
      - %3A-encoded colons inside `List(urn:...)` URN values
  - Restli partial-update protocol (X-RestLi-Method: PARTIAL_UPDATE)
  - Created-entity id surfacing via x-restli-id / x-linkedin-id headers

Reads its config from environment variables:
  LINKEDIN_CLIENT_ID
  LINKEDIN_CLIENT_SECRET
  LINKEDIN_ACCESS_TOKEN          (optional — used until first refresh)
  LINKEDIN_REFRESH_TOKEN
  LINKEDIN_API_VERSION           (default: 202604)
"""
from __future__ import annotations

import json
import logging
import os
import threading
import time
from typing import Any
from urllib.parse import quote

import httpx

log = logging.getLogger(__name__)

API_HOST = "https://api.linkedin.com"
OAUTH_HOST = "https://www.linkedin.com"


class LinkedInError(RuntimeError):
    """LinkedIn API failure (auth, quota, 4xx/5xx, JSON parse)."""


def _env(name: str, *, required: bool = True) -> str:
    v = os.environ.get(name, "").strip()
    if not v and required:
        raise LinkedInError(f"{name} not set")
    return v


def _api_version() -> str:
    return os.environ.get("LINKEDIN_API_VERSION", "").strip() or "202604"


# ----- token cache --------------------------------------------------------

_LOCK = threading.Lock()
_TOKEN: str = ""
_TOKEN_EXPIRES_AT: float = 0.0


def get_token() -> str:
    global _TOKEN, _TOKEN_EXPIRES_AT
    with _LOCK:
        now = time.time()
        if _TOKEN and now < _TOKEN_EXPIRES_AT - 60:
            return _TOKEN
        if not _TOKEN:
            seeded = os.environ.get("LINKEDIN_ACCESS_TOKEN", "").strip()
            if seeded:
                _TOKEN = seeded
                _TOKEN_EXPIRES_AT = now + 50 * 60
                return _TOKEN
        _refresh_locked()
        return _TOKEN


def _refresh_locked() -> None:
    global _TOKEN, _TOKEN_EXPIRES_AT
    refresh = _env("LINKEDIN_REFRESH_TOKEN")
    cid = _env("LINKEDIN_CLIENT_ID")
    sec = _env("LINKEDIN_CLIENT_SECRET")
    r = httpx.post(
        f"{OAUTH_HOST}/oauth/v2/accessToken",
        data={
            "grant_type": "refresh_token",
            "refresh_token": refresh,
            "client_id": cid,
            "client_secret": sec,
        },
        timeout=15,
    )
    if r.status_code >= 400:
        raise LinkedInError(f"refresh failed [{r.status_code}]: {r.text[:200]}")
    data = r.json()
    _TOKEN = data["access_token"]
    _TOKEN_EXPIRES_AT = time.time() + int(data.get("expires_in", 50 * 60))
    log.info("linkedin: refreshed access_token (expires_in=%ss)", data.get("expires_in"))


def reset_token() -> None:
    global _TOKEN, _TOKEN_EXPIRES_AT
    with _LOCK:
        _TOKEN = ""
        _TOKEN_EXPIRES_AT = 0.0


# ----- low-level HTTP -----------------------------------------------------

def _qs(p: dict[str, Any] | None) -> str:
    """Build a query string honouring LinkedIn restli encoding rules.

    Permissive safe set: , : ( ) [ ] %  —  caller must pre-encode URN
    colons as %3A inside List(...) values.
    """
    if not p:
        return ""
    parts = [
        f"{quote(str(k), safe='[]')}={quote(str(v), safe=',:()[]%')}"
        for k, v in p.items()
    ]
    return "?" + "&".join(parts)


def request(
    method: str,
    path: str,
    *,
    params: dict[str, Any] | None = None,
    json_body: dict | None = None,
    with_version: bool = True,
    timeout: float = 30.0,
) -> Any:
    """Signed call to LinkedIn API. Auto-retries once on 401 with a refresh."""
    headers = {
        "Authorization": f"Bearer {get_token()}",
        "X-Restli-Protocol-Version": "2.0.0",
        "Accept": "application/json",
    }
    if with_version:
        headers["LinkedIn-Version"] = _api_version()
    if json_body is not None:
        headers["Content-Type"] = "application/json"
    if isinstance(json_body, dict) and "patch" in json_body:
        headers["X-RestLi-Method"] = "PARTIAL_UPDATE"

    url = f"{API_HOST}{path}{_qs(params)}"

    def _do() -> httpx.Response:
        return httpx.request(
            method,
            url,
            headers={**headers, "Authorization": f"Bearer {get_token()}"},
            json=json_body,
            timeout=timeout,
        )

    r = _do()
    if r.status_code == 401:
        with _LOCK:
            _refresh_locked()
        r = _do()
    if r.status_code >= 400:
        raise LinkedInError(f"LinkedIn {method} {path} [{r.status_code}]: {r.text[:300]}")
    if not r.content:
        rid = r.headers.get("x-restli-id") or r.headers.get("x-linkedin-id") or ""
        return {"_id": rid, "_status": r.status_code}
    try:
        body = r.json()
    except json.JSONDecodeError as e:
        raise LinkedInError(f"non-JSON body from {path}: {r.text[:200]}") from e
    rid = r.headers.get("x-restli-id") or r.headers.get("x-linkedin-id")
    if rid and isinstance(body, dict) and "_id" not in body:
        body = {**body, "_id": rid}
    return body
