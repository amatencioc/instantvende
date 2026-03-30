"""Cargador y caché del perfil dinámico del bot (por vendor)."""
from __future__ import annotations

import json
import logging
import threading
from pathlib import Path
from typing import Any, Optional

from config import settings

_DEFAULT_PROFILE_PATH = Path(__file__).parent / "bot_profile.json"
_lock = threading.RLock()
# Caché por vendor_id: {vendor_id: dict}; None como clave = perfil por defecto
_cached_profiles: dict[Optional[int], dict] = {}
_loader_logger = logging.getLogger(__name__)


def load_default_profile() -> dict:
    """Carga el perfil por defecto desde el archivo JSON."""
    path_str = getattr(settings, "BOT_PROFILE_PATH", "")
    path = Path(path_str) if path_str else _DEFAULT_PROFILE_PATH
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    data.pop("_comment", None)
    return data


def get_profile(db=None, vendor_id: Optional[int] = None) -> dict:
    """
    Devuelve el perfil activo del vendor indicado.
    1. Intenta leer desde la base de datos filtrando por vendor_id.
    2. Fallback: usa el perfil por defecto del archivo JSON.
    Cachea el resultado en memoria para no hacer queries en cada mensaje.
    """
    global _cached_profiles
    with _lock:
        if db is not None:
            try:
                from database import BotProfile
                query = db.query(BotProfile)
                if vendor_id is not None:
                    query = query.filter(BotProfile.vendor_id == vendor_id)
                row = query.order_by(BotProfile.id.desc()).first()
                if row:
                    profile = json.loads(row.profile_json)
                    _cached_profiles[vendor_id] = profile
                    return profile
            except Exception as exc:
                _loader_logger.warning(
                    "No se pudo cargar el perfil desde la DB, usando fallback",
                    exc_info=exc,
                )
        if vendor_id not in _cached_profiles:
            _cached_profiles[vendor_id] = load_default_profile()
        return _cached_profiles[vendor_id]


def invalidate_cache(vendor_id: Optional[int] = None) -> None:
    """Invalida el caché en memoria para forzar recarga desde DB.

    Si se pasa vendor_id, sólo invalida el caché de ese vendor.
    Si se omite, invalida todo el caché.
    """
    global _cached_profiles
    with _lock:
        if vendor_id is not None:
            _cached_profiles.pop(vendor_id, None)
        else:
            _cached_profiles.clear()


def get_field(profile: dict, *keys: str, default: Any = None) -> Any:
    """Navega el perfil con una ruta de claves. Ej: get_field(p, 'bot', 'name')."""
    val = profile
    for key in keys:
        if not isinstance(val, dict):
            return default
        val = val.get(key, default)
        if val is default:
            return default
    return val
