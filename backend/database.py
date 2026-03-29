import sqlite3
from pathlib import Path
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Boolean, Text, ForeignKey
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
from datetime import datetime

# ===== BACKUPS =====
_BACKUP_DIR = Path("./backups")


def backup_database() -> str:
    """Crea un backup timestamped usando la API nativa de SQLite (consistente incluso bajo carga)."""
    _BACKUP_DIR.mkdir(exist_ok=True)
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    backup_path = _BACKUP_DIR / f"instantvende_{timestamp}.db"
    source = sqlite3.connect("./instantvende.db")
    dest = sqlite3.connect(str(backup_path))
    try:
        source.backup(dest)
    finally:
        dest.close()
        source.close()
    return str(backup_path)


def cleanup_old_backups(max_backups: int = 10) -> None:
    """Elimina los backups más antiguos, conservando solo max_backups archivos."""
    if not _BACKUP_DIR.exists():
        return
    backups = sorted(_BACKUP_DIR.glob("instantvende_*.db"))
    while len(backups) > max_backups:
        backups.pop(0).unlink(missing_ok=True)

SQLALCHEMY_DATABASE_URL = "sqlite:///./instantvende.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, 
    connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class Product(Base):
    __tablename__ = "products"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    description = Column(Text)
    price = Column(Integer)
    stock = Column(Integer, default=0)
    image_url = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class Conversation(Base):
    __tablename__ = "conversations"
    
    id = Column(Integer, primary_key=True, index=True)
    phone = Column(String, unique=True, index=True)
    customer_name = Column(String, nullable=True)
    bot_enabled = Column(Boolean, default=True)
    last_message_at = Column(DateTime, default=datetime.utcnow)

class Message(Base):
    __tablename__ = "messages"
    
    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id"), index=True)
    content = Column(Text)
    from_customer = Column(Boolean)
    created_at = Column(DateTime, default=datetime.utcnow)


class CartItem(Base):
    __tablename__ = "cart_items"

    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id"), index=True)
    product_id = Column(Integer, ForeignKey("products.id"))
    quantity = Column(Integer, default=1)
    created_at = Column(DateTime, default=datetime.utcnow)

    product = relationship("Product")


class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id"), index=True)
    phone = Column(String, index=True)
    total = Column(Integer)          # stored in cents
    status = Column(String, default="pending")  # pending, confirmed, shipped, delivered, cancelled
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)

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


Base.metadata.create_all(bind=engine)