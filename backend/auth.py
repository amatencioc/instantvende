"""Sistema de autenticación con API keys."""
import secrets

from fastapi import HTTPException, Security, status
from fastapi.security.api_key import APIKeyHeader

from config import settings

API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)


def verify_api_key(api_key: str = Security(API_KEY_HEADER)) -> str:
    """Valida la clave de API enviada en el encabezado X-API-Key.

    Usa secrets.compare_digest para evitar ataques de temporización.
    """
    expected = settings.API_SECRET_KEY
    if not api_key or not secrets.compare_digest(api_key, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key inválida o ausente",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    return api_key


def verify_api_key_optional(api_key: str = Security(API_KEY_HEADER)) -> str | None:
    """Igual que verify_api_key pero no lanza excepción si no se envía clave.

    Útil para endpoints que son públicos pero registran si el caller es autenticado.
    """
    expected = settings.API_SECRET_KEY
    if not api_key:
        return None
    if not secrets.compare_digest(api_key, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key inválida",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    return api_key
