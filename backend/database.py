import secrets as _secrets

from sqlalchemy import (
    create_engine, event, Column, Integer, String, DateTime, Boolean, Text,
    ForeignKey, UniqueConstraint, CheckConstraint, Index,
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker, validates
from datetime import datetime, timezone

SQLALCHEMY_DATABASE_URL = "sqlite:///./instantvende.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={
        "check_same_thread": False,
        "timeout": 30,            # esperar hasta 30s si la DB está bloqueada
    },
    pool_size=5,                  # conexiones concurrentes permitidas
    max_overflow=10,              # conexiones extra bajo carga
    pool_timeout=30,              # tiempo máximo de espera por conexión del pool
    pool_pre_ping=True,           # verificar conexión antes de usarla
)


@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")      # WAL permite lecturas concurrentes
    cursor.execute("PRAGMA synchronous=NORMAL")    # balance entre seguridad y velocidad
    cursor.execute("PRAGMA cache_size=-64000")     # 64MB de caché
    cursor.execute("PRAGMA foreign_keys=ON")       # integridad referencial
    cursor.execute("PRAGMA busy_timeout=30000")    # 30s timeout en Python level también
    cursor.close()


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# =============================================================================
# VENDOR — must be defined before all tables that reference it
# =============================================================================

class Vendor(Base):
    """Vendedor registrado en el sistema."""
    __tablename__ = "vendors"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, nullable=False, unique=True, index=True)
    business_name = Column(String, nullable=True)
    hashed_password = Column(String, nullable=False)
    api_key = Column(String, unique=True, index=True, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    wa_client_url = Column(String, nullable=True)    # URL del servidor HTTP del cliente WA de este vendor
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relaciones — cascade delete-orphan para aislamiento completo
    conversations = relationship(
        "Conversation", back_populates="vendor", cascade="all, delete-orphan"
    )
    products = relationship(
        "Product", back_populates="vendor", cascade="all, delete-orphan"
    )
    bot_profile = relationship(
        "BotProfile",
        back_populates="vendor",
        foreign_keys="BotProfile.vendor_id",
        uselist=False,
        cascade="all, delete-orphan",
    )
    orders = relationship(
        "Order", back_populates="vendor", cascade="all, delete-orphan"
    )
    whatsapp_session = relationship(
        "WhatsappSession", back_populates="vendor", uselist=False, cascade="all, delete-orphan"
    )


# =============================================================================
# WHATSAPP SESSION — un registro por vendor
# =============================================================================

class WhatsappSession(Base):
    """Estado de sesión de WhatsApp por vendedor."""
    __tablename__ = "whatsapp_sessions"

    id = Column(Integer, primary_key=True, index=True)
    vendor_id = Column(
        Integer,
        ForeignKey("vendors.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    status = Column(String, default="disconnected")  # disconnected | connecting | connected
    qr_code = Column(Text, nullable=True)            # data URL del QR actual
    phone_number = Column(String, nullable=True)     # número vinculado
    session_data = Column(Text, nullable=True)       # datos extra (JSON)
    connected_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    vendor = relationship("Vendor", back_populates="whatsapp_session")


# =============================================================================
# PRODUCT — aislado por vendor
# =============================================================================

class Product(Base):
    __tablename__ = "products"
    __table_args__ = (
        UniqueConstraint("vendor_id", "name", name="uq_vendor_product_name"),
    )

    id = Column(Integer, primary_key=True, index=True)
    vendor_id = Column(
        Integer,
        ForeignKey("vendors.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name = Column(String, nullable=False)
    description = Column(Text)
    price = Column(Integer)
    stock = Column(Integer, default=0)
    image_url = Column(String, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    vendor = relationship("Vendor", back_populates="products")

    @validates("stock")
    def validate_stock(self, key: str, value: int) -> int:
        if value < 0:
            raise ValueError("El stock no puede ser negativo")
        return value

    @validates("price")
    def validate_price(self, key: str, value: int) -> int:
        if value < 1:
            raise ValueError("El precio debe ser mayor a 0 centavos")
        if value > 100_000_00:
            raise ValueError("El precio excede el límite permitido")
        return value


# =============================================================================
# CONVERSATION — aislada por vendor
# =============================================================================

class Conversation(Base):
    __tablename__ = "conversations"
    __table_args__ = (
        UniqueConstraint("vendor_id", "phone", name="uq_vendor_conversation_phone"),
    )

    id = Column(Integer, primary_key=True, index=True)
    vendor_id = Column(
        Integer,
        ForeignKey("vendors.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    phone = Column(String, index=True)
    customer_name = Column(String, nullable=True)
    bot_enabled = Column(Boolean, default=True)
    last_message_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    vendor = relationship("Vendor", back_populates="conversations")
    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan")
    cart_items = relationship("CartItem", back_populates="conversation", cascade="all, delete-orphan")


# =============================================================================
# MESSAGE
# =============================================================================

class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(
        Integer, ForeignKey("conversations.id", ondelete="CASCADE"), index=True
    )
    content = Column(Text)
    from_customer = Column(Boolean)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    conversation = relationship("Conversation", back_populates="messages")


# =============================================================================
# CART ITEM
# =============================================================================

class CartItem(Base):
    __tablename__ = "cart_items"

    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(
        Integer, ForeignKey("conversations.id", ondelete="CASCADE"), index=True
    )
    product_id = Column(Integer, ForeignKey("products.id"))
    quantity = Column(Integer, default=1)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    conversation = relationship("Conversation", back_populates="cart_items")
    product = relationship("Product")


# =============================================================================
# ORDER — aislado por vendor
# =============================================================================

class Order(Base):
    __tablename__ = "orders"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending','confirmed','shipped','delivered','cancelled')",
            name="ck_order_status",
        ),
        Index("ix_orders_vendor_status", "vendor_id", "status"),
        Index("ix_orders_vendor_phone", "vendor_id", "phone"),
    )

    id = Column(Integer, primary_key=True, index=True)
    vendor_id = Column(
        Integer,
        ForeignKey("vendors.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    conversation_id = Column(Integer, ForeignKey("conversations.id"), index=True)
    phone = Column(String, index=True)
    total = Column(Integer)          # stored in cents
    status = Column(String, default="pending")
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    vendor = relationship("Vendor", back_populates="orders")
    items = relationship("OrderItem", back_populates="order")


# =============================================================================
# ORDER ITEM
# =============================================================================

class OrderItem(Base):
    __tablename__ = "order_items"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"), index=True)
    product_id = Column(Integer, ForeignKey("products.id"))
    product_name = Column(String)    # snapshot at order time
    product_price = Column(Integer)  # snapshot at order time (cents)
    quantity = Column(Integer)

    order = relationship("Order", back_populates="items")


# =============================================================================
# BOT PROFILE — uno por vendor
# =============================================================================

class BotProfile(Base):
    """Perfil dinámico del bot — uno por vendedor."""
    __tablename__ = "bot_profiles"

    id = Column(Integer, primary_key=True, index=True)
    vendor_id = Column(
        Integer,
        ForeignKey("vendors.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    profile_json = Column(Text, nullable=False)
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    updated_by_vendor_id = Column(Integer, ForeignKey("vendors.id"), nullable=True)

    vendor = relationship("Vendor", foreign_keys=[vendor_id], back_populates="bot_profile")


# =============================================================================
# MIGRATION — agrega columnas faltantes a tablas existentes sin Alembic
# =============================================================================

def _run_migrations() -> None:
    """Migra esquemas existentes al nuevo diseño multi-tenant sin perder datos."""
    from sqlalchemy import text, inspect as sa_inspect

    inspector = sa_inspect(engine)
    existing_tables = set(inspector.get_table_names())

    def col_names(table: str):
        return {c["name"] for c in inspector.get_columns(table)}

    with engine.begin() as conn:
        # Desactivar FK durante la migración para poder recrear tablas
        conn.execute(text("PRAGMA foreign_keys=OFF"))

        # ── vendors ─────────────────────────────────────────────────────────
        if "vendors" in existing_tables:
            vcols = col_names("vendors")
            if "api_key" not in vcols:
                conn.execute(text("ALTER TABLE vendors ADD COLUMN api_key VARCHAR"))
            if "is_active" not in vcols:
                conn.execute(text("ALTER TABLE vendors ADD COLUMN is_active BOOLEAN DEFAULT 1"))
            if "updated_at" not in vcols:
                conn.execute(text("ALTER TABLE vendors ADD COLUMN updated_at DATETIME"))
            if "wa_client_url" not in vcols:
                conn.execute(text("ALTER TABLE vendors ADD COLUMN wa_client_url VARCHAR"))
            # Generar api_key única para vendors que aún no tienen una
            rows = conn.execute(text("SELECT id FROM vendors WHERE api_key IS NULL")).fetchall()
            existing_keys: set[str] = {
                r[0] for r in conn.execute(
                    text("SELECT api_key FROM vendors WHERE api_key IS NOT NULL")
                ).fetchall()
            }
            for (vid,) in rows:
                for _ in range(10):
                    key = _secrets.token_urlsafe(32)
                    if key not in existing_keys:
                        existing_keys.add(key)
                        conn.execute(
                            text("UPDATE vendors SET api_key=:k WHERE id=:i"),
                            {"k": key, "i": vid},
                        )
                        break

        # ID del primer vendor para asignar registros huérfanos
        first_vendor_id: int | None = None
        if "vendors" in existing_tables:
            row = conn.execute(text("SELECT id FROM vendors ORDER BY id LIMIT 1")).fetchone()
            if row:
                first_vendor_id = row[0]

        fvid = first_vendor_id  # abreviación

        # ── conversations ────────────────────────────────────────────────────
        if "conversations" in existing_tables:
            ccols = col_names("conversations")
            if "vendor_id" not in ccols:
                # Recrear tabla con nuevo esquema (elimina unique(phone) global)
                conn.execute(text("""
                    CREATE TABLE conversations_new (
                        id INTEGER PRIMARY KEY,
                        vendor_id INTEGER REFERENCES vendors(id) ON DELETE CASCADE,
                        phone VARCHAR,
                        customer_name VARCHAR,
                        bot_enabled BOOLEAN DEFAULT 1,
                        last_message_at DATETIME
                    )
                """))
                vid_expr = str(fvid) if fvid else "NULL"
                conn.execute(text(f"""
                    INSERT INTO conversations_new
                        (id, vendor_id, phone, customer_name, bot_enabled, last_message_at)
                    SELECT id, {vid_expr}, phone, customer_name, bot_enabled, last_message_at
                    FROM conversations
                """))
                conn.execute(text("DROP TABLE conversations"))
                conn.execute(text("ALTER TABLE conversations_new RENAME TO conversations"))
                conn.execute(text(
                    "CREATE INDEX IF NOT EXISTS ix_conversations_vendor_id ON conversations(vendor_id)"
                ))
                conn.execute(text(
                    "CREATE INDEX IF NOT EXISTS ix_conversations_phone ON conversations(phone)"
                ))
                conn.execute(text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS uq_vendor_conversation_phone "
                    "ON conversations(vendor_id, phone)"
                ))

        # ── products ─────────────────────────────────────────────────────────
        if "products" in existing_tables:
            pcols = col_names("products")
            if "vendor_id" not in pcols:
                conn.execute(text("""
                    CREATE TABLE products_new (
                        id INTEGER PRIMARY KEY,
                        vendor_id INTEGER REFERENCES vendors(id) ON DELETE CASCADE,
                        name VARCHAR NOT NULL,
                        description TEXT,
                        price INTEGER,
                        stock INTEGER DEFAULT 0,
                        image_url VARCHAR,
                        created_at DATETIME
                    )
                """))
                vid_expr = str(fvid) if fvid else "NULL"
                conn.execute(text(f"""
                    INSERT INTO products_new
                        (id, vendor_id, name, description, price, stock, image_url, created_at)
                    SELECT id, {vid_expr}, name, description, price, stock, image_url, created_at
                    FROM products
                """))
                conn.execute(text("DROP TABLE products"))
                conn.execute(text("ALTER TABLE products_new RENAME TO products"))
                conn.execute(text(
                    "CREATE INDEX IF NOT EXISTS ix_products_vendor_id ON products(vendor_id)"
                ))
                conn.execute(text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS uq_vendor_product_name "
                    "ON products(vendor_id, name)"
                ))

        # ── orders ───────────────────────────────────────────────────────────
        if "orders" in existing_tables:
            ocols = col_names("orders")
            if "vendor_id" not in ocols:
                conn.execute(text("""
                    CREATE TABLE orders_new (
                        id INTEGER PRIMARY KEY,
                        vendor_id INTEGER REFERENCES vendors(id) ON DELETE CASCADE,
                        conversation_id INTEGER REFERENCES conversations(id),
                        phone VARCHAR,
                        total INTEGER,
                        status VARCHAR DEFAULT 'pending',
                        notes TEXT,
                        created_at DATETIME,
                        updated_at DATETIME
                    )
                """))
                vid_expr = str(fvid) if fvid else "NULL"
                conn.execute(text(f"""
                    INSERT INTO orders_new
                        (id, vendor_id, conversation_id, phone, total, status,
                         notes, created_at, updated_at)
                    SELECT id, {vid_expr}, conversation_id, phone, total, status,
                           notes, created_at, updated_at
                    FROM orders
                """))
                conn.execute(text("DROP TABLE orders"))
                conn.execute(text("ALTER TABLE orders_new RENAME TO orders"))
                conn.execute(text(
                    "CREATE INDEX IF NOT EXISTS ix_orders_vendor_id ON orders(vendor_id)"
                ))
                conn.execute(text(
                    "CREATE INDEX IF NOT EXISTS ix_orders_conversation_id ON orders(conversation_id)"
                ))
                conn.execute(text(
                    "CREATE INDEX IF NOT EXISTS ix_orders_phone ON orders(phone)"
                ))
                conn.execute(text(
                    "CREATE INDEX IF NOT EXISTS ix_orders_vendor_status ON orders(vendor_id, status)"
                ))
                conn.execute(text(
                    "CREATE INDEX IF NOT EXISTS ix_orders_vendor_phone ON orders(vendor_id, phone)"
                ))

        # ── bot_profiles ─────────────────────────────────────────────────────
        if "bot_profiles" in existing_tables:
            bpcols = col_names("bot_profiles")
            if "vendor_id" not in bpcols:
                conn.execute(text(
                    "ALTER TABLE bot_profiles ADD COLUMN vendor_id INTEGER REFERENCES vendors(id)"
                ))
                if fvid:
                    conn.execute(text(
                        "UPDATE bot_profiles SET vendor_id=:v WHERE vendor_id IS NULL"
                    ), {"v": fvid})
                conn.execute(text(
                    "CREATE INDEX IF NOT EXISTS ix_bot_profiles_vendor_id ON bot_profiles(vendor_id)"
                ))
            if "updated_by_vendor_id" not in bpcols:
                conn.execute(text(
                    "ALTER TABLE bot_profiles ADD COLUMN "
                    "updated_by_vendor_id INTEGER REFERENCES vendors(id)"
                ))

        conn.execute(text("PRAGMA foreign_keys=ON"))


# Ejecutar migraciones antes de create_all para que las tablas existentes
# reciban las columnas nuevas antes de que SQLAlchemy intente crearlas.
_run_migrations()
Base.metadata.create_all(bind=engine)