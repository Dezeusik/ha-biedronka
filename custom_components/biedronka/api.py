"""Klient API aplikacji mobilnej Biedronka (Moja Biedronka)."""
from __future__ import annotations

import base64
import hashlib
import json
import secrets
import time
from urllib.parse import parse_qs, urlencode, urlparse

import aiohttp

from .const import API_URL, AUTH_URL, CLIENT_ID, REDIRECT_URI, SCOPE, TOKEN_URL, USER_AGENT


class BiedronkaAuthError(Exception):
    """Token wygasł albo został odrzucony – potrzebne ponowne logowanie."""


class BiedronkaError(Exception):
    """Inny błąd komunikacji."""


def pkce_pair() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(64)[:96]
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    return verifier, challenge


def login_url(challenge: str, state: str) -> str:
    return AUTH_URL + "?" + urlencode({
        "response_type": "code", "client_id": CLIENT_ID, "redirect_uri": REDIRECT_URI,
        "state": state, "code_challenge": challenge, "code_challenge_method": "S256",
    })


def code_from_redirect(text: str) -> tuple[str | None, str | None]:
    """Wyciąga code i state z wklejonego adresu app://cma20.biedronka.pl?...code=...

    Akceptuje też cały komunikat z konsoli Chrome („Failed to launch 'app://…'”).
    """
    text = (text or "").strip()
    i = text.find("app://")
    if i >= 0:
        text = text[i:]
        for end in ("'", '"', " "):
            j = text.find(end)
            if j > 0:
                text = text[:j]
    q = urlparse(text).query or urlparse(text).fragment or text
    p = parse_qs(q)
    return (p.get("code") or [None])[0], (p.get("state") or [None])[0]


def _jwt_exp(token: str) -> float:
    try:
        payload = token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        return float(json.loads(base64.urlsafe_b64decode(payload)).get("exp", 0))
    except Exception:  # noqa: BLE001
        return 0.0


class BiedronkaClient:
    def __init__(self, session: aiohttp.ClientSession, refresh_token: str, on_tokens=None) -> None:
        self._s = session
        self.refresh_token = refresh_token
        self._access: str | None = None
        self._on_tokens = on_tokens

    async def _token_request(self, data: dict) -> dict:
        async with self._s.post(TOKEN_URL, data=data, headers={"User-Agent": USER_AGENT},
                                timeout=aiohttp.ClientTimeout(total=30)) as r:
            body = await r.text()
            if r.status in (400, 401):
                raise BiedronkaAuthError(f"{r.status}: {body[:200]}")
            if r.status >= 300:
                raise BiedronkaError(f"token {r.status}: {body[:200]}")
            return json.loads(body)

    async def exchange_code(self, code: str, verifier: str) -> dict:
        tok = await self._token_request({
            "grant_type": "authorization_code", "client_id": CLIENT_ID, "redirect_uri": REDIRECT_URI,
            "code": code, "code_verifier": verifier,
        })
        self._set(tok)
        return tok

    async def refresh(self) -> None:
        tok = await self._token_request({
            "grant_type": "refresh_token", "client_id": CLIENT_ID, "refresh_token": self.refresh_token,
            "redirect_uri": REDIRECT_URI, "scope": SCOPE,
        })
        self._set(tok)

    def _set(self, tok: dict) -> None:
        self._access = tok["access_token"]
        new_rt = tok.get("refresh_token")
        if new_rt and new_rt != self.refresh_token:
            self.refresh_token = new_rt
            if self._on_tokens:
                self._on_tokens(new_rt)

    async def get(self, path: str, params: dict | None = None, _retry: bool = True):
        if not self._access or _jwt_exp(self._access) - 60 < time.time():
            await self.refresh()
        headers = {"User-Agent": USER_AGENT, "Authorization": f"Bearer {self._access}",
                   "Accept-Language": "pl-PL", "Accept": "application/json"}
        url = API_URL + path.strip("/") + "/"
        async with self._s.get(url, params=params, headers=headers, timeout=aiohttp.ClientTimeout(total=30)) as r:
            if r.status == 401 and _retry:
                self._access = None
                return await self.get(path, params, _retry=False)
            if r.status in (401, 403):
                raise BiedronkaAuthError(f"API {r.status}")
            if r.status >= 300:
                raise BiedronkaError(f"API {path} {r.status}: {(await r.text())[:200]}")
            return await r.json(content_type=None)

    async def transactions(self, page: int = 1) -> dict:
        return await self.get("transactions", {"page": str(page)})

    async def transaction(self, tid: str) -> dict:
        return await self.get(f"transactions/{tid}")

    async def me(self) -> dict:
        return await self.get("users/me")
