import os
import re
import random
import time
import threading
import concurrent.futures
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import func
from pydantic import BaseModel, ConfigDict, field_validator
from typing import List, Optional, Dict
from datetime import datetime
import ollama

from config import settings
from auth import verify_api_key, verify_api_key_optional
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
)
import bot_config

# ===== LOGGING =====
logger = setup_logger()

# Advertencia si OLLAMA_TIMEOUT es muy bajo
if settings.OLLAMA_TIMEOUT < 10:
    logger.warning(
        "⚠️  OLLAMA_TIMEOUT es menor de 10 segundos — probablemente incorrecto",
        extra={"ollama_timeout": settings.OLLAMA_TIMEOUT},
    )

# ===== RATE LIMITING EN MEMORIA =====
_message_cooldowns: dict[str, float] = {}

# ===== RESPUESTAS FRECUENTES (FAQ) =====
FAQ_RESPONSES = {
    "horario": f"""📅 *Horario de Atención:*
• {bot_config.SCHEDULE_WEEKDAY}
• {bot_config.SCHEDULE_SATURDAY}
• {bot_config.SCHEDULE_SUNDAY}

Si escribes fuera de horario, te respondo en cuanto abramos. ¿Te puedo ayudar en algo más? 😊""",

    "envio": f"""🚚 *Envíos a todo el Perú:*
• Lima Metropolitana: 24-48 horas — {bot_config.SHIPPING_LIMA_PRICE}
• Provincias: 3-5 días hábiles — {bot_config.SHIPPING_PROVINCES_PRICE}
• 🎁 *GRATIS* en compras mayores a {bot_config.SHIPPING_FREE_THRESHOLD}

Trabajamos con Olva Courier y Shalom. ¿A qué distrito te envío? 😊""",

    "pago": """💳 *Métodos de Pago:*
• 📱 Yape / Plin (¡el más rápido!)
• 🏦 Transferencia — BCP / Interbank
• 💵 Efectivo contraentrega (+S/ 5)

Todos seguros y con confirmación al instante. ¿Con cuál te queda mejor? 😊""",

    "garantia": """✅ *Garantía Fresh Boy:*
• 30 días de satisfacción garantizada
• Si no te gusta → te devolvemos el dinero
• Productos 100% originales y de calidad
• Cambios sin costo si hay defecto de fábrica

¡Vendemos con confianza! ¿Qué producto te interesa? 😊""",

    "ubicacion": f"""📍 *Encuéntranos:*
{bot_config.STORE_NAME}
{bot_config.STORE_ADDRESS}

🛵 También hacemos delivery a todo Lima el mismo día (pedidos antes de las 5 PM).
¿Prefieres venir o te lo enviamos? 😊""",

    "descuento": f"""🏷️ *Descuentos y Promos:*
• Compra 2 productos → {bot_config.DISCOUNT_TWO_PRODUCTS}% de descuento
• Compra 3 o más → {bot_config.DISCOUNT_THREE_PLUS}% de descuento
• 🎁 Envío gratis comprando más de {bot_config.SHIPPING_FREE_THRESHOLD}

¡Arma tu kit y ahorra! Escribe *#catalogo* para ver los productos. 😊""",

    "devolucion": """🔄 *Cambios y Devoluciones:*
• Tienes *30 días* desde la compra
• Producto en condiciones originales
• Coordinamos el recojo sin costo
• Reembolso al mismo método de pago

Somos flex, ¡tu satisfacción es lo primero! ¿Tuviste algún problema con tu pedido?""",

    "combo": """🎁 *Kits y Combos recomendados:*
• 🥾 *Kit Cuero*: Crema + Cepillo = ahorra 10%
• 👟 *Kit Zapatillas*: Limpiador + Protector = ahorra 10%
• 🏆 *Kit Completo*: Los 4 básicos = ahorra 15%

Escribe *#catalogo* para verlos todos y armar tu combo. 😊"""
}

