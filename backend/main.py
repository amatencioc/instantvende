import asyncio
import json
import os
import re
import urllib.request
import urllib.error
import random
import time
import threading
import concurrent.futures
import schedule
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException, Body, Security, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from pydantic import BaseModel, ConfigDict, field_validator
from typing import Generator, List, Optional, Dict
from datetime import datetime, timezone
import ollama

import bcrypt
import secrets
from config import settings
from auth import verify_api_key, verify_api_key_optional, API_KEY_HEADER
from exceptions import (
    setup_exception_handlers,
    handle_db_errors,
    ProductNotFoundException,
    ProductDuplicateException,
    InsufficientStockException,
    OrderNotFoundException,
    ConversationNotFoundException,
    RateLimitException,
)
from logger import setup_logger, log_with_context
from backup import BackupManager, start_backup_scheduler
from database import (
    SessionLocal, Product, Conversation, Message, CartItem, Order, OrderItem,
    BotProfile, Vendor, WhatsappSession,
)
from bot_profile_loader import get_profile, invalidate_cache, get_field, load_default_profile

# ===== LOGGING =====
logger = setup_logger()

# Advertencia si OLLAMA_TIMEOUT es muy bajo
if settings.OLLAMA_TIMEOUT < 10:
    logger.warning(
        "⚠️  OLLAMA_TIMEOUT es menor de 10 segundos — probablemente incorrecto",
        extra={"ollama_timeout": settings.OLLAMA_TIMEOUT},
    )

# ===== RATE LIMITING EN MEMORIA =====

class _BoundedCooldownStore:
    """Store de rate limiting con límite de entradas y limpieza automática."""

    def __init__(self, max_size: int = 10_000, ttl_seconds: float = 300):
        self._store: dict[str, float] = {}
        self._max_size = max_size
        self._ttl = ttl_seconds
        self._lock = threading.Lock()

    def check_and_set(self, key: str, cooldown: float) -> bool:
        """
        Retorna True si está en cooldown (debe rechazar).
        Retorna False si puede procesar (y registra el timestamp).
        """
        now = time.time()
        with self._lock:
            if len(self._store) >= self._max_size:
                cutoff = now - self._ttl
                expired = [k for k, v in self._store.items() if v < cutoff]
                for k in expired:
                    del self._store[k]

            last_ts = self._store.get(key)
            if last_ts is not None and (now - last_ts) < cooldown:
                return True  # en cooldown

            self._store[key] = now
            return False  # libre para procesar


_message_cooldowns = _BoundedCooldownStore(max_size=10_000, ttl_seconds=300)

# ===== EXECUTOR GLOBAL PARA OLLAMA =====
# Reutilizado entre requests para evitar que executor.shutdown(wait=True) bloquee el proceso
_ai_executor = concurrent.futures.ThreadPoolExecutor(
    max_workers=2,  # 1 activo + 1 en cola; evita bloquear FastAPI entre requests
    thread_name_prefix="ollama-worker",
)

# ===== LOCKS POR NÚMERO DE TELÉFONO =====
# Previene que el mismo número procese 2 mensajes en paralelo (causa raíz del bug del 2do mensaje)
_phone_locks: dict[str, threading.Lock] = {}
_phone_lock_last_used: dict[str, float] = {}
_phone_locks_meta_lock = threading.Lock()


def _get_phone_lock(phone: str) -> threading.Lock:
    """Retorna (o crea) el lock para un número de teléfono específico."""
    with _phone_locks_meta_lock:
        if phone not in _phone_locks:
            _phone_locks[phone] = threading.Lock()
        _phone_lock_last_used[phone] = time.time()
        return _phone_locks[phone]


def _cleanup_phone_locks(max_age_seconds: float = 3600.0):
    """Limpia locks de teléfonos inactivos para evitar memory leak.

    Solo elimina locks de números que no han sido usados en `max_age_seconds`.
    No intenta adquirir los locks, por lo que no puede causar falsos rate limits.
    """
    cutoff = time.time() - max_age_seconds
    with _phone_locks_meta_lock:
        to_delete = [
            phone for phone, last_used in _phone_lock_last_used.items()
            if last_used < cutoff
        ]
        for phone in to_delete:
            del _phone_locks[phone]
            del _phone_lock_last_used[phone]
    if to_delete:
        logger.info("Phone locks limpiados", extra={"count": len(to_delete)})

# ===== RESPUESTAS FRECUENTES (FAQ) =====

def build_faq_responses(profile: dict) -> dict:
    """Construye las respuestas FAQ usando el perfil activo del bot."""
    s = profile.get("store", {})
    sh = profile.get("shipping", {})
    sc = profile.get("schedule", {})
    d = profile.get("discounts", {})
    w = profile.get("warranty", {})
    p = profile.get("payments", {})

    payment_list = ", ".join(p.get("methods", ["Yape", "Plin"]))
    carriers = " y ".join(sh.get("carriers", ["Olva Courier", "Shalom"]))

    return {
        "horario": (
            f"📅 *Horario de Atención:*\n"
            f"• {sc.get('weekday', '')}\n"
            f"• {sc.get('saturday', '')}\n"
            f"• {sc.get('sunday', '')}\n\n"
            f"Si escribes fuera de horario, te respondo en cuanto abramos. ¿Te puedo ayudar en algo más? 😊"
        ),
        "envio": (
            f"🚚 *Envíos a todo el Perú:*\n"
            f"• Lima Metropolitana: {sh.get('lima_eta', '24-48h')} — {sh.get('lima_price_display', 'S/ 10')}\n"
            f"• Provincias: {sh.get('provinces_eta', '3-5 días')} — {sh.get('provinces_price_display', 'S/ 15')}\n"
            f"• 🎁 *GRATIS* en compras mayores a {sh.get('free_threshold_display', 'S/ 80')}\n\n"
            f"Trabajamos con {carriers}. ¿A qué distrito te envío? 😊"
        ),
        "pago": (
            f"💳 *Métodos de Pago:*\n"
            f"• {payment_list}\n\n"
            f"Todos seguros y con confirmación al instante. ¿Con cuál te queda mejor? 😊"
        ),
        "garantia": (
            f"✅ *Garantía {s.get('name', 'de la tienda')}:*\n"
            f"• {w.get('days', 30)} días de {w.get('description', 'satisfacción garantizada')}\n"
            f"• Si no te gusta → te devolvemos el dinero\n"
            f"• Productos 100% originales y de calidad\n"
            f"• Cambios sin costo si hay defecto de fábrica\n\n"
            f"¡Vendemos con confianza! ¿Qué producto te interesa? 😊"
        ),
        "ubicacion": (
            f"📍 *Encuéntranos:*\n"
            f"{s.get('name', '')}\n"
            f"{s.get('address', '')}\n\n"
            f"🛵 También hacemos delivery. ¿Prefieres venir o te lo enviamos? 😊"
        ),
        "descuento": (
            f"🏷️ *Descuentos y Promos:*\n"
            f"• Compra 2 productos → {d.get('two_products_pct', 10)}% de descuento\n"
            f"• Compra 3 o más → {d.get('three_plus_pct', 15)}% de descuento\n"
            f"• 🎁 Envío gratis comprando más de {d.get('free_shipping_threshold_display', 'S/ 80')}\n\n"
            f"¡Arma tu kit y ahorra! Escribe *#catalogo* para ver los productos. 😊"
        ),
        "devolucion": (
            f"🔄 *Cambios y Devoluciones:*\n"
            f"• Tienes *{w.get('days', 30)} días* desde la compra\n"
            f"• Producto en condiciones originales\n"
            f"• Coordinamos el recojo sin costo\n"
            f"• Reembolso al mismo método de pago\n\n"
            f"Somos flex, ¡tu satisfacción es lo primero! ¿Tuviste algún problema con tu pedido?"
        ),
        "combo": (
            f"🎁 *Kits y Combos recomendados:*\n"
            f"• Compra 2 productos → {d.get('two_products_pct', 10)}% de descuento\n"
            f"• Compra 3 o más → {d.get('three_plus_pct', 15)}% de descuento\n\n"
            f"Escribe *#catalogo* para verlos todos y armar tu combo. 😊"
        ),
    }

# ===== KEYWORDS PARA FAQ (base genérica — se extiende con valores del perfil activo) =====
_FAQ_KEYWORDS_BASE = {
    "horario":    ["horario", "hora", "cuando abren", "cuando cierran", "atienden", "abierto",
                   "disponible hoy", "abren", "trabajan"],
    "envio":      ["envio", "envío", "delivery", "despacho", "entregar", "llega", "demora",
                   "tiempo de entrega", "cuanto demora", "courier", "provincia", "envian", "envían"],
    "pago":       ["pago", "pagar", "transferencia", "efectivo", "deposito", "depósito",
                   "como pago", "cómo pago"],
    "garantia":   ["garantia", "garantía", "calidad", "original", "es bueno", "sirve",
                   "funciona", "confiable", "seguro"],
    "devolucion": ["devolucion", "devolución", "cambio", "cambiar", "devolver", "mal estado",
                   "defecto", "falla", "no funciono", "no funcionó", "reembolso"],
    "ubicacion":  ["ubicacion", "ubicación", "dirección", "donde", "direccion", "local",
                   "tienda", "visitar", "ir a la tienda"],
    "descuento":  ["descuento", "promo", "promocion", "promoción", "oferta", "barato",
                   "precio especial", "rebaja", "mas barato", "más barato"],
    "combo":      ["combo", "kit", "pack", "paquete", "varios productos", "set",
                   "todos los productos", "conjunto"],
}


def build_faq_keywords(profile: dict) -> dict:
    """Extiende los keywords de FAQ con valores dinámicos del perfil activo."""
    keywords = {k: list(v) for k, v in _FAQ_KEYWORDS_BASE.items()}
    # Carriers del perfil → keywords de envío
    for carrier in get_field(profile, "shipping", "carriers", default=[]):
        kw = carrier.lower().strip()
        if kw and kw not in keywords["envio"]:
            keywords["envio"].append(kw)
    # Métodos de pago → palabras clave de pago
    for method in get_field(profile, "payments", "methods", default=[]):
        for word in re.split(r"[\s/]+", method.lower()):
            word = word.strip(".,")
            if len(word) > 2 and word not in keywords["pago"]:
                keywords["pago"].append(word)
    # Dirección / nombre de tienda → palabras clave de ubicación
    address = get_field(profile, "store", "address", default="")
    for part in re.split(r"[,\s]+", address.lower()):
        part = part.strip(".,")
        if len(part) > 3 and not part.isdigit() and part not in keywords["ubicacion"]:
            keywords["ubicacion"].append(part)
    return keywords

