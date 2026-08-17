from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration, overridable via environment variables.

    Paths default to locations under /app/data so the default docker-compose
    volume mount (./data:/app/data) is enough to persist everything — the
    catalog/hash DB never ships inside the image (see PROJECT_SPEC.md, 4.0).
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Database
    database_path: Path = Path("/app/data/db/poke_collector.db")

    # Catalog assets (reference card images, downloaded by the sync job)
    catalog_dir: Path = Path("/app/data/catalog")

    # pokemontcg.io — key is optional, raises the free-tier rate limit when set
    pokemontcg_api_key: str | None = None
    pokemontcg_base_url: str = "https://api.pokemontcg.io/v2"

    # tcgdex.dev — no key required
    tcgdex_base_url: str = "https://api.tcgdex.net/v2"
    tcgdex_default_lang: str = "en"

    http_timeout_seconds: float = 30.0

    @property
    def database_url(self) -> str:
        return f"sqlite:///{self.database_path}"


@lru_cache
def get_settings() -> Settings:
    return Settings()
