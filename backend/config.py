"""Configuración centralizada con pydantic-settings."""
from __future__ import annotations

from functools import lru_cache
from typing import List

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # === Seguridad ===
    API_SECRET_KEY: str  # Requerido — no tiene default intencional

    # === Base de datos ===
    DATABASE_URL: str = "sqlite:///./instantvende.db"

    # === Ollama / IA ===
    OLLAMA_MODEL: str = "phi3:mini"
    OLLAMA_TIMEOUT: int = 45

    # === CORS ===
    CORS_ORIGINS: str = "*"

    # === Backups ===
    BACKUP_INTERVAL_HOURS: int = 6
    MAX_BACKUPS: int = 10

    @field_validator("API_SECRET_KEY")
    @classmethod
    def api_key_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("API_SECRET_KEY no puede estar vacío")
        return v

    @property
    def cors_origins_list(self) -> List[str]:
        """Devuelve la lista de orígenes CORS parseando la cadena separada por comas."""
        if self.CORS_ORIGINS.strip() == "*":
            return ["*"]
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]


@lru_cache()
def get_settings() -> Settings:
    """Singleton cacheado de configuración."""
    return Settings()


# Alias conveniente
settings = get_settings()