# ===== COMANDOS DEL BOT =====
BOT_COMMANDS = {
    "catalog":    [
        "#catalogo", "#catálogo",
        "ver productos", "mostrar productos", "lista de productos",
        "que productos tienen", "qué productos tienen",
        "que tienen", "qué tienen",
        "que vendes", "qué vendes",
        "que venden", "qué venden",
        "que productos", "qué productos",
        "que hay", "qué hay",
        "que tienes", "qué tienes",
        "que productos hay", "qué productos hay",
        "ver catalogo", "ver catálogo",
        "mostrar catalogo", "mostrar catálogo",
    ],
    "cart":       ["#carrito", "mi carrito", "ver carrito", "ver mi carrito"],
    "order":      ["#pedido", "hacer pedido", "confirmar pedido", "quiero pedir", "confirmar compra"],
    "clear_cart": ["#limpiar", "limpiar carrito", "vaciar carrito", "borrar carrito"],
    "help":       ["#ayuda", "ayuda", "help", "comandos", "como funciona"],
    "status":     ["#estado", "mi pedido", "estado de mi pedido", "donde esta mi pedido", "donde está mi pedido"],
}

BOT_HELP_TEXT = """🤖 *COMANDOS DISPONIBLES*
─────────────────────────
📋 *#catalogo* → Ver todos los productos
🛒 *#carrito* → Ver tu carrito
📦 *#pedido* → Confirmar tu pedido
🗑️ *#limpiar* → Vaciar carrito
📊 *#estado* → Estado de tu último pedido
❓ *#ayuda* → Ver esta ayuda

💬 También puedes escribirme naturalmente y te ayudo 😊"""


def detect_command(message: str) -> Optional[str]:
    """Detecta si el mensaje es un comando específico del bot"""
    message_lower = message.lower().strip()
    for command, triggers in BOT_COMMANDS.items():
        if any(message_lower == trigger or message_lower.startswith(trigger) or trigger in message_lower for trigger in triggers):
            return command
    if re.match(r'^(agregar|añadir|quiero el|dame el|producto)\s+\d+', message_lower):
        return "add_to_cart"
    return None


def generate_catalog(products: List, profile: dict) -> str:
    """Genera catálogo formateado para WhatsApp"""
    if not products:
        return "😔 No tenemos productos disponibles en este momento. ¡Vuelve pronto!"

    store_name = get_field(profile, "store", "name", default="TIENDA")

    catalog = f"📦 *CATÁLOGO DE PRODUCTOS*\n"
    catalog += "─" * 26 + "\n"

    for i, p in enumerate(products, 1):
        price_fmt = f"S/ {p.price / 100:.2f}"
        if p.stock > 5:
            stock_str = f"✅ Disponible ({p.stock} unidades)"
        elif p.stock > 0:
            stock_str = f"⚠️ Últimas {p.stock} unidades"
        else:
            stock_str = "❌ Agotado"

        catalog += f"\n*{i}. {p.name}*\n"
        catalog += f"💰 {price_fmt}\n"
        catalog += f"📝 {p.description}\n"
        catalog += f"{stock_str}\n"

    catalog += "\n" + "─" * 26 + "\n"
    catalog += "🛒 Para agregar: escribe *agregar 1*, *agregar 2*, etc.\n"
    catalog += "📋 Ver carrito: *#carrito*\n"
    catalog += "📦 Confirmar pedido: *#pedido*"
    return catalog


def generate_cart_display(cart_items: List, products_dict: Dict) -> str:
    """Genera vista formateada del carrito"""
    if not cart_items:
        return "🛒 Tu carrito está vacío.\n\nEscribe *#catalogo* para ver nuestros productos."

    display = "🛒 *TU CARRITO*\n"
    display += "─" * 25 + "\n\n"
    total = 0
    for item in cart_items:
        product = products_dict.get(item.product_id)
        if product:
            subtotal = product.price * item.quantity
            total += subtotal
            display += f"• *{product.name}*\n"
            display += f"  {item.quantity} x S/ {product.price / 100:.2f} = S/ {subtotal / 100:.2f}\n\n"
    display += "─" * 25 + "\n"
    display += f"💰 *TOTAL: S/ {total / 100:.2f}*\n\n"
    display += "✅ Confirmar pedido: *#pedido*\n"
    display += "🗑️ Vaciar carrito: *#limpiar*"
    return display


# ===== DETECCIÓN DE INTENCIONES =====

# Palabras que sugieren que el cliente describe un PROBLEMA (quiere recomendación)
RECOMMENDATION_TRIGGERS = [
    "sucio", "manchado", "opaco", "rayado", "desgastado", "roto", "despegado",
    "oloroso", "olor", "humedo", "húmedo", "mojado", "viejo", "feo", "dañado",
    "cuero", "ante", "gamuza", "lona", "tela", "goma", "suela", "zapatilla",
    "zapato", "bota", "mocasin", "moccasin", "sandalia", "como limpio",
    "como puedo", "cómo limpio", "cómo puedo", "que producto", "qué producto",
    "me recomiendas", "me recomiendan", "sirve para", "mejor para"
]

# Palabras que indican objeción de precio
PRICE_OBJECTION_TRIGGERS = [
    "es caro", "muy caro", "cuesta mucho", "no tengo tanto", "mas barato",
    "más barato", "algo economico", "algo económico", "precio alto"
]


def detect_intent(message: str, profile: dict | None = None) -> dict:
    """Detecta la intención del mensaje del cliente con tipos extendidos"""
    message_lower = message.lower().strip()

    intent = {
        "type": "general",  # general, faq, purchase, recommendation, price_objection, greeting, goodbye, complaint
        "faq_topic": None,
        "confidence": 0.0,
        "signals": []   # palabras clave que dispararon el intent
    }

    # --- Saludo (primero: evita falsos positivos si el saludo tiene otras palabras) ---
    greeting_keywords = [
        "hola", "buenos dias", "buenos días", "buenas tardes", "buenas noches",
        "buenas", "hey", "hi", "saludos", "buen dia", "buen día",
        "ola", "wenas", "wenas tardes", "buenas tarde",  # variantes y errores tipográficos
        "me brinda", "me pueden", "me puedes",  # frases de solicitud de atención
    ]
    matched_greetings = [kw for kw in greeting_keywords if kw in message_lower]
    if matched_greetings and len(message_lower.split()) <= 10:
        intent["type"] = "greeting"
        intent["confidence"] = 0.95
        intent["signals"] = matched_greetings
        return intent

    # --- Despedida ---
    goodbye_keywords = [
        "gracias", "muchas gracias", "chau", "chao", "adios", "adiós",
        "hasta luego", "bye", "nos vemos", "hasta pronto", "ok gracias"
    ]
    matched_goodbyes = [kw for kw in goodbye_keywords if kw in message_lower]
    if matched_goodbyes:
        intent["type"] = "goodbye"
        intent["confidence"] = 0.9
        intent["signals"] = matched_goodbyes
        return intent

    # --- FAQ (alta prioridad si hay match directo) ---
    faq_kws = build_faq_keywords(profile) if profile else _FAQ_KEYWORDS_BASE
    for topic, keywords in faq_kws.items():
        matched = [kw for kw in keywords if kw in message_lower]
        if matched:
            intent["type"] = "faq"
            intent["faq_topic"] = topic
            intent["confidence"] = 0.9
            intent["signals"] = matched
            return intent

    # --- Objeción de precio ---
    price_signals = [kw for kw in PRICE_OBJECTION_TRIGGERS if kw in message_lower]
    if price_signals:
        intent["type"] = "price_objection"
        intent["confidence"] = 0.85
        intent["signals"] = price_signals
        return intent

    # --- Queja / problema con un pedido ---
    complaint_keywords = [
        "llegó mal", "llego mal", "no llegó", "no llego", "estaba roto",
        "estaba malo", "problema con", "no funciona", "queja", "reclamacion",
        "reclamación", "mal servicio"
    ]
    complaint_signals = [kw for kw in complaint_keywords if kw in message_lower]
    if complaint_signals:
        intent["type"] = "complaint"
        intent["confidence"] = 0.9
        intent["signals"] = complaint_signals
        return intent

    # --- Intención de compra directa ---
    purchase_keywords = [
        "quiero comprar", "lo quiero", "lo llevo", "me interesa comprarlo",
        "quiero pedirlo", "cuánto cuesta", "cuanto cuesta", "cuanto sale",
        "disponible", "hay stock", "pedido", "ordenar", "comprar",
        "me lo mandas", "envíame", "envíame uno", "quiero uno"
    ]
    purchase_signals = [kw for kw in purchase_keywords if kw in message_lower]
    if purchase_signals:
        intent["type"] = "purchase"
        intent["confidence"] = 0.85
        intent["signals"] = purchase_signals
        return intent

    # --- Recomendación: cliente describe un problema o tipo de calzado ---
    rec_signals = [kw for kw in RECOMMENDATION_TRIGGERS if kw in message_lower]
    if rec_signals:
        intent["type"] = "recommendation"
        intent["confidence"] = 0.8
        intent["signals"] = rec_signals
        return intent

    return intent


def get_greeting_by_time(timezone_str: str = "America/Lima") -> str:
    """Devuelve saludo según la zona horaria configurada en el perfil del bot."""
    _fallback_offsets = {
        "America/Lima": -5, "America/Bogota": -5, "America/Guayaquil": -5,
        "America/Santiago": -4, "America/Mexico_City": -6, "America/Caracas": -4,
        "America/Buenos_Aires": -3, "America/Sao_Paulo": -3,
    }
    try:
        from zoneinfo import ZoneInfo
        tz = ZoneInfo(timezone_str)
        hour = datetime.now(tz).hour
    except Exception:
        from datetime import timezone as _tz, timedelta
        offset = _fallback_offsets.get(timezone_str, -5)
        hour = datetime.now(_tz(timedelta(hours=offset))).hour
    if hour < 12:
        return "Buenos días"
    elif hour < 20:
        return "Buenas tardes"
    else:
        return "Buenas noches"


