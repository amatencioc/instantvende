# 🛍️ InstantVende MVP

**Bot de ventas para WhatsApp con IA local (Ollama) — para pequeños negocios**

InstantVende permite a tiendas pequeñas tener un **vendedor automático en WhatsApp** que atiende clientes 24/7, maneja catálogo de productos, carritos de compra y pedidos — todo sin necesidad de servicios cloud de IA.

---

## ✨ Funcionalidades

| Módulo | Descripción |
|--------|-------------|
| 🤖 **Bot IA (Favio)** | Vendedor carismático con personalidad definida — responde naturalmente en español |
| 📋 **Catálogo interactivo** | Clientes escriben `#catalogo` y ven todos los productos formateados |
| 🛒 **Carrito de compras** | Agregan productos con `agregar [número]`, ven su carrito con `#carrito` |
| 📦 **Pedidos** | Confirmación con `#pedido`, tracking de estado (pendiente → enviado → entregado) |
| ✅ **Validación de stock** | Avisos automáticos si un producto está agotado |
| 💬 **FAQ automático** | Respuestas instantáneas a horarios, envíos, pagos, garantía, devoluciones |
| 🧠 **Detección de intención** | Clasifica mensajes: compra, recomendación, queja, objeción de precio, saludo |
| 📊 **Analytics** | Dashboard con ventas, pedidos por estado, productos top y revenue |
| 👨‍💼 **Control humano** | Activar/desactivar el bot por conversación para intervención manual |

---

## 🏗️ Arquitectura

```mermaid
graph TB
    subgraph Cliente["📱 Cliente (WhatsApp)"]
        WA[WhatsApp App]
    end

    subgraph Bot["🟢 Servicio WhatsApp (Node.js)"]
        WW[whatsapp-web.js]
        QR[QR Auth / Session]
    end

    subgraph API["🐍 Backend (FastAPI - Python)"]
        PM[POST /api/process-message]
        CMD[Detector de Comandos]
        INT[Detector de Intención]
        AI[Generador IA]
        CART[Gestor de Carrito]
        ORD[Gestor de Pedidos]
    end

    subgraph IA["🤖 IA Local (Ollama)"]
        PHI[phi3:mini]
    end

    subgraph DB["🗄️ Base de Datos (SQLite)"]
        P[(Products)]
        C[(Conversations)]
        M[(Messages)]
        CI[(CartItems)]
        O[(Orders)]
        OI[(OrderItems)]
    end

    WA -->|Mensaje entrante| WW
    WW -->|POST JSON| PM
    PM --> CMD
    CMD -->|Comando detectado| CART
    CMD -->|Comando detectado| ORD
    CMD -->|Sin comando| INT
    INT -->|FAQ / saludo / queja| AI
    AI -->|Consulta| PHI
    PHI -->|Respuesta generada| AI
    AI -->|Respuesta| PM
    CART --> DB
    ORD --> DB
    PM --> DB
    PM -->|Respuesta JSON| WW
    WW -->|Envía mensaje| WA
```

---

## 🔗 Flujo de un mensaje

```mermaid
sequenceDiagram
    participant C as 📱 Cliente
    participant B as 🟢 Bot Node.js
    participant A as 🐍 FastAPI
    participant DB as 🗄️ SQLite
    participant AI as 🤖 Ollama

    C->>B: "Hola, quiero algo para mis zapatillas"
    B->>A: POST /api/process-message
    A->>DB: Buscar/crear conversación
    A->>A: detect_command() → null
    A->>A: detect_intent() → recommendation
    A->>DB: Obtener productos en stock
    A->>AI: Sistema prompt + historial + productos
    AI-->>A: "Para zapatillas blancas te va perfecto el Limpiador Espuma..."
    A->>DB: Guardar mensaje + respuesta
    A-->>B: { reply: "...", bot_enabled: true }
    B-->>C: Envía respuesta por WhatsApp
```

---

## 🗄️ Modelo de datos

