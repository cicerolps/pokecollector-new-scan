"""Async client for the pokemontcg.io v2 API.

Used by the catalog sync job (Fase 2) to enumerate sets/cards and download
reference images for hashing. Key is optional — the free tier without a key
just has a lower rate limit (see PROJECT_SPEC.md section 4).
"""
from __future__ import annotations

from typing import Any

import httpx

from app.config import Settings, get_settings


class PokemonTcgApiError(RuntimeError):
    """Raised when the pokemontcg.io API returns an unexpected response."""


class PokemonTcgClient:
    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        headers = {}
        if self._settings.pokemontcg_api_key:
            headers["X-Api-Key"] = self._settings.pokemontcg_api_key
        self._client = httpx.AsyncClient(
            base_url=self._settings.pokemontcg_base_url,
            headers=headers,
            timeout=self._settings.http_timeout_seconds,
        )

    async def __aenter__(self) -> "PokemonTcgClient":
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        await self._client.aclose()

    async def _get(
        self, path: str, params: dict[str, Any] | None = None
    ) -> dict[str, Any] | None:
        try:
            response = await self._client.get(path, params=params)
        except httpx.TransportError as exc:
            raise PokemonTcgApiError(f"Network error calling {path}: {exc}") from exc
        if response.status_code == 404:
            return None
        if response.status_code >= 400:
            raise PokemonTcgApiError(
                f"pokemontcg.io returned {response.status_code} for {path}: {response.text[:200]}"
            )
        return response.json()

    async def list_sets(self, *, page: int = 1, page_size: int = 250) -> list[dict[str, Any]]:
        """Return the set list (id, name, series, releaseDate, images, ...)."""
        payload = await self._get("/sets", params={"page": page, "pageSize": page_size})
        return (payload or {}).get("data", [])

    async def get_set(self, set_id: str) -> dict[str, Any] | None:
        payload = await self._get(f"/sets/{set_id}")
        return payload.get("data") if payload else None

    async def list_cards(
        self,
        *,
        set_id: str | None = None,
        query: str | None = None,
        page: int = 1,
        page_size: int = 250,
    ) -> list[dict[str, Any]]:
        """Return cards for a set (or matching a Lucene-style `query`)."""
        q_parts = []
        if set_id:
            q_parts.append(f'set.id:"{set_id}"')
        if query:
            q_parts.append(query)
        params: dict[str, Any] = {"page": page, "pageSize": page_size}
        if q_parts:
            params["q"] = " ".join(q_parts)
        payload = await self._get("/cards", params=params)
        return (payload or {}).get("data", [])

    async def get_card(self, card_id: str) -> dict[str, Any] | None:
        payload = await self._get(f"/cards/{card_id}")
        return payload.get("data") if payload else None
