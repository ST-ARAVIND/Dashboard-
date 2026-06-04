"""Application configuration loaded from environment / .env file.

All settings are typed and validated with pydantic-settings.  Secrets are kept
here and never serialized to the frontend (see ``api`` routers).
"""
from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Strongly-typed application settings."""

    model_config = SettingsConfigDict(
        # Look for a .env file in the repo root (one level above /backend) and /backend.
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- Angel One SmartAPI ---
    angel_api_key: str = Field(default="", alias="ANGEL_API_KEY")
    angel_client_code: str = Field(default="", alias="ANGEL_CLIENT_CODE")
    angel_mpin: str = Field(default="", alias="ANGEL_MPIN")
    angel_totp_secret: str = Field(default="", alias="ANGEL_TOTP_SECRET")

    # --- News ---
    news_provider: str = Field(default="rss", alias="NEWS_PROVIDER")
    news_api_key: str = Field(default="", alias="NEWS_API_KEY")

    # --- Sentiment ---
    sentiment_model: str = Field(default="vader", alias="SENTIMENT_MODEL")

    # --- Analytics ---
    risk_free_rate: float = Field(default=0.065, alias="RISK_FREE_RATE")

    # --- Storage ---
    database_url: str = Field(default="sqlite:///./market.db", alias="DATABASE_URL")

    # --- Server ---
    backend_host: str = Field(default="127.0.0.1", alias="BACKEND_HOST")
    backend_port: int = Field(default=8000, alias="BACKEND_PORT")
    cors_origins: str = Field(
        default="http://localhost:5173,http://127.0.0.1:5173",
        alias="CORS_ORIGINS",
    )

    # --- Scheduler ---
    oi_snapshot_interval: int = Field(default=180, alias="OI_SNAPSHOT_INTERVAL")

    # --- API protection (optional) ---
    # If set, every /api/* request (except /api/health) must send this token in
    # an `X-API-Token` header. Leave empty to keep the API open (local dev).
    # NOTE: a token shipped to a public browser bundle is light protection, not
    # real auth — it deters casual drive-by use of your Angel session/quota.
    api_auth_token: str = Field(default="", alias="API_AUTH_TOKEN")

    # --- Scrip master ---
    scrip_master_url: str = Field(
        default="https://margincalculator.angelbroking.com/OpenAPI_File/files/OpenAPIScripMaster.json",
        alias="SCRIP_MASTER_URL",
    )

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def angel_credentials_present(self) -> bool:
        """True only when every Angel One credential is supplied."""
        return all(
            [
                self.angel_api_key,
                self.angel_client_code,
                self.angel_mpin,
                self.angel_totp_secret,
            ]
        )


@lru_cache
def get_settings() -> Settings:
    """Cached singleton accessor for settings."""
    return Settings()


settings = get_settings()