# ===== KEYWORDS PARA FAQ =====
FAQ_KEYWORDS = {
    "horario":    ["horario", "hora", "cuando abren", "cuando cierran", "atienden", "abierto",
                   "disponible hoy", "abren", "trabajan"],
    "envio":      ["envio", "envío", "delivery", "despacho", "entregar", "llega", "demora",
                   "tiempo de entrega", "cuanto demora", "olva", "shalom", "courier",
                   "provincia", "envian", "envían"],
    "pago":       ["pago", "pagar", "transferencia", "yape", "plin", "efectivo", "bcp",
                   "interbank", "deposito", "depósito", "como pago", "cómo pago"],
    "garantia":   ["garantia", "garantía", "calidad", "original", "es bueno", "sirve",
                   "funciona", "confiable", "seguro"],
    "devolucion": ["devolucion", "devolución", "cambio", "cambiar", "devolver", "mal estado",
                   "defecto", "falla", "no funciono", "no funcionó", "reembolso"],
    "ubicacion":  ["ubicacion", "ubicación", "dirección", "donde", "direccion", "local",
                   "tienda", "miraflores", "visitar", "ir a la tienda"],
    "descuento":  ["descuento", "promo", "promocion", "promoción", "oferta", "barato",
                   "precio especial", "rebaja", "mas barato", "más barato"],
    "combo":      ["combo", "kit", "pack", "paquete", "varios productos", "set",
                   "todos los productos", "conjunto"],
}

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


def generate_catalog(products: List) -> str:
    """Genera catálogo formateado para WhatsApp"""
    if not products:
        return "😔 No tenemos productos disponibles en este momento. ¡Vuelve pronto!"

    catalog = f"🛍️ *CATÁLOGO {bot_config.STORE_NAME.upper()}*\n"
    catalog += "─" * 30 + "\n\n"

    for i, p in enumerate(products, 1):
        stock_emoji = "✅" if p.stock > 5 else ("⚠️" if p.stock > 0 else "❌")
        desc = (p.description[:bot_config.CATALOG_DESC_MAX_CHARS] + "...") if len(p.description) > bot_config.CATALOG_DESC_MAX_CHARS else p.description
        catalog += f"*{i}. {p.name}*\n"
        catalog += f"   💰 S/ {p.price / 100:.2f}\n"
        catalog += f"   {stock_emoji} Stock: {p.stock} unidades\n"
        catalog += f"   📝 {desc}\n"
        if p.image_url:
            catalog += f"   🖼️ {p.image_url}\n"
        catalog += "\n"

    catalog += "─" * 30 + "\n"
    catalog += "➕ Agregar producto: *agregar [número]*\n"
    catalog += "🛒 Ver carrito: *#carrito*\n"
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


def detect_intent(message: str) -> dict:
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
        "buenas", "hey", "saludos", "buen dia", "buen día", "ola"
    ]
    matched_greetings = [kw for kw in greeting_keywords if kw in message_lower]
    if matched_greetings and len(message_lower.split()) <= 5:
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
    for topic, keywords in FAQ_KEYWORDS.items():
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


def get_greeting_by_time() -> str:
    """Devuelve saludo según hora de Perú (UTC-5)"""
    from datetime import timezone, timedelta
    peru_tz = timezone(timedelta(hours=-5))
    hour = datetime.now(peru_tz).hour
    if hour < 12:
        return "Buenos días"
    elif hour < 20:
        return "Buenas tardes"
    else:
        return "Buenas noches"


def get_product_recommendations(message: str, products: List) -> List:
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
        return products[:bot_config.AI_MAX_RECOMMENDATIONS]  # devuelve los primeros si no hay match

    scored = []
    for p in products:
        product_text = (p.name + " " + p.description).lower()
        score = sum(1 for kw in relevant_product_keywords if kw in product_text)
        if score > 0:
            scored.append((score, p))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [p for _, p in scored[:bot_config.AI_MAX_RECOMMENDATIONS]] if scored else products[:bot_config.AI_MAX_RECOMMENDATIONS]

def _backup_loop() -> None:
    """Hilo daemon que realiza backups periódicos de la base de datos SQLite."""
    start_backup_scheduler(
        interval_hours=settings.BACKUP_INTERVAL_HOURS,
        max_backups=settings.MAX_BACKUPS,
    )


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Pre-cargar modelo Ollama al arrancar (dentro del lifespan para no bloquear imports)
    logger.info("⏳ Pre-cargando modelo Ollama...")
    try:
        ollama.chat(
            model=settings.OLLAMA_MODEL,
            messages=[{'role': 'user', 'content': 'test'}],
            options={'num_predict': 1}
        )
        logger.info("✅ Modelo cargado en memoria")
    except Exception as e:
        logger.warning("⚠️  No se pudo pre-cargar modelo Ollama", extra={"error": str(e)})

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


