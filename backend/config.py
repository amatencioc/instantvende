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

    # === Bot / Negocio ===
    BOT_NAME: str = "Favio"
    STORE_NAME: str = "Fresh Boy Store"
    STORE_ADDRESS: str = "Av. Principal 123, Miraflores, Lima"

    # === Envíos (en centavos para consistencia interna) ===
    SHIPPING_LIMA_CENTS: int = 1000       # S/ 10
    SHIPPING_PROVINCES_CENTS: int = 1500  # S/ 15
    SHIPPING_FREE_THRESHOLD_CENTS: int = 8000  # S/ 80

    # === Horarios ===
    SCHEDULE_WEEKDAY: str = "Lun - Vie: 9:00 AM - 8:00 PM"
    SCHEDULE_SATURDAY: str = "Sábados: 10:00 AM - 6:00 PM"

    # === Descuentos ===
    DISCOUNT_TWO_PRODUCTS_PCT: int = 10
    DISCOUNT_THREE_PLUS_PCT: int = 15

    # === Bot tuning ===
    HISTORY_MESSAGES_LIMIT: int = 6
    AI_MAX_PRODUCTS_CONTEXT: int = 8
    AI_MAX_RECOMMENDATIONS: int = 3
    MESSAGE_COOLDOWN_SECONDS: float = 1.5
    AI_RESPONSE_MAX_CHARS: int = 1000

    # === Bot profile ===
    BOT_PROFILE_PATH: str = ""  # ruta al bot_profile.json; vacío = usar el del directorio del backend

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
