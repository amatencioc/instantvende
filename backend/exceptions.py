"""Manejo robusto de errores: excepciones personalizadas y manejadores globales."""
from __future__ import annotations

from contextlib import contextmanager
from typing import Generator, Optional

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session


# ---------------------------------------------------------------------------
# Excepciones personalizadas
# ---------------------------------------------------------------------------

class InstantVendeException(Exception):
    """Excepción base del proyecto."""
    status_code: int = 500
    detail: str = "Error interno del servidor"

    def __init__(self, detail: str | None = None):
        self.detail = detail or self.__class__.detail
        super().__init__(self.detail)


class ProductNotFoundException(InstantVendeException):
    status_code = 404
    detail = "Producto no encontrado"


class ProductDuplicateException(InstantVendeException):
    status_code = 409
    detail = "Ya existe un producto con ese nombre"


class InsufficientStockException(InstantVendeException):
    status_code = 400
    detail = "Stock insuficiente"


class OrderNotFoundException(InstantVendeException):
    status_code = 404
    detail = "Pedido no encontrado"


class ConversationNotFoundException(InstantVendeException):
    status_code = 404
    detail = "Conversación no encontrada"


class InvalidStatusTransitionException(InstantVendeException):
    status_code = 422
    detail = "Transición de estado inválida"


class RateLimitException(InstantVendeException):
    status_code = 429
    detail = "Demasiadas solicitudes, espera un momento"


# ---------------------------------------------------------------------------
# Context manager para operaciones de BD
# ---------------------------------------------------------------------------

@contextmanager
def handle_db_errors(db: Optional[Session] = None) -> Generator[None, None, None]:
    """Context manager que convierte errores de SQLAlchemy en HTTPExceptions legibles."""
    try:
        yield
    except InstantVendeException:
        if db:
            db.rollback()
        raise
    except IntegrityError as exc:
        if db:
            db.rollback()
        raise ProductDuplicateException(
            f"Error de integridad en la base de datos: {exc.orig}"
        ) from exc
    except OperationalError as exc:
        if db:
            db.rollback()
        raise InstantVendeException(
            f"Error operacional en la base de datos: {exc.orig}"
        ) from exc
    except Exception as exc:
        if db:
            db.rollback()
        raise InstantVendeException(f"Error inesperado: {exc}") from exc


# ---------------------------------------------------------------------------
# Registro de manejadores en la aplicación FastAPI
# ---------------------------------------------------------------------------

def setup_exception_handlers(app: FastAPI) -> None:
    """Registra manejadores de excepción para toda la aplicación."""

    @app.exception_handler(InstantVendeException)
    async def instantvende_exception_handler(
        request: Request, exc: InstantVendeException
    ) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail, "error": type(exc).__name__},
        )

    @app.exception_handler(IntegrityError)
    async def integrity_error_handler(
        request: Request, exc: IntegrityError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=409,
            content={"detail": "Conflicto de datos — posible duplicado", "error": "IntegrityError"},
        )

    @app.exception_handler(OperationalError)
    async def operational_error_handler(
        request: Request, exc: OperationalError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=503,
            content={"detail": "Base de datos no disponible temporalmente", "error": "OperationalError"},
        )

    @app.exception_handler(RateLimitException)
    async def rate_limit_exception_handler(
        request: Request, exc: RateLimitException
    ) -> JSONResponse:
        return JSONResponse(
            status_code=429,
            content={"detail": exc.detail, "error": "RateLimitException"},
        )
