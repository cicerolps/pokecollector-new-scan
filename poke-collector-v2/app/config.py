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

    # Pipeline (Fase 3-4) — see PROJECT_SPEC.md section 3
    card_output_width: int = 600
    card_output_height: int = 825
    hash_match_top_n: int = 5
    # Candidate #1 is accepted directly when its combined Hamming distance is
    # at least this much lower than candidate #2's; otherwise OCR
    # disambiguation kicks in (PROJECT_SPEC.md 3.2).
    hash_confidence_gap: int = 10
    # Below this combined distance for candidate #1, treat as no match at all
    # rather than a low-confidence guess.
    hash_no_match_distance: int = 60
    easyocr_model_dir: Path = Path("/opt/easyocr-models")
    easyocr_languages: tuple[str, ...] = ("en",)

    @property
    def database_url(self) -> str:
        return f"sqlite:///{self.database_path}"

    @property
    def card_output_size(self) -> tuple[int, int]:
        return (self.card_output_width, self.card_output_height)


@lru_cache
def get_settings() -> Settings:
    return Settings()
