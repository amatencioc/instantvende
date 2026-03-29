from sqlalchemy import create_engine, event, Column, Integer, String, DateTime, Boolean, Text, ForeignKey
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

class Product(Base):
    __tablename__ = "products"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, unique=True)
    description = Column(Text)
    price = Column(Integer)
    stock = Column(Integer, default=0)
    image_url = Column(String, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

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

class Conversation(Base):
    __tablename__ = "conversations"
    
    id = Column(Integer, primary_key=True, index=True)
    phone = Column(String, unique=True, index=True)
    customer_name = Column(String, nullable=True)
    bot_enabled = Column(Boolean, default=True)
    last_message_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

class Message(Base):
    __tablename__ = "messages"
    
    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id"), index=True)
    content = Column(Text)
    from_customer = Column(Boolean)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class CartItem(Base):
    __tablename__ = "cart_items"

    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id"), index=True)
    product_id = Column(Integer, ForeignKey("products.id"))
    quantity = Column(Integer, default=1)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    product = relationship("Product")


class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id"), index=True)
    phone = Column(String, index=True)
    total = Column(Integer)          # stored in cents
    status = Column(String, default="pending")  # pending, confirmed, shipped, delivered, cancelled
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    items = relationship("OrderItem", back_populates="order")


class OrderItem(Base):
    __tablename__ = "order_items"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"), index=True)
    product_id = Column(Integer, ForeignKey("products.id"))
    product_name = Column(String)    # snapshot at order time
    product_price = Column(Integer)  # snapshot at order time (cents)
    quantity = Column(Integer)

    order = relationship("Order", back_populates="items")


class BotProfile(Base):
    """Perfil dinámico del bot — editado desde el panel de administración."""
    __tablename__ = "bot_profiles"

    id = Column(Integer, primary_key=True, index=True)
    profile_json = Column(Text, nullable=False)   # JSON completo del perfil
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    updated_by = Column(String, nullable=True)    # quién hizo el último cambio


Base.metadata.create_all(bind=engine)