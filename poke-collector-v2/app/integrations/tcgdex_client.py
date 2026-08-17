"""Async client for the tcgdex.dev v2 REST API.

Promoted to the catalog's primary source (see PROJECT_SPEC.md section 4,
and the Fase 2 commit that made this switch): pokemontcg.io's team moved to
the commercial Scrydex product and the legacy free API has become
unreliable (observed live: repeated bare 500/502s). tcgdex.dev needs no API
key and is what the original poke-collector's production backend already
relies on. Language is a path segment (`/v2/{lang}/...`), not a query param.
"""
from __future__ import annotations

import asyncio
from typing import Any

import httpx

from app.config import Settings, get_settings

_RETRYABLE_STATUS_CODES = {500, 502, 503, 504}
_MAX_ATTEMPTS = 3
_BACKOFF_BASE_SECONDS = 1.0


class TcgdexApiError(RuntimeError):
    """Raised when the tcgdex.dev API returns an unexpected response."""


class TcgdexClient:
    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._client = httpx.AsyncClient(
            base_url=self._settings.tcgdex_base_url,
            timeout=self._settings.http_timeout_seconds,
        )

    async def __aenter__(self) -> "TcgdexClient":
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        await self._client.aclose()

    async def _get(self, path: str) -> Any:
        """GET with retry-with-backoff on transient failures.

        Same rationale as PokemonTcgClient._get: this job runs unattended
        from a systemd timer, so a bare 5xx shouldn't kill the whole run.
        4xx errors are not retried.
        """
        last_error: TcgdexApiError | None = None
        for attempt in range(1, _MAX_ATTEMPTS + 1):
            try:
                response = await self._client.get(path)
            except httpx.TransportError as exc:
                last_error = TcgdexApiError(f"Network error calling {path}: {exc}")
            else:
                if response.status_code == 404:
                    return None
                if response.status_code not in _RETRYABLE_STATUS_CODES:
                    if response.status_code >= 400:
                        raise TcgdexApiError(
                            f"tcgdex.dev returned {response.status_code} for {path}: "
                            f"{response.text[:200]}"
                        )
                    return response.json()
                last_error = TcgdexApiError(
                    f"tcgdex.dev returned {response.status_code} for {path}: {response.text[:200]}"
                )
            if attempt < _MAX_ATTEMPTS:
                await asyncio.sleep(_BACKOFF_BASE_SECONDS * (2 ** (attempt - 1)))
        assert last_error is not None
        raise last_error

    async def list_sets(self, *, lang: str | None = None) -> list[dict[str, Any]]:
        lang = lang or self._settings.tcgdex_default_lang
        payload = await self._get(f"/{lang}/sets")
        return payload or []

    async def get_set(self, set_id: str, *, lang: str | None = None) -> dict[str, Any] | None:
        lang = lang or self._settings.tcgdex_default_lang
        return await self._get(f"/{lang}/sets/{set_id}")

    async def get_card(self, card_id: str, *, lang: str | None = None) -> dict[str, Any] | None:
        lang = lang or self._settings.tcgdex_default_lang
        return await self._get(f"/{lang}/cards/{card_id}")

    async def list_set_cards(self, set_id: str, *, lang: str | None = None) -> list[dict[str, Any]]:
        """Card briefs for a set — full set detail includes a `cards` array."""
        set_detail = await self.get_set(set_id, lang=lang)
        if not set_detail:
            return []
        return set_detail.get("cards", [])