```mermaid
erDiagram
    Product {
        int id PK
        string name
        text description
        int price
        int stock
        string image_url
        datetime created_at
    }
    Conversation {
        int id PK
        string phone
        string customer_name
        bool bot_enabled
        datetime last_message_at
    }
    Message {
        int id PK
        int conversation_id FK
        text content
        bool from_customer
        datetime created_at
    }
    CartItem {
        int id PK
        int conversation_id FK
        int product_id FK
        int quantity
        datetime created_at
    }
    Order {
        int id PK
        int conversation_id FK
        string phone
        int total
        string status
        text notes
        datetime created_at
        datetime updated_at
    }
    OrderItem {
        int id PK
        int order_id FK
        int product_id FK
        string product_name
        int product_price
        int quantity
    }

    Conversation ||--o{ Message : "tiene"
    Conversation ||--o{ CartItem : "tiene"
    Conversation ||--o{ Order : "tiene"
    Order ||--o{ OrderItem : "contiene"
    Product ||--o{ CartItem : "referenciado por"
    Product ||--o{ OrderItem : "referenciado por"
```

---

## 📁 Estructura del proyecto

```
instantvende-mvp/
├── backend/                    # API FastAPI (Python)
│   ├── main.py                 # Endpoints, lógica de bot, IA
│   ├── database.py             # Modelos SQLAlchemy (SQLite)
│   └── requirements.txt        # Dependencias Python
│
├── whatsapp/                   # Cliente WhatsApp (Node.js)
│   ├── whatsapp_client.js      # Conexión WhatsApp Web + envío de mensajes
│   └── package.json            # Dependencias Node.js
│
└── README.md
```

---

## 🔒 Configuración de Seguridad (Fase 1)

### Variables de entorno

Antes de ejecutar el proyecto, crea los archivos `.env` copiando los templates:

```bash
# Backend
cp backend/.env.example backend/.env

# WhatsApp client
cp whatsapp/.env.example whatsapp/.env
```

### Generar API Key segura

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

Copia el valor generado en:
- `backend/.env` → `API_SECRET_KEY=<valor>`
- `whatsapp/.env` → `BACKEND_API_KEY=<valor>` (debe ser el mismo)

### Nuevas características de seguridad

| Característica | Descripción |
|----------------|-------------|
| 🔑 **API Keys** | Todos los endpoints críticos requieren `X-API-Key` en el header |
| 📋 **Logging JSON** | Logs estructurados en `logs/app.log` y `logs/errors.log` con rotación automática |
| 💾 **Backups automáticos** | La BD se respalda cada 6 horas en `backups/` (configurable) |
| ⚙️ **Config centralizada** | Todas las variables en `.env` — nunca hardcodeadas en el código |
| 🛡️ **Validaciones** | Stock y precio validados en BD + Pydantic en endpoints |
| 🚨 **Manejo de errores** | Excepciones personalizadas con respuestas HTTP claras |

---



### Prerequisitos

