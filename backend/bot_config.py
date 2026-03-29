"""Constantes del bot leídas desde Settings (config.py / .env)."""
from __future__ import annotations

from config import settings

# === Identidad del negocio ===
BOT_NAME: str = settings.BOT_NAME
STORE_NAME: str = settings.STORE_NAME
STORE_ADDRESS: str = settings.STORE_ADDRESS

# === Envíos ===
SHIPPING_LIMA_CENTS: int = settings.SHIPPING_LIMA_CENTS
SHIPPING_PROVINCES_CENTS: int = settings.SHIPPING_PROVINCES_CENTS
SHIPPING_FREE_THRESHOLD_CENTS: int = settings.SHIPPING_FREE_THRESHOLD_CENTS

# Representaciones legibles (S/ XX.xx)
SHIPPING_LIMA_PRICE: str = f"S/ {settings.SHIPPING_LIMA_CENTS / 100:.0f}"
SHIPPING_PROVINCES_PRICE: str = f"S/ {settings.SHIPPING_PROVINCES_CENTS / 100:.0f}"
SHIPPING_FREE_THRESHOLD: str = f"S/ {settings.SHIPPING_FREE_THRESHOLD_CENTS / 100:.0f}"

# === Horarios ===
SCHEDULE_WEEKDAY: str = settings.SCHEDULE_WEEKDAY
SCHEDULE_SATURDAY: str = settings.SCHEDULE_SATURDAY
SCHEDULE_SUNDAY: str = "Domingos: Cerrado 😴"

# === Descuentos ===
DISCOUNT_TWO_PRODUCTS: int = settings.DISCOUNT_TWO_PRODUCTS_PCT
DISCOUNT_THREE_PLUS: int = settings.DISCOUNT_THREE_PLUS_PCT

# === Límites del bot ===
HISTORY_MESSAGES_LIMIT: int = settings.HISTORY_MESSAGES_LIMIT
AI_MAX_PRODUCTS_CONTEXT: int = settings.AI_MAX_PRODUCTS_CONTEXT
AI_MAX_RECOMMENDATIONS: int = settings.AI_MAX_RECOMMENDATIONS
MESSAGE_COOLDOWN_SECONDS: float = settings.MESSAGE_COOLDOWN_SECONDS
AI_RESPONSE_MAX_CHARS: int = settings.AI_RESPONSE_MAX_CHARS

# Límites de descripción en catálogo y contexto IA
CATALOG_DESC_MAX_CHARS: int = 60
AI_DESC_MAX_CHARS: int = 90
