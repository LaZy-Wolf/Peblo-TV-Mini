from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Read the repo root .env too, so running from api/ picks up the same
    # file docker compose does. Later entries win.
    model_config = SettingsConfigDict(env_file=("../.env", ".env"), extra="ignore")

    database_url: str = "postgresql+psycopg://peblo:peblo@localhost:5432/peblo"
    test_database_url: str = "postgresql+psycopg://peblo:peblo@localhost:5432/peblo_test"

    jwt_secret: str = "dev-only-change-me-not-for-production-use"
    jwt_expiry_hours: int = 8
    seed_editor_email: str = "editor@peblo.test"
    seed_editor_password: str = "editor-dev-password"
    seed_admin_email: str = "admin@peblo.test"
    seed_admin_password: str = "admin-dev-password"

    storage_backend: str = "local"
    storage_local_root: Path = Path("./storage_local")
    storage_public_base_url: str = "http://localhost:8000/media"

    r2_account_id: str = ""
    r2_access_key_id: str = ""
    r2_secret_access_key: str = ""
    r2_bucket: str = ""
    r2_endpoint_url: str = ""

    data_dir: Path = Path("./data")
    cors_origins: str = "http://localhost:5173,http://localhost:5174"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