- Python 3.10+
- Node.js 18+
- [Ollama](https://ollama.com) instalado y corriendo

### 1. Instalar Ollama y el modelo de IA

```bash
# Instalar Ollama (Mac/Linux)
curl -fsSL https://ollama.com/install.sh | sh

# Descargar el modelo (≈2GB)
ollama pull phi3:mini
```

### 2. Backend (FastAPI)

```bash
cd backend

# Crear entorno virtual
python -m venv venv

# Activar (Windows)
venv\Scripts\activate
# Activar (Mac/Linux)
source venv/bin/activate

# Instalar dependencias
pip install -r requirements.txt

# Iniciar servidor
python main.py
# → API disponible en http://localhost:8000
# → Documentación en http://localhost:8000/docs
```

### 3. Bot de WhatsApp (Node.js)

```bash
cd whatsapp

# Instalar dependencias
npm install

# Iniciar el bot
node whatsapp_client.js
```

Al iniciar por primera vez, aparece un **código QR** en la terminal. Escanéalo con WhatsApp:
> WhatsApp → Configuración → Dispositivos vinculados → Vincular dispositivo

---

## 🤖 Comandos del bot

Los clientes pueden escribir estos comandos en el chat:

| Comando | Acción |
|---------|--------|
| `#catalogo` | Ver todos los productos disponibles |
| `agregar [N]` | Agregar el producto N al carrito |
| `#carrito` | Ver productos en el carrito |
| `#pedido` | Confirmar y crear el pedido |
| `#limpiar` | Vaciar el carrito |
| `#estado` | Ver estado del último pedido |
| `#ayuda` | Ver lista de comandos |

---

## 📡 API Endpoints

### Productos
| Método | Ruta | Descripción |
|--------|------|-------------|
| `GET` | `/api/products` | Listar productos |
| `POST` | `/api/products` | Crear producto |

### Mensajes y Conversaciones
| Método | Ruta | Descripción |
|--------|------|-------------|
| `POST` | `/api/process-message` | Procesar mensaje entrante de WhatsApp |
| `GET` | `/api/conversations` | Listar todas las conversaciones |
| `GET` | `/api/conversations/{id}/messages` | Mensajes de una conversación |
| `PATCH` | `/api/conversations/{id}/toggle-bot` | Activar/desactivar bot |

### Carrito
| Método | Ruta | Descripción |
|--------|------|-------------|
| `POST` | `/api/cart/{phone}/add` | Agregar item al carrito |
| `GET` | `/api/cart/{phone}` | Ver carrito de un cliente |
| `DELETE` | `/api/cart/{phone}` | Vaciar carrito |

### Pedidos
| Método | Ruta | Descripción |
|--------|------|-------------|
| `GET` | `/api/orders` | Listar pedidos (filtrar por `?status=`) |
| `GET` | `/api/orders/{id}` | Detalle de un pedido |
| `PATCH` | `/api/orders/{id}/status` | Actualizar estado del pedido |

### Analytics y Sistema
| Método | Ruta | Descripción |
|--------|------|-------------|
| `GET` | `/api/analytics` | Dashboard de métricas |
| `GET` | `/api/health/ollama` | Estado del modelo IA |
| `GET` | `/` | Health check general |

---

## 🧠 Stack tecnológico

| Tecnología | Uso | Versión |
|------------|-----|---------|
| **FastAPI** | Framework API REST | 0.135.2 |
| **SQLAlchemy** | ORM base de datos | 2.0.48 |
| **SQLite** | Base de datos local | Built-in |
| **Pydantic** | Validación de datos | 2.12.5 |
| **Ollama** | Cliente IA local | 0.6.1 |
| **phi3:mini** | Modelo de lenguaje | Microsoft |
| **whatsapp-web.js** | Interfaz WhatsApp | 1.34.6 |
| **Node.js** | Runtime WhatsApp | 18+ |
| **Uvicorn** | Servidor ASGI | 0.42.0 |

---

## 🔧 Configuración

Las constantes del bot se configuran directamente en los archivos:

**`whatsapp/whatsapp_client.js`**
```javascript
const BACKEND_URL = 'http://localhost:8000';  // URL del backend
const BUSINESS_NAME = 'InstantVende';
```

**`backend/main.py`**
```python
# FAQ_RESPONSES → textos de respuestas automáticas
# BOT_COMMANDS  → comandos del bot y sus triggers
# modelo Ollama: 'phi3:mini' (cambiar para usar otro modelo)
```

---

## 📊 Estados de Pedido

```
pending → confirmed → shipped → delivered
                              ↘
                           cancelled (restaura stock automáticamente)
```

---

## � Producción con PM2 (auto-restart)

PM2 mantiene ambos servicios corriendo 24/7 y los reinicia automáticamente si se caen.

### Instalación

```bash
npm install -g pm2
```

### Iniciar todo con un comando

```bat
# Windows
start.bat

# Mac/Linux
pm2 start ecosystem.config.js
```

### Comandos útiles

```bash
pm2 status                     # Estado de los servicios
pm2 logs                       # Logs en tiempo real (ambos)
pm2 logs instantvende-api      # Solo logs del backend
pm2 logs instantvende-wa       # Solo logs de WhatsApp
pm2 restart instantvende-api   # Reiniciar backend
pm2 restart instantvende-wa    # Reiniciar WhatsApp
pm2 stop all                   # Detener todo
pm2 delete all                 # Quitar de PM2
```

### Auto-arranque al reiniciar el servidor

```bash
pm2 startup       # Genera el comando según tu OS (ejecutar el comando que muestra)
pm2 save          # Guarda el estado actual para que arranque automático
```

### Comportamiento ante fallos

| Evento | Respuesta |
|--------|-----------|
| Backend cuelgue/crash | PM2 reinicia el proceso automáticamente |
| WhatsApp client cae | PM2 reinicia (espera 5s para evitar loop) |
| Timeout de Ollama (45s) | El bot responde con mensaje de fallback, sin reinicio |
| Backend no responde (ECONNREFUSED) | WhatsApp client envía mensaje de error al cliente |
| Backend usa >500MB RAM | PM2 reinicia el proceso para liberar memoria |

Los logs se guardan en `./logs/` con timestamp.

---

## �📝 Licencia

MIT — Libre para uso personal y comercial.