def get_product_recommendations(message: str, products: List, max_recommendations: int = 3) -> List:
    """Filtra productos relevantes según palabras clave del mensaje"""
    if not products:
        return []

    message_lower = message.lower()

    # Mapeo problema/material → palabras clave de productos
    category_map = {
        "cuero":     ["cuero", "leather", "crema", "restaura", "brillo"],
        "ante":      ["ante", "gamuza", "nubuck", "suede", "borrador"],
        "tela":      ["tela", "lona", "canvas", "limpiador", "espuma"],
        "zapatilla": ["zapatilla", "sneaker", "deporte", "limpiador", "blanco"],
        "suela":     ["suela", "pegamento", "pega", "despegado"],
        "olor":      ["olor", "desodorante", "fresco", "aroma"],
        "impermeable": ["agua", "lluvia", "impermeable", "protector"],
    }

    relevant_product_keywords = set()
    for category, triggers in category_map.items():
        if any(t in message_lower for t in triggers):
            relevant_product_keywords.update(triggers)

    if not relevant_product_keywords:
        return products[:max_recommendations]  # devuelve los primeros si no hay match

    scored = []
    for p in products:
        product_text = (p.name + " " + p.description).lower()
        score = sum(1 for kw in relevant_product_keywords if kw in product_text)
        if score > 0:
            scored.append((score, p))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [p for _, p in scored[:max_recommendations]] if scored else products[:max_recommendations]

def _backup_loop() -> None:
    """Hilo daemon que realiza backups periódicos de la base de datos SQLite."""
    start_backup_scheduler(
        interval_hours=settings.BACKUP_INTERVAL_HOURS,
        max_backups=settings.MAX_BACKUPS,
    )
    # Limpiar phone locks sin uso cada N horas para evitar memory leak
    schedule.every(settings.BACKUP_INTERVAL_HOURS).hours.do(_cleanup_phone_locks)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Pre-cargar modelo Ollama de forma asíncrona usando el executor global
    logger.info("⏳ Pre-cargando modelo Ollama...")
    try:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            _ai_executor,
            lambda: ollama.chat(
                model=settings.OLLAMA_MODEL,
                # 'hola' dispara el procesamiento en español — más representativo del uso real
                messages=[{'role': 'user', 'content': 'hola'}],
                # num_predict=1 minimiza el trabajo; num_thread coincide con el default de runtime
                options={'num_predict': 1, 'num_thread': 4}
            )
        )
        logger.info("✅ Modelo Ollama pre-calentado")
    except Exception as e:
        logger.warning("⚠️  No se pudo pre-calentar Ollama", extra={"error": str(e)})

    # Backup inicial al arrancar el servidor
    _mgr = BackupManager(max_backups=settings.MAX_BACKUPS)
    try:
        path = _mgr.create_backup()
        _mgr.cleanup_old_backups()
        log_with_context(logger, "info", "Backup inicial creado", path=path)
    except Exception as exc:
        log_with_context(logger, "warning", "Backup inicial falló", error=str(exc))
    # Hilo daemon de backup periódico (se cierra automáticamente con el proceso)
    threading.Thread(target=_backup_loop, daemon=True).start()
    yield
    # Apagar el executor global limpiamente al cerrar el servidor
    _ai_executor.shutdown(wait=False)


app = FastAPI(title="InstantVende API", version="1.0.0-mvp", lifespan=lifespan)
setup_exception_handlers(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_vendor(
    api_key: str = Security(API_KEY_HEADER),
    db: Session = Depends(get_db),
) -> Vendor:
    """Autentica la solicitud y retorna el Vendor dueño de la API key.

    Cada vendor tiene su propia API key única generada al registrarse.
    Nunca se confía en vendor_id enviado por el cliente en el body.
    """
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key inválida o ausente",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    vendor = db.query(Vendor).filter(
        Vendor.api_key == api_key,
        Vendor.is_active.is_(True),
    ).first()
    if not vendor:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key inválida o ausente",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    return vendor


def get_or_create_conversation(db: Session, phone: str, vendor_id: int, customer_name: Optional[str] = None) -> "Conversation":
    """Obtiene o crea una conversación de forma thread-safe, filtrada por vendor."""
    conversation = db.query(Conversation).filter(
        Conversation.phone == phone,
        Conversation.vendor_id == vendor_id,
    ).first()

    if conversation:
        if customer_name and not conversation.customer_name:
            conversation.customer_name = customer_name
            db.commit()
        return conversation

    try:
        conversation = Conversation(phone=phone, vendor_id=vendor_id, customer_name=customer_name)
        db.add(conversation)
        db.commit()
        db.refresh(conversation)
        return conversation
    except IntegrityError:
        db.rollback()
        conversation = db.query(Conversation).filter(
            Conversation.phone == phone,
            Conversation.vendor_id == vendor_id,
        ).first()
        if not conversation:
            raise
        return conversation

class ProductCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str
    description: str
    price: int
    stock: int
    image_url: Optional[str] = None

    @field_validator("name")
    @classmethod
    def name_valid(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("El nombre no puede estar vacío")
        if len(v) > 200:
            raise ValueError("El nombre no puede superar 200 caracteres")
        return v

    @field_validator("description")
    @classmethod
    def description_valid(cls, v: str) -> str:
        if len(v) > 2000:
            raise ValueError("La descripción no puede superar 2000 caracteres")
        return v.strip()

    @field_validator("price")
    @classmethod
    def price_valid(cls, v: int) -> int:
        if v < 1:
            raise ValueError("El precio debe ser mayor a 0 centavos")
        if v > 100_000_00:  # S/ 100,000 en centavos
            raise ValueError("El precio excede el límite permitido")
        return v

    @field_validator("stock")
    @classmethod
    def stock_valid(cls, v: int) -> int:
        if v < 0:
            raise ValueError("El stock no puede ser negativo")
        if v > 100_000:
            raise ValueError("El stock no puede superar 100,000 unidades")
        return v

    @field_validator("image_url")
    @classmethod
    def image_url_valid(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            v = v.strip()
            if v and not (v.startswith("http://") or v.startswith("https://")):
                raise ValueError("image_url debe ser una URL válida (http/https)")
        return v or None


class MessageRequest(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    phone: str
    message: str
    customer_name: Optional[str] = None

    @field_validator("phone")
    @classmethod
    def phone_valid(cls, v: str) -> str:
        digits = re.sub(r"\D", "", v)
        if len(digits) < 7 or len(digits) > 15:
            raise ValueError("Número de teléfono inválido (7-15 dígitos)")
        return digits

    @field_validator("message")
    @classmethod
    def message_valid(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("El mensaje no puede estar vacío")
        if len(v) > 4096:
            raise ValueError("El mensaje no puede superar 4096 caracteres")
        return v


class CartItemRequest(BaseModel):
    product_id: int
    quantity: int = 1

    @field_validator("product_id")
    @classmethod
    def product_id_valid(cls, v: int) -> int:
        if v < 1:
            raise ValueError("ID de producto inválido")
        return v

    @field_validator("quantity")
    @classmethod
    def quantity_valid(cls, v: int) -> int:
        if v < 1:
            raise ValueError("La cantidad debe ser al menos 1")
        if v > 100:
            raise ValueError("La cantidad no puede superar 100 unidades por artículo")
        return v


class OrderCreateRequest(BaseModel):
    phone: str
    notes: Optional[str] = None

    @field_validator("phone")
    @classmethod
    def phone_valid(cls, v: str) -> str:
        digits = re.sub(r"\D", "", v)
        if len(digits) < 7 or len(digits) > 15:
            raise ValueError("Número de teléfono inválido (7-15 dígitos)")
        return digits

    @field_validator("notes")
    @classmethod
    def notes_valid(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and len(v) > 1000:
            raise ValueError("Las notas no pueden superar 1000 caracteres")
        return v


class OrderStatusUpdate(BaseModel):
    status: str

    @field_validator("status")
    @classmethod
    def status_valid(cls, v: str) -> str:
        allowed = {"pending", "confirmed", "shipped", "delivered", "cancelled"}
        if v not in allowed:
            raise ValueError(f"Estado inválido. Permitidos: {', '.join(sorted(allowed))}")
        return v

@app.get("/api/products")
def get_products(
    db: Session = Depends(get_db),
    current_vendor: Vendor = Depends(get_current_vendor),
):
    return db.query(Product).filter(Product.vendor_id == current_vendor.id).all()

@app.post("/api/products")
def create_product(
    product: ProductCreate,
    db: Session = Depends(get_db),
    current_vendor: Vendor = Depends(get_current_vendor),
):
    with handle_db_errors(db):
        existing = db.query(Product).filter(
            Product.name == product.name,
            Product.vendor_id == current_vendor.id,
        ).first()
        if existing:
            raise ProductDuplicateException(f"Ya existe un producto con el nombre '{product.name}'")
        db_product = Product(**product.model_dump(), vendor_id=current_vendor.id)
        db.add(db_product)
        db.commit()
        db.refresh(db_product)
        log_with_context(logger, "info", "Producto creado", product_name=product.name, product_id=db_product.id)
        return db_product

@app.put("/api/products/{product_id}")
def update_product(
    product_id: int,
    product: ProductCreate,
    db: Session = Depends(get_db),
    current_vendor: Vendor = Depends(get_current_vendor),
):
    """Actualizar un producto existente"""
    db_product = db.query(Product).filter(
        Product.id == product_id,
        Product.vendor_id == current_vendor.id,
    ).first()
    if not db_product:
        raise ProductNotFoundException(f"Producto {product_id} no encontrado")

    with handle_db_errors(db):
        if product.name != db_product.name:
            existing = db.query(Product).filter(
                Product.name == product.name,
                Product.vendor_id == current_vendor.id,
                Product.id != product_id,
            ).first()
            if existing:
                raise ProductDuplicateException(f"Ya existe un producto con el nombre '{product.name}'")

        for field, value in product.model_dump().items():
            setattr(db_product, field, value)

        db.commit()
        db.refresh(db_product)
        log_with_context(logger, "info", "Producto actualizado", product_id=product_id)
        return db_product

@app.delete("/api/products/{product_id}")
def delete_product(
    product_id: int,
    db: Session = Depends(get_db),
    current_vendor: Vendor = Depends(get_current_vendor),
):
    """Eliminar un producto"""
    db_product = db.query(Product).filter(
        Product.id == product_id,
        Product.vendor_id == current_vendor.id,
    ).first()
    if not db_product:
        raise ProductNotFoundException(f"Producto {product_id} no encontrado")

    with handle_db_errors(db):
        db.delete(db_product)
        db.commit()
        log_with_context(logger, "info", "Producto eliminado", product_id=product_id)
        return {"message": f"Producto {product_id} eliminado exitosamente"}

def generate_ai_response(message: str, products: List[Product], profile: dict, conversation_history: List[str] = None, recently_viewed: List[str] = None) -> str:
    """
    Genera respuesta inteligente con personalidad y detección de intención
    """
    ai_cfg = profile.get("ai", {})
    msgs_cfg = profile.get("messages", {})
    bot_name = get_field(profile, "bot", "name", default="Favio")
    store_name = get_field(profile, "store", "name", default="la tienda")
    warranty_days = get_field(profile, "warranty", "days", default=30)
    discount_two = get_field(profile, "discounts", "two_products_pct", default=10)
    max_products_ctx = ai_cfg.get("max_products_in_context", 8)
    max_recommendations = ai_cfg.get("max_recommendations", 3)
    max_chars = ai_cfg.get("response_max_chars", 1000)
    history_limit = ai_cfg.get("history_messages_limit", 6)
    ai_desc_chars = profile.get("catalog", {}).get("ai_description_chars", 90)
    tz_str = get_field(profile, "schedule", "timezone", default="America/Lima")

    # Detectar intención del mensaje
    intent = detect_intent(message, profile)

    # Si es una pregunta FAQ, responder directamente (más rápido)
    if intent["type"] == "faq" and intent["faq_topic"]:
        log_with_context(logger, "info", "FAQ detectada", topic=intent["faq_topic"])
        faq = build_faq_responses(profile)
        return faq.get(intent["faq_topic"], msgs_cfg.get("error_general", "Disculpa, tuve un problemita técnico 😅 Escribe *#catalogo* o *#ayuda*."))

    # Si es saludo
    if intent["type"] == "greeting":
        saludo = get_greeting_by_time(tz_str)
        is_returning = bool(conversation_history)
        if is_returning:
            templates = msgs_cfg.get("greeting_returning", [
                f"¡{{saludo}}! 👋 Qué bueno verte de vuelta. Soy {{bot_name}}. ¿Volvemos con los zapatos? 😄",
            ])
        else:
            templates = msgs_cfg.get("greeting_new", [
                f"¡{{saludo}}! 👋 Soy {{bot_name}} de *{{store_name}}*. Escribe *#catalogo* para ver todo. ¿Qué tipo de zapatos quieres cuidar?",
            ])
        template = random.choice(templates)
        return template.format(saludo=saludo, bot_name=bot_name, store_name=store_name)

    # Si es despedida
    if intent["type"] == "goodbye":
        templates = msgs_cfg.get("goodbye", [
            "¡Un placer atenderte! 🙌 Si necesitas algo más, aquí estoy. ¡Que te vaya bien!",
        ])
        return random.choice(templates)

    # Queja: responder con empatía primero
    if intent["type"] == "complaint":
        template = msgs_cfg.get(
            "complaint_response",
            "Oye, lamento mucho escuchar eso. 😔 Tu satisfacción es lo más importante. Cuéntame qué pasó y lo resolvemos de inmediato. Tenemos garantía de {warranty_days} días.",
        )
        return template.format(warranty_days=warranty_days)

    # Objeción de precio: reconocer y redirigir
    if intent["type"] == "price_objection":
        template = msgs_cfg.get(
            "price_objection_response",
            "Entiendo perfectamente, el presupuesto importa. 💰 Tenemos opciones desde poco, y comprar 2 productos te da {discount_two}% de descuento. ¿Cuánto quieres invertir? 😊",
        )
        return template.format(discount_two=discount_two)

    # Enriquecer la lista de productos con recomendaciones inteligentes
    recommended = get_product_recommendations(message, products, max_recommendations)
    all_products = products[:max_products_ctx]

    def fmt_product(p: Product) -> str:
        stock_label = (
            "✅ disponible" if p.stock > 5
            else (f"⚠️ últimas {p.stock} unidades" if p.stock > 0
                  else "❌ agotado")
        )
        price_fmt = f"S/ {p.price / 100:.2f}"
        desc = p.description[:ai_desc_chars] if len(p.description) > ai_desc_chars else p.description
        return (
            f"  • *{p.name}* — {price_fmt} | {stock_label}\n"
            f"    Descripción: {desc}"
        )

    if recommended:
        rec_context = "PRODUCTOS RECOMENDADOS para este cliente:\n" + "\n".join(fmt_product(p) for p in recommended)
    else:
        rec_context = ""

    if all_products:
        all_context = "CATÁLOGO COMPLETO DISPONIBLE:\n" + "\n".join(fmt_product(p) for p in all_products)
    else:
        all_context = "Sin productos en stock en este momento."

    # Historial: últimos N mensajes (más antiguos primero)
    history_context = ""
    if conversation_history:
        history_context = f"\n\n📜 HISTORIAL RECIENTE (últimos mensajes):\n" + "\n".join(conversation_history[-history_limit:])

    # Carrito activo
    cart_context = ""
    if recently_viewed:
        cart_context = f"\n\n🛒 CARRITO ACTIVO: {len(recently_viewed)} producto(s) ya en el carrito. Motiva al cliente a confirmar con *#pedido*."

    # Señales del intent para guiar la respuesta
    intent_hint = ""
    if intent["type"] == "recommendation":
        intent_hint = f"\n\n🎯 El cliente DESCRIBE UN PROBLEMA: {', '.join(intent.get('signals', []))}. Diagnostica y recomienda el producto exacto."
    elif intent["type"] == "purchase":
        intent_hint = "\n\n💰 El cliente QUIERE COMPRAR. Confirma disponibilidad, menciona precio y redirige a *#catalogo* o *agregar [número]*."

    saludo_hora = get_greeting_by_time(tz_str)

    # Construir el system prompt desde la plantilla del perfil
    catchphrases = get_field(profile, "bot", "catchphrases", default=[])
    catchphrases_str = ", ".join(catchphrases) if catchphrases else "pe, bacán"
    payment_methods = ", ".join(get_field(profile, "payments", "methods", default=["Yape", "Plin"]))

    template_str = profile.get("system_prompt_template", "")
    fmt_vars = {
        "bot_name": bot_name,
        "bot_role": get_field(profile, "bot", "role", default="vendedor estrella"),
        "store_name": store_name,
        "experience_years": get_field(profile, "bot", "experience_years", default=5),
        "store_type": get_field(profile, "store", "type", default="tienda"),
        "language_style": get_field(profile, "bot", "language_style", default="natural"),
        "catchphrases": catchphrases_str,
        "max_emojis": get_field(profile, "bot", "max_emojis_per_response", default=2),
        "response_language": get_field(profile, "bot", "response_language", default="español"),
        "rec_context": rec_context,
        "all_context": all_context,
        "lima_eta": get_field(profile, "shipping", "lima_eta", default="24-48h"),
        "lima_price": get_field(profile, "shipping", "lima_price_display", default="S/ 10"),
        "provinces_eta": get_field(profile, "shipping", "provinces_eta", default="3-5 días"),
        "provinces_price": get_field(profile, "shipping", "provinces_price_display", default="S/ 15"),
        "free_threshold": get_field(profile, "shipping", "free_threshold_display", default="S/ 80"),
        "payment_methods": payment_methods,
        "warranty_days": warranty_days,
        "current_greeting": saludo_hora,
        "weekday_schedule": get_field(profile, "schedule", "weekday", default=""),
        "saturday_schedule": get_field(profile, "schedule", "saturday", default=""),
        "history_context": history_context,
        "cart_context": cart_context,
        "intent_hint": intent_hint,
    }
    try:
        system_prompt = template_str.format(**fmt_vars)
    except (KeyError, ValueError) as fmt_err:
        log_with_context(logger, "warning", "Error formateando system_prompt_template", error=str(fmt_err))
        system_prompt = f"Eres {bot_name}, el vendedor de {store_name}. Ayuda al cliente a encontrar el producto correcto.\n\n{rec_context}\n\n{all_context}{history_context}{cart_context}{intent_hint}"

    try:
        start_time = time.time()
        log_with_context(logger, "info", "Generando respuesta con IA", intent=intent['type'])

        ollama_messages = [
            {'role': 'system', 'content': system_prompt},
            {'role': 'user', 'content': message}
        ]
        ollama_options = {
            'temperature': ai_cfg.get("ollama_temperature", 0.8),
            'num_predict': ai_cfg.get("ollama_num_predict", 80),
            'num_ctx': ai_cfg.get("ollama_num_ctx", 1024),
            'top_p': ai_cfg.get("ollama_top_p", 0.9),
            'repeat_penalty': ai_cfg.get("ollama_repeat_penalty", 1.2),
            'num_thread': ai_cfg.get("ollama_num_thread", 4),
        }

        # Llamada con timeout usando el executor global (no bloquea FastAPI entre requests)
        future = _ai_executor.submit(
            ollama.chat,
            model=settings.OLLAMA_MODEL,
            messages=ollama_messages,
            options=ollama_options
        )
        try:
            response = future.result(timeout=settings.OLLAMA_TIMEOUT)
        except concurrent.futures.TimeoutError:
            future.cancel()
            log_with_context(logger, "warning", "Ollama timeout", timeout=settings.OLLAMA_TIMEOUT)
            return msgs_cfg.get(
                "error_timeout",
                "¡Hola! 👋 Mientras proceso tu pregunta, echa un vistazo a nuestros productos con *#catalogo*. ¿Te puedo ayudar con algo específico? 😊",
            )

        elapsed = time.time() - start_time
        ai_message = response['message']['content'].strip()

        # Fallback si Ollama devuelve respuesta vacía o solo espacios
        if not ai_message:
            log_with_context(logger, "warning", "Ollama devolvió respuesta vacía")
            return msgs_cfg.get(
                "error_general",
                "Disculpa, tuve un problemita técnico 😅 Escribe *#catalogo* o *#ayuda*.",
            )

        # Truncar respuesta excesivamente larga al último punto, interrogación o salto de línea
        if len(ai_message) > max_chars:
            truncated = ai_message[:max_chars]
            # Buscar el último punto, signo de interrogación o exclamación para corte limpio
            last_break = max(
                truncated.rfind('.'),
                truncated.rfind('?'),
                truncated.rfind('!'),
                truncated.rfind('\n')
            )
            if last_break > max_chars // 3:  # más permisivo — acepta cortes desde 1/3 del texto
                ai_message = truncated[:last_break + 1].strip()
            else:
                # Si no hay punto limpio, añadir CTA de cierre
                ai_response_ending = msgs_cfg.get(
                    "response_truncated_suffix",
                    "\n\nEscribe *#catalogo* para ver todos los productos o *#ayuda* para más opciones. 😊"
                )
                ai_message = truncated.rstrip() + ai_response_ending

        # Post-procesado según intent (evitar sufijos duplicados)
        if intent["type"] == "purchase" and "#catalogo" not in ai_message and "agregar" not in ai_message.lower():
            if "?" not in ai_message:
                ai_message += " Escribe *#catalogo* para verlos todos."
        elif intent["type"] == "recommendation" and "agregar" not in ai_message.lower() and "#catalogo" not in ai_message:
            ai_message += " Escribe *#catalogo* para verlo. 😊"

        log_with_context(logger, "info", "Respuesta IA generada", elapsed=round(elapsed, 2), intent=intent['type'])
        return ai_message

    except Exception as e:
        log_with_context(logger, "error", "Error generando respuesta IA", error=str(e))
        return msgs_cfg.get(
            "error_general",
            "Disculpa, tuve un problemita técnico 😅 Escribe *#catalogo* o *#ayuda*.",
        )

@app.post("/api/process-message")
def process_message(
    request: MessageRequest,
    db: Session = Depends(get_db),
    current_vendor: Vendor = Depends(get_current_vendor),
):
    """Procesar mensaje con IA, comandos y manejo de carrito/pedidos"""

    log_with_context(logger, "info", "Nuevo mensaje recibido", phone=request.phone[-4:], msg_preview=request.message[:100])

    # Cargar perfil activo del vendor (con fallback a JSON por defecto)
    profile = get_profile(db, vendor_id=current_vendor.id)
    ai_cfg = profile.get("ai", {})
    msgs_cfg = profile.get("messages", {})
    bot_name = get_field(profile, "bot", "name", default="Favio")
    # MESSAGE_COOLDOWN_SECONDS es configuración de servidor, no del perfil del bot
    message_cooldown = settings.MESSAGE_COOLDOWN_SECONDS

    # Lock por teléfono: previene procesamiento paralelo del mismo usuario
    # (causa raíz del bug del 2do mensaje con Ollama lento)
    phone_lock = _get_phone_lock(request.phone)
    if not phone_lock.acquire(blocking=False):
        log_with_context(logger, "info", "Request concurrente bloqueado", phone=request.phone[-4:])
        raise RateLimitException(msgs_cfg.get("rate_limit", "Un momento, estoy procesando tu mensaje anterior 🙏"))

    try:
        # Rate limiting: evitar procesamiento doble si el mismo número envía mensajes consecutivos
        if _message_cooldowns.check_and_set(request.phone, message_cooldown):
            raise RateLimitException(msgs_cfg.get("rate_limit", "Un momento, estoy procesando tu mensaje anterior 🙏"))

        # 1. Buscar o crear conversación (thread-safe, filtrada por vendor)
        conversation = get_or_create_conversation(
            db, request.phone, current_vendor.id, request.customer_name
        )
        log_with_context(logger, "info", "Conversación activa", conversation_id=conversation.id)

        # 2. Guardar mensaje del cliente
        customer_msg = Message(
            conversation_id=conversation.id,
            content=request.message,
            from_customer=True
        )
        db.add(customer_msg)
        db.commit()

        # 3. Verificar si bot está activo
        if not conversation.bot_enabled:
            log_with_context(logger, "info", "Bot desactivado para conversación", conversation_id=conversation.id)
            # bot_disabled_response puede ser null en el perfil para mantener el comportamiento original
            # (sin respuesta automática — el agente humano responde manualmente)
            disabled_msg = msgs_cfg.get("bot_disabled_response") or None
            return {
                "reply": disabled_msg,
                "bot_enabled": False,
                "message": "Bot desactivado. Respuesta manual requerida."
            }

        # 4. Detectar comandos
        command = detect_command(request.message)
        ai_response = None
        media_url = None

        if command == "catalog":
            products = db.query(Product).filter(
                Product.stock > 0, Product.vendor_id == current_vendor.id
            ).all()
            ai_response = generate_catalog(products, profile)
            log_with_context(logger, "info", "Comando: catálogo", product_count=len(products))

        elif command == "cart":
            cart_items = db.query(CartItem).filter(
                CartItem.conversation_id == conversation.id
            ).all()
            product_ids = [item.product_id for item in cart_items]
            products_list = db.query(Product).filter(
                Product.id.in_(product_ids), Product.vendor_id == current_vendor.id
            ).all() if product_ids else []
            products_dict = {p.id: p for p in products_list}
            ai_response = generate_cart_display(cart_items, products_dict)
            log_with_context(logger, "info", "Comando: ver carrito", item_count=len(cart_items))

        elif command == "order":
            cart_items = db.query(CartItem).filter(
                CartItem.conversation_id == conversation.id
            ).all()

            if not cart_items:
                ai_response = "🛒 Tu carrito está vacío.\n\nEscribe *#catalogo* para ver nuestros productos."
            else:
                product_ids = [item.product_id for item in cart_items]
                products_list = db.query(Product).filter(
                    Product.id.in_(product_ids), Product.vendor_id == current_vendor.id
                ).all()
                products_dict = {p.id: p for p in products_list}

                # Validar stock y calcular total
                out_of_stock = []
                total = 0
                for item in cart_items:
                    product = products_dict.get(item.product_id)
                    if product:
                        if product.stock < item.quantity:
                            out_of_stock.append(f"{product.name} (disponible: {product.stock})")
                        else:
                            total += product.price * item.quantity

                if out_of_stock:
                    ai_response = (
                        f"⚠️ *Stock insuficiente para:*\n" +
                        "\n".join(f"• {p}" for p in out_of_stock) +
                        "\n\nEscribe *#limpiar* para vaciar el carrito y volver a agregar."
                    )
                else:
                    # Crear pedido — transacción atómica con lock de stock para evitar race conditions
                    with handle_db_errors(db):
                        order = Order(
                            conversation_id=conversation.id,
                            phone=request.phone,
                            vendor_id=current_vendor.id,
                            total=0,  # se actualizará a confirmed_total antes del commit
                            status="pending"
                        )
                        db.add(order)
                        db.flush()  # obtener order.id sin hacer commit todavía

                        confirmed_total = 0
                        out_of_stock_atomic = []

                        # Crear items del pedido y descontar stock
                        for item in cart_items:
                            product = db.query(Product).filter(
                                Product.id == item.product_id,
                                Product.vendor_id == current_vendor.id,
                            ).with_for_update().first()

                            if not product:
                                db.rollback()
                                raise ProductNotFoundException(f"Producto {item.product_id} no encontrado")

                            if product.stock < item.quantity:
                                out_of_stock_atomic.append(f"{product.name} (disponible: {product.stock})")
                                continue

                            db.add(OrderItem(
                                order_id=order.id,
                                product_id=product.id,
                                product_name=product.name,
                                product_price=product.price,
                                quantity=item.quantity
                            ))
                            product.stock -= item.quantity
                            confirmed_total += product.price * item.quantity

                        if out_of_stock_atomic:
                            db.rollback()
                            ai_response = (
                                f"⚠️ *Stock insuficiente para:*\n" +
                                "\n".join(f"• {p}" for p in out_of_stock_atomic) +
                                "\n\nEscribe *#limpiar* para vaciar el carrito y volver a agregar."
                            )
                        else:
                            order.total = confirmed_total

                            # Vaciar carrito dentro de la misma transacción
                            db.query(CartItem).filter(
                                CartItem.conversation_id == conversation.id
                            ).delete()

                            db.commit()  # commit atómico de TODO

                            total = confirmed_total
                            _payment_str = ", ".join(get_field(profile, "payments", "methods", default=["Yape", "Plin"]))
                            ai_response = (
                                f"✅ *¡PEDIDO CONFIRMADO!*\n"
                                f"─────────────────────────\n"
                                f"🔖 Pedido #{order.id}\n"
                                f"💰 Total: S/ {total / 100:.2f}\n"
                                f"📋 Estado: Pendiente de confirmación\n\n"
                                f"📞 Te contactaremos para coordinar pago y envío.\n"
                                f"💳 Pagos: {_payment_str}\n\n"
                                f"¡Gracias por tu compra! 🙌"
                            )
                            log_with_context(logger, "info", "Pedido creado", order_id=order.id, total=total)

        elif command == "clear_cart":
            deleted = db.query(CartItem).filter(
                CartItem.conversation_id == conversation.id
            ).delete()
            db.commit()
            ai_response = f"🗑️ Carrito vaciado ({deleted} item(s) eliminados).\n\nEscribe *#catalogo* para empezar de nuevo."
            log_with_context(logger, "info", "Comando: limpiar carrito", deleted=deleted)

        elif command == "help":
            ai_response = msgs_cfg.get("bot_help_text") or BOT_HELP_TEXT
            log_with_context(logger, "info", "Comando: ayuda")

        elif command == "status":
            last_order = db.query(Order).filter(
                Order.phone == request.phone,
                Order.vendor_id == current_vendor.id,
            ).order_by(Order.created_at.desc()).first()

            if not last_order:
                ai_response = "📦 No tienes pedidos aún.\n\nEscribe *#catalogo* para ver nuestros productos."
            else:
                status_labels = {
                    "pending":   "⏳ Pendiente de confirmación",
                    "confirmed": "✅ Confirmado",
                    "shipped":   "🚚 En camino",
                    "delivered": "📬 Entregado",
                    "cancelled": "❌ Cancelado",
                }
                label = status_labels.get(last_order.status, last_order.status)
                ai_response = (
                    f"📦 *ESTADO DE TU PEDIDO*\n"
                    f"─────────────────────────\n"
                    f"🔖 Pedido #{last_order.id}\n"
                    f"💰 Total: S/ {last_order.total / 100:.2f}\n"
                    f"📋 Estado: {label}\n"
                    f"📅 Fecha: {last_order.created_at.strftime('%d/%m/%Y %H:%M')}\n\n"
                    f"¿Necesitas algo más? 😊"
                )
            log_with_context(logger, "info", "Comando: estado de pedido")

        elif command == "add_to_cart":
            match = re.search(r'\d+', request.message)
            if match:
                product_num = int(match.group())
                products = db.query(Product).filter(
                    Product.stock > 0, Product.vendor_id == current_vendor.id
                ).all()

                if 1 <= product_num <= len(products):
                    product = products[product_num - 1]

                    # Re-consultar con lock para evitar race condition de stock
                    locked_product = db.query(Product).filter(
                        Product.id == product.id,
                        Product.vendor_id == current_vendor.id,
                    ).with_for_update().first()

                    if not locked_product or locked_product.stock < 1:
                        product_name = locked_product.name if locked_product else "ese producto"
                        ai_response = f"⚠️ Lo siento, *{product_name}* está agotado.\n\nEscribe *#catalogo* para ver otros productos disponibles."
                    else:
                        with handle_db_errors(db):
                            existing = db.query(CartItem).filter(
                                CartItem.conversation_id == conversation.id,
                                CartItem.product_id == locked_product.id
                            ).with_for_update().first()

                            if existing:
                                existing.quantity += 1
                            else:
                                db.add(CartItem(
                                    conversation_id=conversation.id,
                                    product_id=locked_product.id,
                                    quantity=1
                                ))
                            db.commit()

                        if locked_product.image_url:
                            media_url = locked_product.image_url

                        ai_response = (
                            f"✅ *{locked_product.name}* agregado al carrito!\n"
                            f"💰 Precio: S/ {locked_product.price / 100:.2f}\n\n"
                            f"🛒 Ver carrito: *#carrito*\n"
                            f"📦 Confirmar pedido: *#pedido*\n"
                            f"📋 Seguir comprando: *#catalogo*"
                        )
                        log_with_context(logger, "info", "Producto agregado al carrito", product_num=product_num, product_name=locked_product.name)
                else:
                    ai_response = f"⚠️ Número inválido. Escribe *#catalogo* para ver los productos disponibles (1 al {len(products)})."
            else:
                ai_response = "⚠️ Por favor indica el número de producto. Ejemplo: *agregar 1*"

        # 5. Si no fue un comando → detección rápida de intención ANTES de llamar a IA
        if ai_response is None:
            quick_intent = detect_intent(request.message, profile)
            log_with_context(logger, "info", "Intent rápido detectado", intent_type=quick_intent["type"], confidence=quick_intent["confidence"])

            if quick_intent["type"] == "greeting":
                # Nivel 1 — respuesta inmediata (0ms): saludo
                tz_str = get_field(profile, "schedule", "timezone", default="America/Lima")
                saludo = get_greeting_by_time(tz_str)
                is_returning = bool(
                    db.query(Message).filter(
                        Message.conversation_id == conversation.id,
                        Message.from_customer == False  # noqa: E712 — SQLAlchemy uses == for boolean filters
                    ).first()
                )
                templates = msgs_cfg.get("greeting_returning" if is_returning else "greeting_new", [])
                if not templates:
                    store_name = get_field(profile, "store", "name", default="la tienda")
                    templates = [
                        f"¡{{saludo}}! 👋 Soy {{bot_name}} de *{{store_name}}*. Escribe *#catalogo* para ver todo. ¿En qué te puedo ayudar?",
                    ] if not is_returning else [
                        f"¡{{saludo}}! 👋 Qué bueno verte de nuevo. Soy {{bot_name}}. ¿En qué te ayudo hoy? 😄",
                    ]
                store_name = get_field(profile, "store", "name", default="la tienda")
                ai_response = random.choice(templates).format(
                    saludo=saludo,
                    bot_name=bot_name,
                    store_name=store_name,
                )

            elif quick_intent["type"] == "faq" and quick_intent.get("faq_topic"):
                # Nivel 1 — respuesta inmediata: FAQ
                faq = build_faq_responses(profile)
                ai_response = faq.get(quick_intent["faq_topic"])

            elif quick_intent["type"] == "goodbye":
                # Nivel 1 — respuesta inmediata: despedida
                templates = msgs_cfg.get("goodbye", [
                    "¡Un placer atenderte! 🙌 Si necesitas algo más, aquí estoy. ¡Que te vaya bien!",
                ])
                ai_response = random.choice(templates)

            elif quick_intent["type"] == "complaint":
                # Nivel 1 — respuesta inmediata: queja
                warranty_days = get_field(profile, "warranty", "days", default=30)
                template = msgs_cfg.get(
                    "complaint_response",
                    "Oye, lamento mucho escuchar eso. 😔 Tu satisfacción es lo más importante. Cuéntame qué pasó y lo resolvemos de inmediato. Tenemos garantía de {warranty_days} días.",
                )
                ai_response = template.format(warranty_days=warranty_days)

            elif quick_intent["type"] == "price_objection":
                # Nivel 1 — respuesta inmediata: objeción de precio
                discount_two = get_field(profile, "discounts", "two_products_pct", default=10)
                template = msgs_cfg.get(
                    "price_objection_response",
                    "Entiendo perfectamente, el presupuesto importa. 💰 Tenemos opciones desde poco, y comprar 2 productos te da {discount_two}% de descuento. ¿Cuánto quieres invertir? 😊",
                )
                ai_response = template.format(discount_two=discount_two)

            elif quick_intent["type"] in ("recommendation", "purchase"):
                # Nivel 2 — respuesta rápida (<2s): mostrar catálogo inmediatamente sin IA
                max_products_ctx = ai_cfg.get("max_products_in_context", 8)
                products = db.query(Product).filter(
                    Product.stock > 0, Product.vendor_id == current_vendor.id
                ).limit(max_products_ctx).all()
                if products:
                    catalog_text = generate_catalog(products, profile)
                    context_msg = msgs_cfg.get(
                        "recommendation_prompt",
                        "¡Aquí tienes nuestro catálogo! 😊 Dime el número del producto que te interesa y te cuento más:",
                    )
                    ai_response = context_msg + "\n\n" + catalog_text
                else:
                    ai_response = msgs_cfg.get(
                        "catalog_empty",
                        "¡Hola! Por el momento estamos actualizando nuestro catálogo. Escribe *#ayuda* para ver qué puedo hacer por ti. 😊",
                    )
                log_with_context(logger, "info", "Catálogo mostrado por intent rápido", intent_type=quick_intent["type"])

        # 5b. Si el intent rápido no resolvió → usar IA (solo para casos complejos/generales)
        if ai_response is None:
            history_limit = ai_cfg.get("history_messages_limit", settings.HISTORY_MESSAGES_LIMIT)
            recent_messages = db.query(Message).filter(
                Message.conversation_id == conversation.id
            ).order_by(Message.created_at.desc()).limit(history_limit).all()

            conversation_history = [
                f"{'Cliente' if msg.from_customer else bot_name}: {msg.content}"
                for msg in reversed(recent_messages)
            ]

            cart_items = db.query(CartItem).filter(
                CartItem.conversation_id == conversation.id
            ).all()
            recently_viewed = [str(item.product_id) for item in cart_items]

            products = db.query(Product).filter(
                Product.stock > 0, Product.vendor_id == current_vendor.id
            ).all()
            log_with_context(logger, "info", "Procesando con IA", product_count=len(products))

            ai_response = generate_ai_response(
                message=request.message,
                products=products,
                profile=profile,
                conversation_history=conversation_history,
                recently_viewed=recently_viewed
            )

        # Garantía final — jamás guardar ni responder con None
        if ai_response is None:
            ai_response = msgs_cfg.get(
                "fallback_response",
                "¡Hola! 👋 Escribe *#catalogo* para ver nuestros productos o *#ayuda* para los comandos disponibles. 😊",
            )
            log_with_context(logger, "warning", "ai_response era None — usando fallback final")

        # 6. Guardar respuesta del bot
        db.add(Message(
            conversation_id=conversation.id,
            content=ai_response,
            from_customer=False
        ))

        # 7. Actualizar timestamp
        conversation.last_message_at = datetime.now(timezone.utc)
        db.commit()

        log_with_context(logger, "info", "Respuesta enviada", preview=ai_response[:60])

        return {
            "reply": ai_response,
            "bot_enabled": True,
            "conversation_id": conversation.id,
            "media_url": media_url,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

    finally:
        phone_lock.release()

# ===== ENDPOINTS DE CONVERSACIONES =====

@app.get("/api/conversations")
def get_conversations(
    db: Session = Depends(get_db),
    current_vendor: Vendor = Depends(get_current_vendor),
):
    """Obtener todas las conversaciones del vendor ordenadas por más reciente"""
    conversations = db.query(Conversation).filter(
        Conversation.vendor_id == current_vendor.id
    ).order_by(Conversation.last_message_at.desc()).all()

    if not conversations:
        return []

    conv_ids = [c.id for c in conversations]
    subq = (
        db.query(Message.conversation_id, func.max(Message.id).label("max_id"))
        .filter(Message.conversation_id.in_(conv_ids))
        .group_by(Message.conversation_id)
        .subquery()
    )
    last_messages = (
        db.query(Message)
        .join(subq, Message.id == subq.c.max_id)
        .all()
    )
    last_msg_map = {m.conversation_id: m.content for m in last_messages}

    return [
        {
            "id": c.id,
            "phone": c.phone,
            "customer_name": c.customer_name,
            "bot_enabled": c.bot_enabled,
            "last_message_at": c.last_message_at,
            "last_message": last_msg_map.get(c.id),
        }
        for c in conversations
    ]

@app.get("/api/conversations/{conversation_id}/messages")
def get_messages(
    conversation_id: int,
    db: Session = Depends(get_db),
    current_vendor: Vendor = Depends(get_current_vendor),
):
    """Obtener todos los mensajes de una conversación específica"""
    conversation = db.query(Conversation).filter(
        Conversation.id == conversation_id,
        Conversation.vendor_id == current_vendor.id,
    ).first()

    if not conversation:
        raise ConversationNotFoundException(f"Conversación {conversation_id} no encontrada")

    messages = db.query(Message).filter(
        Message.conversation_id == conversation_id
    ).order_by(Message.created_at.asc()).all()

    return messages

@app.patch("/api/conversations/{conversation_id}/toggle-bot")
def toggle_bot(
    conversation_id: int,
    enabled: bool,
    db: Session = Depends(get_db),
    current_vendor: Vendor = Depends(get_current_vendor),
):
    """Activar/desactivar bot para una conversación (para intervención humana)"""
    conversation = db.query(Conversation).filter(
        Conversation.id == conversation_id,
        Conversation.vendor_id == current_vendor.id,
    ).first()

    if not conversation:
        raise ConversationNotFoundException(f"Conversación {conversation_id} no encontrada")

    conversation.bot_enabled = enabled
    db.commit()

    action = "activado" if enabled else "desactivado"
    log_with_context(logger, "info", f"Bot {action}", conversation_id=conversation_id)

    return {
        "bot_enabled": conversation.bot_enabled,
        "conversation_id": conversation_id,
    }


class SendMessageRequest(BaseModel):
    message: str

    @field_validator("message")
    @classmethod
    def message_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("El mensaje no puede estar vacío")
        if len(v) > 4096:
            raise ValueError("El mensaje no puede superar 4096 caracteres")
        return v


@app.post("/api/conversations/{conversation_id}/send-message")
def send_manual_message(
    conversation_id: int,
    body: SendMessageRequest,
    db: Session = Depends(get_db),
    current_vendor: Vendor = Depends(get_current_vendor),
):
    """Enviar un mensaje manual al cliente por WhatsApp desde el panel admin"""
    conversation = db.query(Conversation).filter(
        Conversation.id == conversation_id,
        Conversation.vendor_id == current_vendor.id,
    ).first()
    if not conversation:
        raise ConversationNotFoundException(f"Conversación {conversation_id} no encontrada")

    # Usar URL del cliente WA del vendor, con fallback al global
    wa_url = current_vendor.wa_client_url or settings.WA_CLIENT_URL
    payload = json.dumps({
        "phone": conversation.phone,
        "message": body.message,
        "api_key": current_vendor.api_key,
    }).encode()
    try:
        req = urllib.request.Request(
            f"{wa_url}/send",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10):
            pass
    except urllib.error.URLError as e:
        raise HTTPException(status_code=502, detail=f"No se pudo conectar con WhatsApp: {e.reason}")
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Error WhatsApp: {str(e)}")

    msg = Message(
        conversation_id=conversation.id,
        content=body.message,
        from_customer=False,
    )
    db.add(msg)
    conversation.last_message_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(msg)

    log_with_context(logger, "info", "Mensaje manual enviado", conversation_id=conversation_id)
    return {"ok": True, "message_id": msg.id, "created_at": msg.created_at}


@app.delete("/api/conversations/{conversation_id}")
def delete_conversation(
    conversation_id: int,
    db: Session = Depends(get_db),
    current_vendor: Vendor = Depends(get_current_vendor),
):
    """Eliminar una conversación y todos sus mensajes y carrito asociado"""
    conversation = db.query(Conversation).filter(
        Conversation.id == conversation_id,
        Conversation.vendor_id == current_vendor.id,
    ).first()
    if not conversation:
        raise ConversationNotFoundException(f"Conversación {conversation_id} no encontrada")

    db.query(Message).filter(Message.conversation_id == conversation_id).delete()
    db.query(CartItem).filter(CartItem.conversation_id == conversation_id).delete()
    db.delete(conversation)
    db.commit()

    log_with_context(logger, "info", "Conversación eliminada", conversation_id=conversation_id)
    return {"ok": True}


# ===== ENDPOINTS DE CARRITO =====

@app.post("/api/cart/{phone}/add")
def api_add_to_cart(
    phone: str,
    item: CartItemRequest,
    db: Session = Depends(get_db),
    current_vendor: Vendor = Depends(get_current_vendor),
):
    """Agregar producto al carrito vía API"""
    conversation = db.query(Conversation).filter(
        Conversation.phone == phone,
        Conversation.vendor_id == current_vendor.id,
    ).first()
    if not conversation:
        raise ConversationNotFoundException(f"Conversación para teléfono {phone} no encontrada")

    product = db.query(Product).filter(
        Product.id == item.product_id,
        Product.vendor_id == current_vendor.id,
    ).first()
    if not product:
        raise ProductNotFoundException(f"Producto {item.product_id} no encontrado")
    if product.stock < item.quantity:
        raise InsufficientStockException(f"Stock insuficiente. Disponible: {product.stock}")

    existing = db.query(CartItem).filter(
        CartItem.conversation_id == conversation.id,
        CartItem.product_id == item.product_id
    ).first()

    if existing:
        with handle_db_errors(db):
            existing.quantity += item.quantity
            db.commit()
    else:
        with handle_db_errors(db):
            db.add(CartItem(
                conversation_id=conversation.id,
                product_id=item.product_id,
                quantity=item.quantity
            ))
            db.commit()
    return {"message": f"{product.name} agregado al carrito", "product": product.name, "quantity": item.quantity}


@app.get("/api/cart/{phone}")
def api_get_cart(
    phone: str,
    db: Session = Depends(get_db),
    current_vendor: Vendor = Depends(get_current_vendor),
):
    """Ver carrito de un cliente vía API"""
    conversation = db.query(Conversation).filter(
        Conversation.phone == phone,
        Conversation.vendor_id == current_vendor.id,
    ).first()
    if not conversation:
        return {"items": [], "total": 0, "total_soles": 0.0}

    cart_items = db.query(CartItem).filter(
        CartItem.conversation_id == conversation.id
    ).all()

    result = []
    total = 0
    for item in cart_items:
        product = db.query(Product).filter(
            Product.id == item.product_id,
            Product.vendor_id == current_vendor.id,
        ).first()
        if product:
            subtotal = product.price * item.quantity
            total += subtotal
            result.append({
                "product_id": product.id,
                "product_name": product.name,
                "price": product.price,
                "price_soles": product.price / 100,
                "quantity": item.quantity,
                "subtotal": subtotal,
                "subtotal_soles": subtotal / 100,
                "image_url": product.image_url,
                "in_stock": product.stock >= item.quantity,
            })
    return {"items": result, "total": total, "total_soles": total / 100}


@app.delete("/api/cart/{phone}")
def api_clear_cart(
    phone: str,
    db: Session = Depends(get_db),
    current_vendor: Vendor = Depends(get_current_vendor),
):
    """Vaciar carrito de un cliente"""
    conversation = db.query(Conversation).filter(
        Conversation.phone == phone,
        Conversation.vendor_id == current_vendor.id,
    ).first()
    if not conversation:
        raise ConversationNotFoundException(f"Conversación para teléfono {phone} no encontrada")
    deleted = db.query(CartItem).filter(
        CartItem.conversation_id == conversation.id
    ).delete()
    db.commit()
    return {"message": f"Carrito vaciado. {deleted} item(s) eliminados."}


# ===== ENDPOINTS DE PEDIDOS =====

@app.get("/api/orders")
def get_orders(
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    current_vendor: Vendor = Depends(get_current_vendor),
):
    """Listar todos los pedidos del vendor, opcionalmente filtrados por estado"""
    query = db.query(Order).filter(Order.vendor_id == current_vendor.id)
    if status:
        query = query.filter(Order.status == status)
    orders = query.order_by(Order.created_at.desc()).all()

    result = []
    for order in orders:
        items = db.query(OrderItem).filter(OrderItem.order_id == order.id).all()
        result.append({
            "id": order.id,
            "phone": order.phone,
            "total": order.total,
            "total_soles": order.total / 100,
            "status": order.status,
            "notes": order.notes,
            "created_at": order.created_at.isoformat(),
            "updated_at": order.updated_at.isoformat() if order.updated_at else None,
            "items": [
                {
                    "product_name": i.product_name,
                    "product_price_soles": i.product_price / 100,
                    "quantity": i.quantity,
                    "subtotal_soles": (i.product_price * i.quantity) / 100,
                }
                for i in items
            ],
        })
    return result


@app.get("/api/orders/{order_id}")
def get_order(
    order_id: int,
    db: Session = Depends(get_db),
    current_vendor: Vendor = Depends(get_current_vendor),
):
    """Obtener detalles de un pedido específico"""
    order = db.query(Order).filter(
        Order.id == order_id,
        Order.vendor_id == current_vendor.id,
    ).first()
    if not order:
        raise OrderNotFoundException(f"Pedido {order_id} no encontrado")

    items = db.query(OrderItem).filter(OrderItem.order_id == order.id).all()
    return {
        "id": order.id,
        "phone": order.phone,
        "total_soles": order.total / 100,
        "status": order.status,
        "notes": order.notes,
        "created_at": order.created_at.isoformat(),
        "updated_at": order.updated_at.isoformat() if order.updated_at else None,
        "items": [
            {
                "product_name": i.product_name,
                "price_soles": i.product_price / 100,
                "quantity": i.quantity,
                "subtotal_soles": (i.product_price * i.quantity) / 100,
            }
            for i in items
        ],
    }


@app.patch("/api/orders/{order_id}/status")
def update_order_status(
    order_id: int,
    update: OrderStatusUpdate,
    db: Session = Depends(get_db),
    current_vendor: Vendor = Depends(get_current_vendor),
):
    """Actualizar estado de un pedido (y restaurar stock si se cancela)"""
    order = db.query(Order).filter(
        Order.id == order_id,
        Order.vendor_id == current_vendor.id,
    ).first()
    if not order:
        raise OrderNotFoundException(f"Pedido {order_id} no encontrado")

    with handle_db_errors(db):
        # Restaurar stock si se cancela
        if update.status == "cancelled" and order.status != "cancelled":
            for item in db.query(OrderItem).filter(OrderItem.order_id == order_id).all():
                product = db.query(Product).filter(Product.id == item.product_id).first()
                if product:
                    product.stock += item.quantity

        order.status = update.status
        order.updated_at = datetime.now(timezone.utc)
        db.commit()

    status_labels = {
        "pending": "Pendiente", "confirmed": "Confirmado",
        "shipped": "En camino", "delivered": "Entregado", "cancelled": "Cancelado",
    }
    return {
        "order_id": order_id,
        "status": update.status,
        "status_label": status_labels.get(update.status),
        "message": f"Pedido #{order_id} actualizado a '{status_labels.get(update.status)}'",
    }


# ===== ANALYTICS =====

@app.get("/api/analytics")
def get_analytics(
    db: Session = Depends(get_db),
    current_vendor: Vendor = Depends(get_current_vendor),
):
    """Dashboard de métricas y estadísticas del vendor"""
    vid = current_vendor.id

    total_revenue = db.query(func.sum(Order.total)).filter(
        Order.vendor_id == vid,
        Order.status.in_(["confirmed", "shipped", "delivered"]),
    ).scalar() or 0

    orders_by_status = db.query(
        Order.status, func.count(Order.id)
    ).filter(Order.vendor_id == vid).group_by(Order.status).all()

    # top_products filtrado por pedidos del vendor
    top_products = (
        db.query(
            OrderItem.product_name,
            func.sum(OrderItem.quantity).label("total_sold"),
            func.sum(OrderItem.product_price * OrderItem.quantity).label("revenue"),
        )
        .join(Order, Order.id == OrderItem.order_id)
        .filter(Order.vendor_id == vid)
        .group_by(OrderItem.product_name)
        .order_by(func.sum(OrderItem.quantity).desc())
        .limit(5)
        .all()
    )

    conv_total = db.query(func.count(Conversation.id)).filter(
        Conversation.vendor_id == vid
    ).scalar() or 0

    msg_total = (
        db.query(func.count(Message.id))
        .join(Conversation, Conversation.id == Message.conversation_id)
        .filter(Conversation.vendor_id == vid)
        .scalar() or 0
    )

    return {
        "conversations": {"total": conv_total},
        "messages": {"total": msg_total},
        "orders": {
            "total": db.query(func.count(Order.id)).filter(Order.vendor_id == vid).scalar() or 0,
            "by_status": {s: count for s, count in orders_by_status},
            "pending":   db.query(func.count(Order.id)).filter(Order.vendor_id == vid, Order.status == "pending").scalar() or 0,
            "confirmed": db.query(func.count(Order.id)).filter(Order.vendor_id == vid, Order.status == "confirmed").scalar() or 0,
            "shipped":   db.query(func.count(Order.id)).filter(Order.vendor_id == vid, Order.status == "shipped").scalar() or 0,
            "delivered": db.query(func.count(Order.id)).filter(Order.vendor_id == vid, Order.status == "delivered").scalar() or 0,
            "cancelled": db.query(func.count(Order.id)).filter(Order.vendor_id == vid, Order.status == "cancelled").scalar() or 0,
        },
        "revenue": {"total_soles": total_revenue / 100},
        "products": {
            "total": db.query(func.count(Product.id)).filter(Product.vendor_id == vid).scalar() or 0,
            "in_stock": db.query(func.count(Product.id)).filter(Product.vendor_id == vid, Product.stock > 0).scalar() or 0,
            "top_sellers": [
                {
                    "name": name,
                    "units_sold": int(sold or 0),
                    "revenue_soles": float(revenue or 0) / 100,
                }
                for name, sold, revenue in top_products
            ],
        },
    }


@app.get("/")
def root():
    return {
        "status": "ok",
        "service": "InstantVende API",
        "message": "Backend funcionando con Ollama"
    }

@app.get("/api/health/ollama")
def check_ollama(_: Optional[str] = Depends(verify_api_key_optional)):
    try:
        response = ollama.chat(
            model=settings.OLLAMA_MODEL,
            messages=[{'role': 'user', 'content': 'Hola'}]
        )
        return {"status": "ok", "response": response['message']['content']}
    except Exception as e:
        return {"status": "error", "message": str(e)}


# ===== BOT PROFILE ENDPOINTS =====

@app.get("/api/bot-profile")
def read_bot_profile(
    db: Session = Depends(get_db),
    current_vendor: Vendor = Depends(get_current_vendor),
):
    """Leer el perfil activo del bot del vendor (desde DB o desde el JSON por defecto)."""
    row = db.query(BotProfile).filter(
        BotProfile.vendor_id == current_vendor.id
    ).first()
    if row:
        return json.loads(row.profile_json)
    return load_default_profile()


@app.put("/api/bot-profile")
def update_bot_profile(
    profile_data: dict = Body(...),
    db: Session = Depends(get_db),
    current_vendor: Vendor = Depends(get_current_vendor),
):
    """Actualizar el perfil completo del bot del vendor. Los cambios se reflejan en el siguiente mensaje."""
    profile_json_str = json.dumps(profile_data, ensure_ascii=False)
    row = db.query(BotProfile).filter(BotProfile.vendor_id == current_vendor.id).first()
    if row:
        row.profile_json = profile_json_str
        row.updated_at = datetime.now(timezone.utc)
        row.updated_by_vendor_id = current_vendor.id
    else:
        row = BotProfile(
            vendor_id=current_vendor.id,
            profile_json=profile_json_str,
            updated_by_vendor_id=current_vendor.id,
        )
        db.add(row)
    with handle_db_errors(db):
        db.commit()
    invalidate_cache(vendor_id=current_vendor.id)
    log_with_context(logger, "info", "Perfil del bot actualizado", vendor_id=current_vendor.id)
    return {"message": "Perfil actualizado correctamente"}


@app.post("/api/bot-profile/reset")
def reset_bot_profile(
    db: Session = Depends(get_db),
    current_vendor: Vendor = Depends(get_current_vendor),
):
    """Restaurar el perfil por defecto eliminando el perfil guardado en DB."""
    with handle_db_errors(db):
        db.query(BotProfile).filter(BotProfile.vendor_id == current_vendor.id).delete()
        db.commit()
    invalidate_cache(vendor_id=current_vendor.id)
    log_with_context(logger, "info", "Perfil del bot restaurado al valor por defecto", vendor_id=current_vendor.id)
    return {"message": "Perfil restaurado al valor por defecto"}

# ===== VENDORS =====


def _hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def _verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def _generate_unique_api_key(db: Session, max_attempts: int = 10) -> str:
    """Genera una API key única garantizando que no exista ya en la DB."""
    for _ in range(max_attempts):
        key = secrets.token_urlsafe(32)
        if not db.query(Vendor).filter(Vendor.api_key == key).first():
            return key
    raise HTTPException(status_code=500, detail="No se pudo generar una API key única")


class VendorRegister(BaseModel):
    name: str
    email: str
    business_name: Optional[str] = None
    password: str

    @field_validator("email")
    @classmethod
    def email_lower(cls, v: str) -> str:
        return v.strip().lower()

    @field_validator("password")
    @classmethod
    def password_min(cls, v: str) -> str:
        if len(v) < 6:
            raise ValueError("La contraseña debe tener al menos 6 caracteres")
        return v


class VendorLogin(BaseModel):
    email: str
    password: str

    @field_validator("email")
    @classmethod
    def email_lower(cls, v: str) -> str:
        return v.strip().lower()


def vendor_to_dict(v: Vendor) -> dict:
    return {
        "id": v.id,
        "name": v.name,
        "email": v.email,
        "business_name": v.business_name,
        "is_active": v.is_active,
        "created_at": v.created_at.isoformat() if v.created_at else None,
    }


@app.post("/api/vendors/register", status_code=201)
def vendor_register(data: VendorRegister, db: Session = Depends(get_db)):
    """Registrar un nuevo vendedor. Genera una API key única por vendor."""
    existing = db.query(Vendor).filter(Vendor.email == data.email).first()
    if existing:
        raise HTTPException(status_code=409, detail="Ya existe una cuenta con ese email")

    # Generar API key única — no re-usar la clave global del sistema
    api_key = _generate_unique_api_key(db)

    vendor = Vendor(
        name=data.name.strip(),
        email=data.email,
        business_name=data.business_name.strip() if data.business_name else None,
        hashed_password=_hash_password(data.password),
        api_key=api_key,
        is_active=True,
    )
    db.add(vendor)
    db.commit()
    db.refresh(vendor)
    log_with_context(logger, "info", "Vendedor registrado", email=vendor.email)
    return {"vendor": vendor_to_dict(vendor), "api_key": vendor.api_key}


@app.post("/api/vendors/login")
def vendor_login(data: VendorLogin, db: Session = Depends(get_db)):
    """Iniciar sesión con email y contraseña. Retorna la API key del vendor."""
    vendor = db.query(Vendor).filter(Vendor.email == data.email).first()
    if not vendor or not _verify_password(data.password, vendor.hashed_password):
        raise HTTPException(status_code=401, detail="Email o contraseña incorrectos")
    if not vendor.is_active:
        raise HTTPException(status_code=403, detail="Cuenta desactivada")

    # Generar nueva api_key si el vendor aún no tiene una
    if not vendor.api_key:
        vendor.api_key = _generate_unique_api_key(db)
        db.commit()
        db.refresh(vendor)

    log_with_context(logger, "info", "Vendedor autenticado", email=vendor.email)
    return {"vendor": vendor_to_dict(vendor), "api_key": vendor.api_key}


@app.get("/api/vendors/me")
def vendor_me(current_vendor: Vendor = Depends(get_current_vendor)):
    """Devuelve la información del vendor autenticado."""
    return {"vendor": vendor_to_dict(current_vendor)}


# ===== WHATSAPP CONNECTION STATUS =====

class WaSessionUpdate(BaseModel):
    """Payload enviado por el cliente WA para actualizar su estado en la DB."""
    status: str          # disconnected | connecting | connected
    qr_code: Optional[str] = None
    phone_number: Optional[str] = None


@app.post("/api/wa/session/update")
def wa_session_update(
    body: WaSessionUpdate,
    db: Session = Depends(get_db),
    current_vendor: Vendor = Depends(get_current_vendor),
):
    """El cliente WA llama a este endpoint para actualizar su estado de sesión."""
    session = db.query(WhatsappSession).filter(
        WhatsappSession.vendor_id == current_vendor.id
    ).first()

    now = datetime.now(timezone.utc)
    if session:
        session.status = body.status
        session.qr_code = body.qr_code
        session.phone_number = body.phone_number
        session.updated_at = now
        if body.status == "connected":
            session.connected_at = now
    else:
        session = WhatsappSession(
            vendor_id=current_vendor.id,
            status=body.status,
            qr_code=body.qr_code,
            phone_number=body.phone_number,
            connected_at=now if body.status == "connected" else None,
        )
        db.add(session)

    db.commit()
    return {"ok": True}


@app.get("/api/wa/status")
def wa_status(
    db: Session = Depends(get_db),
    current_vendor: Vendor = Depends(get_current_vendor),
):
    """Estado de conexión WhatsApp del vendor autenticado.

    Primero consulta la DB (actualizada por el cliente WA vía /api/wa/session/update),
    con fallback al proxy HTTP al cliente WA del vendor.
    """
    # Intentar leer desde la tabla de sesiones (fuente de verdad si el cliente WA la actualiza)
    session = db.query(WhatsappSession).filter(
        WhatsappSession.vendor_id == current_vendor.id
    ).first()
    if session:
        return {
            "connected": session.status == "connected",
            "status": session.status,
            "qrDataUrl": session.qr_code,
            "phone_number": session.phone_number,
            "connected_at": session.connected_at.isoformat() if session.connected_at else None,
        }

    # Fallback: proxear al servidor HTTP del cliente WA del vendor
    wa_url = current_vendor.wa_client_url or settings.WA_CLIENT_URL
    try:
        req = urllib.request.Request(f"{wa_url}/status", method="GET")
        with urllib.request.urlopen(req, timeout=5) as resp:
            return json.loads(resp.read())
    except Exception:
        return {"connected": False, "qrDataUrl": None, "info": None}


@app.post("/api/wa/disconnect")
def wa_disconnect(
    db: Session = Depends(get_db),
    current_vendor: Vendor = Depends(get_current_vendor),
):
    """Desconectar WhatsApp y borrar sesión del vendor autenticado."""
    # Actualizar estado en DB
    session = db.query(WhatsappSession).filter(
        WhatsappSession.vendor_id == current_vendor.id
    ).first()
    if session:
        session.status = "disconnected"
        session.qr_code = None
        session.phone_number = None
        session.connected_at = None
        db.commit()

    # Proxear al servidor HTTP del cliente WA del vendor
    wa_url = current_vendor.wa_client_url or settings.WA_CLIENT_URL
    try:
        req = urllib.request.Request(
            f"{wa_url}/disconnect",
            data=b"{}",
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read())
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    log_with_context(logger, "info", "🚀 InstantVende Backend iniciando", host="0.0.0.0", port=8000)
    uvicorn.run(app, host="0.0.0.0", port=8000)