app = FastAPI(title="InstantVende API", version="1.0.0-mvp", lifespan=lifespan)
setup_exception_handlers(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

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
def get_products(db: Session = Depends(get_db), _: str = Depends(verify_api_key)):
    return db.query(Product).all()

@app.post("/api/products")
def create_product(product: ProductCreate, db: Session = Depends(get_db), _: str = Depends(verify_api_key)):
    with handle_db_errors():
        existing = db.query(Product).filter(Product.name == product.name).first()
        if existing:
            raise ProductDuplicateException(f"Ya existe un producto con el nombre '{product.name}'")
        db_product = Product(**product.dict())
        db.add(db_product)
        db.commit()
        db.refresh(db_product)
        log_with_context(logger, "info", "Producto creado", product_name=product.name, product_id=db_product.id)
        return db_product

def generate_ai_response(message: str, products: List[Product], conversation_history: List[str] = None, recently_viewed: List[str] = None) -> str:
    """
    Genera respuesta inteligente con personalidad y detección de intención
    """
    
    # Detectar intención del mensaje
    intent = detect_intent(message)
    
    # Si es una pregunta FAQ, responder directamente (más rápido)
    if intent["type"] == "faq" and intent["faq_topic"]:
        log_with_context(logger, "info", "FAQ detectada", topic=intent["faq_topic"])
        return FAQ_RESPONSES[intent["faq_topic"]]
    
    # Si es saludo
    if intent["type"] == "greeting":
        saludo = get_greeting_by_time()
        is_returning = bool(conversation_history)  # tiene historial → cliente recurrente
        if is_returning:
            greetings = [
                f"¡{saludo}! 👋 Qué bueno verte de vuelta. Soy {bot_config.BOT_NAME}. ¿Volvemos con los zapatos? 😄 ¿En qué te ayudo hoy?",
                f"¡{saludo}! 😊 ¡Bienvenido de nuevo a {bot_config.STORE_NAME}! ¿Qué necesitas esta vez?",
                f"¡{saludo}! Qué gusto que regreses. 🙌 Cuéntame, ¿qué tienes hoy para cuidar?",
            ]
        else:
            greetings = [
                f"¡{saludo}! 👋 Soy {bot_config.BOT_NAME} de *{bot_config.STORE_NAME}*. Me especializo en productos de cuidado de calzado. Escribe *#catalogo* para ver todo lo que tenemos. ¿Qué tipo de zapatos quieres cuidar?",
                f"¡{saludo}! 😊 Bienvenido a *{bot_config.STORE_NAME}*. Tenemos todo para que tus zapatos luzcan como nuevos. ¿Con qué te puedo ayudar hoy?",
                f"¡{saludo}! Mucho gusto, soy {bot_config.BOT_NAME}. 🎯 Cuéntame, ¿qué zapatos quieres recuperar?",
            ]
        return random.choice(greetings)

    # Si es despedida
    if intent["type"] == "goodbye":
        goodbyes = [
            "¡Un placer atenderte! 🙌 Si necesitas algo más, aquí estoy de lunes a sábado. ¡Que te vaya bien!",
            "¡Chau! 👋 Gracias por escribirnos. Cuando quieras cuidar tus zapatos, ya sabes dónde encontrarnos. 😊",
            "¡Hasta pronto! 🤝 Fue un gusto ayudarte. ¡Que tus zapatos brillen siempre!",
        ]
        return random.choice(goodbyes)

    # Queja: responder con empatía primero
    if intent["type"] == "complaint":
        return (
            "Oye, lamento mucho escuchar eso. 😔 Tu satisfacción es lo más importante para nosotros. "
            "Cuéntame exactamente qué pasó y lo resolvemos de inmediato, ¿ok? "
            "Tenemos garantía de 30 días y nos hacemos cargo sin problema."
        )

    # Objeción de precio: reconocer y redirigir
    if intent["type"] == "price_objection":
        return (
            f"Entiendo perfectamente, el presupuesto importa. 💰 "
            f"Tenemos opciones para todos los bolsillos, y comprar 2 productos te da {bot_config.DISCOUNT_TWO_PRODUCTS}% de descuento. "
            f"¿Me cuentas qué zapatos tienes y cuánto quieres invertir? Así te busco lo más conveniente. 😊"
        )
    
    # Enriquecer la lista de productos con recomendaciones inteligentes para el mensaje actual
    recommended = get_product_recommendations(message, products)
    all_products = products[:bot_config.AI_MAX_PRODUCTS_CONTEXT]

    def fmt_product(p: Product) -> str:
        stock_label = "✅ disponible" if p.stock > 5 else (f"⚠️ últimas {p.stock} unidades" if p.stock > 0 else "❌ agotado")
        return f"  • *{p.name}* — S/ {p.price / 100:.2f} | {stock_label}\n    {p.description[:bot_config.AI_DESC_MAX_CHARS]}"

    if recommended:
        rec_context = "PRODUCTOS RECOMENDADOS para este cliente:\n" + "\n".join(fmt_product(p) for p in recommended)
    else:
        rec_context = ""

    if all_products:
        all_context = "CATÁLOGO COMPLETO DISPONIBLE:\n" + "\n".join(fmt_product(p) for p in all_products)
    else:
        all_context = "Sin productos en stock en este momento."

    # Historial: últimos N mensajes con etiqueta (más antiguos primero)
    history_context = ""
    if conversation_history:
        history_context = f"\n\n📜 HISTORIAL RECIENTE (últimos mensajes):\n" + "\n".join(conversation_history[-bot_config.HISTORY_MESSAGES_LIMIT:])

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

    saludo_hora = get_greeting_by_time()

    system_prompt = f"""Eres *{bot_config.BOT_NAME}*, el vendedor estrella de *{bot_config.STORE_NAME}* con 5 años de experiencia en cuidado de calzado.

🧠 TU PERSONALIDAD:
- Eres cálido, cercano y carismático — como hablar con un amigo que sabe mucho de zapatos
- Usas lenguaje natural peruano (puedes decir "bacán", "jale", "pe" pero sin exagerar)
- Máximo 1-2 emojis por respuesta (no spamear emojis)
- SIEMPRE respondes en español, nunca en inglés
- No eres robótico: varía tus frases, no repitas las mismas palabras
- Eres honesto: si un producto no aplica al caso del cliente, lo dices

🎯 ESTRATEGIA DE VENTA:
1. Primero ESCUCHA y DIAGNOSTICA el problema del cliente
2. Luego recomienda el producto EXACTO con nombre y precio
3. Explica POR QUÉ ese producto resuelve SU problema específico
4. Cierra con pregunta o CTA (call-to-action)
5. Nunca presiones — sugiere con confianza

💡 MANEJO DE SITUACIONES:
- Cliente indeciso → haz UNA pregunta de clarificación (material, color, tipo de zapato)
- Cliente pregunta precio → dígale inmediatamente, sin rodeos
- Cliente tiene carrito → menciónalo sutilmente y anima a confirmar
- Cliente dice "es caro" → muestra el valor, menciona la garantía, sugiere combos
- No sabes la respuesta → di "déjame verificarlo" y deriva a #ayuda

{rec_context}

{all_context}

📋 COMANDOS QUE PUEDE USAR EL CLIENTE:
- *#catalogo* → ver todos los productos
- *agregar [número]* → agregar al carrito (ej: agregar 2)
- *#carrito* → ver su carrito
- *#pedido* → confirmar compra
- *#ayuda* → más ayuda

INFO TIENDA:
- Envíos: Lima 24-48h ({bot_config.SHIPPING_LIMA_PRICE}) | Provincias 3-5 días ({bot_config.SHIPPING_PROVINCES_PRICE}) | Gratis sobre {bot_config.SHIPPING_FREE_THRESHOLD}
- Pagos: Yape, Plin, transferencia BCP/Interbank, efectivo
- Garantía: 30 días satisfacción garantizada
- Horario: {saludo_hora} — {bot_config.SCHEDULE_WEEKDAY} | {bot_config.SCHEDULE_SATURDAY}
{history_context}{cart_context}{intent_hint}

✍️ ESTILO DE RESPUESTA:
- Máximo 4 líneas (conciso, no bloques de texto)
- Siempre termina con pregunta O call-to-action (nunca ambos)
- Usa *negrita* para nombres de productos y precios
- NUNCA generes listas largas — eso lo hace el comando #catalogo

EJEMPLOS DE BUENAS RESPUESTAS:
• "Mis zapatillas blancas están amarillentas" → "¡Clásico problema! 😅 Para eso te va perfecto el *Limpiador Espuma Premium* (S/ 15) — saca las manchas de tela y lona sin dañarlas. Escribe *agregar [número]* para añadirlo. ¿Qué número calzas? (Por si acaso 😄)"
• "¿Cuánto cuesta la crema?" → "La *Crema Restauradora Cuero* está a *S/ 18* y dura varios meses. ¿Es para zapatos claros u oscuros? Así te doy el tip de aplicación exacto. 😊"
• "Quiero algo para mis botas de cuero" → "Bacán, las botas de cuero necesitan dos cosas: limpieza y nutrición. Te recomiendo el *Kit Cuero* (crema + cepillo) que sale más económico. ¿Las botas son negras o de otro color?"
"""

    try:
        start_time = time.time()
        log_with_context(logger, "info", "Generando respuesta con IA", intent=intent['type'])

        ollama_messages = [
            {'role': 'system', 'content': system_prompt},
            {'role': 'user', 'content': message}
        ]
        ollama_options = {
            'temperature': 0.8,
            'num_predict': 80,
            'num_ctx': 1024,
            'top_p': 0.9,
            'repeat_penalty': 1.2,
            'num_thread': 4,
        }

        # Llamada con timeout de 45 segundos para no bloquear al cliente
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(
                ollama.chat,
                model=settings.OLLAMA_MODEL,
                messages=ollama_messages,
                options=ollama_options
            )
            try:
                response = future.result(timeout=settings.OLLAMA_TIMEOUT)
            except concurrent.futures.TimeoutError:
                log_with_context(logger, "warning", "Ollama timeout", timeout=settings.OLLAMA_TIMEOUT)
                return (
                    "Disculpa la demora 🙏 Escribe *#catalogo* para ver todos nuestros productos "
                    "o cuéntame más sobre lo que necesitas y te ayudo de inmediato."
                )

        elapsed = time.time() - start_time
        ai_message = response['message']['content'].strip()

        # Fallback si Ollama devuelve respuesta vacía o solo espacios
        if not ai_message:
            log_with_context(logger, "warning", "Ollama devolvió respuesta vacía")
            return (
                "Disculpa, no pude procesar eso bien. 😅 "
                "Escribe *#catalogo* para ver nuestros productos o *#ayuda* para los comandos."
            )

        # Truncar respuesta excesivamente larga al último punto o salto de línea antes del límite
        max_chars = bot_config.AI_RESPONSE_MAX_CHARS
        if len(ai_message) > max_chars:
            truncated = ai_message[:max_chars]
            # Buscar el último punto o salto de línea para corte limpio
            last_break = max(truncated.rfind('.'), truncated.rfind('\n'))
            if last_break > max_chars // 2:
                ai_message = truncated[:last_break + 1].strip()
            else:
                ai_message = truncated.rstrip() + "..."

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
        return (
            "Disculpa, tuve un problemita técnico 😅 "
            "Escribe *#catalogo* para ver nuestros productos o *#ayuda* para ver los comandos disponibles."
        )

@app.post("/api/process-message")
def process_message(request: MessageRequest, db: Session = Depends(get_db), _: str = Depends(verify_api_key)):
    """Procesar mensaje con IA, comandos y manejo de carrito/pedidos"""

    log_with_context(logger, "info", "Nuevo mensaje recibido", phone=request.phone[-4:], message=request.message[:100])

    # Rate limiting: evitar procesamiento doble si el mismo número envía mensajes consecutivos
    now = time.time()
    # Limpiar entradas antiguas (> 5 minutos) para evitar memory leak
    _COOLDOWN_CLEANUP_SECONDS = 300
    stale_cutoff = now - _COOLDOWN_CLEANUP_SECONDS
    stale_keys = [k for k, v in _message_cooldowns.items() if v < stale_cutoff]
    for k in stale_keys:
        del _message_cooldowns[k]

    last_ts = _message_cooldowns.get(request.phone)
    if last_ts is not None and (now - last_ts) < bot_config.MESSAGE_COOLDOWN_SECONDS:
        raise RateLimitException("Un momento, estoy procesando tu mensaje anterior 🙏")
    _message_cooldowns[request.phone] = now

    # 1. Buscar o crear conversación
    conversation = db.query(Conversation).filter(
        Conversation.phone == request.phone
    ).first()

    if not conversation:
        conversation = Conversation(phone=request.phone)
        db.add(conversation)
        db.commit()
        db.refresh(conversation)
        log_with_context(logger, "info", "Nueva conversación creada", conversation_id=conversation.id)
    else:
        log_with_context(logger, "info", "Conversación existente", conversation_id=conversation.id)

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
        return {
            "reply": None,
            "bot_enabled": False,
            "message": "Bot desactivado. Respuesta manual requerida."
        }

    # 4. Detectar comandos
    command = detect_command(request.message)
    ai_response = None
    media_url = None

    if command == "catalog":
        products = db.query(Product).filter(Product.stock > 0).all()
        ai_response = generate_catalog(products)
        log_with_context(logger, "info", "Comando: catálogo", product_count=len(products))

    elif command == "cart":
        cart_items = db.query(CartItem).filter(
            CartItem.conversation_id == conversation.id
        ).all()
        product_ids = [item.product_id for item in cart_items]
        products_list = db.query(Product).filter(Product.id.in_(product_ids)).all() if product_ids else []
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
            products_list = db.query(Product).filter(Product.id.in_(product_ids)).all()
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
                # Crear pedido
                with handle_db_errors():
                    order = Order(
                        conversation_id=conversation.id,
                        phone=request.phone,
                        total=total,
                        status="pending"
                    )
                    db.add(order)
                    db.commit()
                    db.refresh(order)

                    # Crear items del pedido y descontar stock
                    for item in cart_items:
                        product = products_dict.get(item.product_id)
                        if product:
                            db.add(OrderItem(
                                order_id=order.id,
                                product_id=product.id,
                                product_name=product.name,
                                product_price=product.price,
                                quantity=item.quantity
                            ))
                            product.stock -= item.quantity

                    # Vaciar carrito
                    db.query(CartItem).filter(
                        CartItem.conversation_id == conversation.id
                    ).delete()
                    db.commit()

                ai_response = (
                    f"✅ *¡PEDIDO CONFIRMADO!*\n"
                    f"─────────────────────────\n"
                    f"🔖 Pedido #{order.id}\n"
                    f"💰 Total: S/ {total / 100:.2f}\n"
                    f"📋 Estado: Pendiente de confirmación\n\n"
                    f"📞 Te contactaremos para coordinar pago y envío.\n"
                    f"💳 Pagos: Yape, Plin, transferencia\n\n"
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
        ai_response = BOT_HELP_TEXT
        log_with_context(logger, "info", "Comando: ayuda")

    elif command == "status":
        last_order = db.query(Order).filter(
            Order.phone == request.phone
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
            products = db.query(Product).filter(Product.stock > 0).all()

            if 1 <= product_num <= len(products):
                product = products[product_num - 1]

                if product.stock < 1:
                    ai_response = f"⚠️ Lo siento, *{product.name}* está agotado.\n\nEscribe *#catalogo* para ver otros productos disponibles."
                else:
                    existing = db.query(CartItem).filter(
                        CartItem.conversation_id == conversation.id,
                        CartItem.product_id == product.id
                    ).first()

                    if existing:
                        existing.quantity += 1
                    else:
                        db.add(CartItem(
                            conversation_id=conversation.id,
                            product_id=product.id,
                            quantity=1
                        ))
                    db.commit()

                    if product.image_url:
                        media_url = product.image_url

                    ai_response = (
                        f"✅ *{product.name}* agregado al carrito!\n"
                        f"💰 Precio: S/ {product.price / 100:.2f}\n\n"
                        f"🛒 Ver carrito: *#carrito*\n"
                        f"📦 Confirmar pedido: *#pedido*\n"
                        f"📋 Seguir comprando: *#catalogo*"
                    )
                    log_with_context(logger, "info", "Producto agregado al carrito", product_num=product_num, product_name=product.name)
            else:
                ai_response = f"⚠️ Número inválido. Escribe *#catalogo* para ver los productos disponibles (1 al {len(products)})."
        else:
            ai_response = "⚠️ Por favor indica el número de producto. Ejemplo: *agregar 1*"

    # 5. Si no fue un comando → usar IA
    if ai_response is None:
        recent_messages = db.query(Message).filter(
            Message.conversation_id == conversation.id
        ).order_by(Message.created_at.desc()).limit(bot_config.HISTORY_MESSAGES_LIMIT).all()

        conversation_history = [
            f"{'Cliente' if msg.from_customer else bot_config.BOT_NAME}: {msg.content}"
            for msg in reversed(recent_messages)
        ]

        cart_items = db.query(CartItem).filter(
            CartItem.conversation_id == conversation.id
        ).all()
        recently_viewed = [str(item.product_id) for item in cart_items]

        products = db.query(Product).filter(Product.stock > 0).all()
        log_with_context(logger, "info", "Procesando con IA", product_count=len(products))

        ai_response = generate_ai_response(
            message=request.message,
            products=products,
            conversation_history=conversation_history,
            recently_viewed=recently_viewed
        )

    # 6. Guardar respuesta del bot
    db.add(Message(
        conversation_id=conversation.id,
        content=ai_response,
        from_customer=False
    ))

    # 7. Actualizar timestamp
    conversation.last_message_at = datetime.utcnow()
    db.commit()

    log_with_context(logger, "info", "Respuesta enviada", preview=ai_response[:60])

    return {
        "reply": ai_response,
        "bot_enabled": True,
        "conversation_id": conversation.id,
        "media_url": media_url,
        "timestamp": datetime.utcnow().isoformat()
    }

# ===== ENDPOINTS DE CONVERSACIONES =====

@app.get("/api/conversations")
def get_conversations(db: Session = Depends(get_db), _: str = Depends(verify_api_key)):
    """Obtener todas las conversaciones ordenadas por más reciente"""
    conversations = db.query(Conversation).order_by(
        Conversation.last_message_at.desc()
    ).all()
    return conversations

@app.get("/api/conversations/{conversation_id}/messages")
def get_messages(conversation_id: int, db: Session = Depends(get_db), _: str = Depends(verify_api_key)):
    """Obtener todos los mensajes de una conversación específica"""
    conversation = db.query(Conversation).filter(
        Conversation.id == conversation_id
    ).first()

    if not conversation:
        raise ConversationNotFoundException(f"Conversación {conversation_id} no encontrada")

    messages = db.query(Message).filter(
        Message.conversation_id == conversation_id
    ).order_by(Message.created_at.asc()).all()

    return messages

@app.patch("/api/conversations/{conversation_id}/toggle-bot")
def toggle_bot(conversation_id: int, enabled: bool, db: Session = Depends(get_db), _: str = Depends(verify_api_key)):
    """Activar/desactivar bot para una conversación (para intervención humana)"""
    conversation = db.query(Conversation).filter(
        Conversation.id == conversation_id
    ).first()
    
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversación no encontrada")
    
    conversation.bot_enabled = enabled
    db.commit()
    
    action = "activado" if enabled else "desactivado"
    log_with_context(logger, "info", f"Bot {action}", conversation_id=conversation_id)
    
    return {
        "bot_enabled": conversation.bot_enabled,
        "conversation_id": conversation_id,
        "message": f"Bot {action} exitosamente"
    }


# ===== ENDPOINTS DE CARRITO =====

@app.post("/api/cart/{phone}/add")
def api_add_to_cart(phone: str, item: CartItemRequest, db: Session = Depends(get_db), _: str = Depends(verify_api_key)):
    """Agregar producto al carrito vía API"""
    conversation = db.query(Conversation).filter(Conversation.phone == phone).first()
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversación no encontrada")

    product = db.query(Product).filter(Product.id == item.product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    if product.stock < item.quantity:
        raise HTTPException(status_code=400, detail=f"Stock insuficiente. Disponible: {product.stock}")

    existing = db.query(CartItem).filter(
        CartItem.conversation_id == conversation.id,
        CartItem.product_id == item.product_id
    ).first()

    if existing:
        with handle_db_errors():
            existing.quantity += item.quantity
            db.commit()
    else:
        with handle_db_errors():
            db.add(CartItem(
                conversation_id=conversation.id,
                product_id=item.product_id,
                quantity=item.quantity
            ))
            db.commit()
    return {"message": f"{product.name} agregado al carrito", "product": product.name, "quantity": item.quantity}


@app.get("/api/cart/{phone}")
def api_get_cart(phone: str, db: Session = Depends(get_db), _: str = Depends(verify_api_key)):
    """Ver carrito de un cliente vía API"""
    conversation = db.query(Conversation).filter(Conversation.phone == phone).first()
    if not conversation:
        return {"items": [], "total": 0, "total_soles": 0.0}

    cart_items = db.query(CartItem).filter(
        CartItem.conversation_id == conversation.id
    ).all()

    result = []
    total = 0
    for item in cart_items:
        product = db.query(Product).filter(Product.id == item.product_id).first()
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
def api_clear_cart(phone: str, db: Session = Depends(get_db), _: str = Depends(verify_api_key)):
    """Vaciar carrito de un cliente"""
    conversation = db.query(Conversation).filter(Conversation.phone == phone).first()
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversación no encontrada")
    deleted = db.query(CartItem).filter(
        CartItem.conversation_id == conversation.id
    ).delete()
    db.commit()
    return {"message": f"Carrito vaciado. {deleted} item(s) eliminados."}


# ===== ENDPOINTS DE PEDIDOS =====

@app.get("/api/orders")
def get_orders(status: Optional[str] = None, db: Session = Depends(get_db), _: str = Depends(verify_api_key)):
    """Listar todos los pedidos, opcionalmente filtrados por estado"""
    query = db.query(Order)
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
def get_order(order_id: int, db: Session = Depends(get_db), _: str = Depends(verify_api_key)):
    """Obtener detalles de un pedido específico"""
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Pedido no encontrado")

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
def update_order_status(order_id: int, update: OrderStatusUpdate, db: Session = Depends(get_db), _: str = Depends(verify_api_key)):
    """Actualizar estado de un pedido (y restaurar stock si se cancela)"""
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Pedido no encontrado")

    with handle_db_errors():
        # Restaurar stock si se cancela
        if update.status == "cancelled" and order.status != "cancelled":
            for item in db.query(OrderItem).filter(OrderItem.order_id == order_id).all():
                product = db.query(Product).filter(Product.id == item.product_id).first()
                if product:
                    product.stock += item.quantity

        order.status = update.status
        order.updated_at = datetime.utcnow()
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
def get_analytics(db: Session = Depends(get_db), _: str = Depends(verify_api_key)):
    """Dashboard de métricas y estadísticas"""
    total_revenue = db.query(func.sum(Order.total)).filter(
        Order.status.in_(["confirmed", "shipped", "delivered"])
    ).scalar() or 0

    orders_by_status = db.query(
        Order.status, func.count(Order.id)
    ).group_by(Order.status).all()

    top_products = db.query(
        OrderItem.product_name,
        func.sum(OrderItem.quantity).label("total_sold"),
        func.sum(OrderItem.product_price * OrderItem.quantity).label("revenue"),
    ).group_by(OrderItem.product_name).order_by(
        func.sum(OrderItem.quantity).desc()
    ).limit(5).all()

    return {
        "conversations": {
            "total": db.query(func.count(Conversation.id)).scalar() or 0,
        },
        "messages": {
            "total": db.query(func.count(Message.id)).scalar() or 0,
        },
        "orders": {
            "total": db.query(func.count(Order.id)).scalar() or 0,
            "by_status": {status: count for status, count in orders_by_status},
            "pending":   db.query(func.count(Order.id)).filter(Order.status == "pending").scalar() or 0,
            "confirmed": db.query(func.count(Order.id)).filter(Order.status == "confirmed").scalar() or 0,
            "shipped":   db.query(func.count(Order.id)).filter(Order.status == "shipped").scalar() or 0,
            "delivered": db.query(func.count(Order.id)).filter(Order.status == "delivered").scalar() or 0,
            "cancelled": db.query(func.count(Order.id)).filter(Order.status == "cancelled").scalar() or 0,
        },
        "revenue": {
            "total_soles": total_revenue / 100,
        },
        "products": {
            "total": db.query(func.count(Product.id)).scalar() or 0,
            "in_stock": db.query(func.count(Product.id)).filter(Product.stock > 0).scalar() or 0,
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

if __name__ == "__main__":
    import uvicorn
    logger.info("🚀 InstantVende Backend iniciando", host="0.0.0.0", port=8000)
    uvicorn.run(app, host="0.0.0.0", port=8000)