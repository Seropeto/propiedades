"""
master_db.py — Base de datos maestra de Toxiro Digital
Gestiona clientes, suscripciones, conteo de listados y admins.
"""
import sqlite3
import os
import hashlib
import secrets
from datetime import datetime, date

MASTER_DB_PATH = "/data/db/toxiro_master.db"
os.makedirs("/data/db", exist_ok=True)


def get_master_db():
    conn = sqlite3.connect(MASTER_DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_master_db():
    with get_master_db() as conn:

        # ── ADMINS ────────────────────────────────────────────────────────────
        conn.execute("""
            CREATE TABLE IF NOT EXISTS admins (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre          TEXT NOT NULL,
                email           TEXT UNIQUE NOT NULL,
                password_hash   TEXT NOT NULL,
                rol             TEXT DEFAULT 'admin',
                activo          INTEGER DEFAULT 1,
                creado_en       DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # ── CLIENTES ──────────────────────────────────────────────────────────
        conn.execute("""
            CREATE TABLE IF NOT EXISTS clientes (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                slug            TEXT UNIQUE NOT NULL,
                nombre_corredora TEXT NOT NULL,
                razon_social    TEXT,
                email_contacto  TEXT NOT NULL,
                telefono_contacto TEXT,
                activo          INTEGER DEFAULT 1,
                creado_en       DATETIME DEFAULT CURRENT_TIMESTAMP,
                creado_por      INTEGER REFERENCES admins(id)
            )
        """)

        # ── CONFIGURACIÓN CLIENTE ─────────────────────────────────────────────
        conn.execute("""
            CREATE TABLE IF NOT EXISTS configuracion_cliente (
                cliente_id          INTEGER PRIMARY KEY REFERENCES clientes(id),
                logo_url            TEXT,
                color_primario      TEXT DEFAULT '#0B1929',
                color_secundario    TEXT DEFAULT '#C9A84C',
                cuenta_instagram    TEXT,
                uploadpost_api_key  TEXT,
                subdominio          TEXT UNIQUE,
                nombre_display      TEXT,
                openai_api_key      TEXT,
                actualizado_en      DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # ── SUSCRIPCIONES ────────────────────────────────────────────────────
        conn.execute("""
            CREATE TABLE IF NOT EXISTS suscripciones (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                cliente_id          INTEGER NOT NULL REFERENCES clientes(id),
                tipo_plan           TEXT NOT NULL,
                listados_incluidos  INTEGER NOT NULL,
                precio_usd          REAL,
                fecha_inicio        DATE NOT NULL,
                fecha_fin           DATE,
                estado              TEXT DEFAULT 'activa',
                creado_en           DATETIME DEFAULT CURRENT_TIMESTAMP,
                notas               TEXT
            )
        """)

        # ── CONTEO DE LISTADOS ────────────────────────────────────────────────
        conn.execute("""
            CREATE TABLE IF NOT EXISTS conteo_listados (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                cliente_id          INTEGER NOT NULL REFERENCES clientes(id),
                periodo             TEXT NOT NULL,
                listados_generados  INTEGER DEFAULT 0,
                listados_limite     INTEGER NOT NULL,
                bloqueado           INTEGER DEFAULT 0,
                UNIQUE(cliente_id, periodo)
            )
        """)

        # ── LISTADOS ADICIONALES (TOP-UPS) ────────────────────────────────────
        conn.execute("""
            CREATE TABLE IF NOT EXISTS listados_adicionales (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                cliente_id          INTEGER NOT NULL REFERENCES clientes(id),
                periodo             TEXT NOT NULL,
                cantidad            INTEGER NOT NULL,
                precio_usd          REAL,
                metodo_pago         TEXT,
                referencia_pago     TEXT,
                aprobado_por        INTEGER REFERENCES admins(id),
                creado_en           DATETIME DEFAULT CURRENT_TIMESTAMP,
                notas               TEXT
            )
        """)

        # ── LOG DE ACTIVIDAD ──────────────────────────────────────────────────
        conn.execute("""
            CREATE TABLE IF NOT EXISTS log_actividad (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                cliente_id          INTEGER REFERENCES clientes(id),
                admin_id            INTEGER REFERENCES admins(id),
                accion              TEXT NOT NULL,
                session_id_prop     TEXT,
                detalles            TEXT,
                creado_en           DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        conn.commit()


# ── HELPERS ───────────────────────────────────────────────────────────────────

def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    h = hashlib.sha256(f"{salt}{password}".encode()).hexdigest()
    return f"{salt}:{h}"


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        salt, h = stored_hash.split(":", 1)
        return hashlib.sha256(f"{salt}{password}".encode()).hexdigest() == h
    except Exception:
        return False


def get_periodo_actual() -> str:
    """Retorna el periodo actual en formato YYYY-MM (ej: '2026-03')"""
    return date.today().strftime("%Y-%m")


# ── CLIENTES ──────────────────────────────────────────────────────────────────

def crear_cliente(slug: str, nombre_corredora: str, email_contacto: str,
                  telefono: str = None, razon_social: str = None,
                  creado_por: int = None) -> int:
    """Crea un cliente y su configuración por defecto. Retorna el cliente_id."""
    with get_master_db() as conn:
        cur = conn.execute("""
            INSERT INTO clientes (slug, nombre_corredora, razon_social, email_contacto,
                                  telefono_contacto, creado_por)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (slug, nombre_corredora, razon_social, email_contacto, telefono, creado_por))
        cliente_id = cur.lastrowid

        conn.execute("""
            INSERT INTO configuracion_cliente (cliente_id, subdominio, nombre_display)
            VALUES (?, ?, ?)
        """, (cliente_id, slug, nombre_corredora))

        conn.commit()

    # Crear DB propia del cliente
    _init_cliente_db(slug)
    return cliente_id


def _init_cliente_db(slug: str):
    """Crea la base de datos SQLite propia del cliente."""
    db_path = f"/data/db/{slug}.db"
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS propiedades (
            session_id          TEXT PRIMARY KEY,
            creado_en           TEXT,
            tipo_propiedad      TEXT,
            operacion           TEXT,
            direccion           TEXT,
            ciudad              TEXT,
            estado              TEXT,
            precio              TEXT,
            recamaras           TEXT,
            banos               TEXT,
            metros_construidos  TEXT,
            metros_terreno      TEXT,
            estacionamientos    TEXT,
            amenidades          TEXT,
            descripcion_agente  TEXT,
            nombre_agente       TEXT,
            telefono_agente     TEXT,
            email_agente        TEXT,
            estado_publicacion  TEXT DEFAULT 'Activa'
        )
    """)
    conn.commit()
    conn.close()


def get_cliente_db(slug: str):
    """Retorna una conexión a la DB del cliente identificado por su slug."""
    db_path = f"/data/db/{slug}.db"
    if not os.path.exists(db_path):
        raise FileNotFoundError(f"DB del cliente '{slug}' no encontrada.")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def get_cliente_por_slug(slug: str):
    """Retorna el cliente + su configuración, o None si no existe/está inactivo."""
    with get_master_db() as conn:
        row = conn.execute("""
            SELECT c.*, cc.logo_url, cc.color_primario, cc.color_secundario,
                   cc.cuenta_instagram, cc.uploadpost_api_key, cc.subdominio,
                   cc.nombre_display, cc.openai_api_key
            FROM clientes c
            LEFT JOIN configuracion_cliente cc ON cc.cliente_id = c.id
            WHERE c.slug = ? AND c.activo = 1
        """, (slug,)).fetchone()
    return row


# ── SUSCRIPCIONES ─────────────────────────────────────────────────────────────

PLANES = {
    "basico":       {"listados": 20,  "precio": 29.0},
    "profesional":  {"listados": 60,  "precio": 49.0},
    "agencia":      {"listados": 9999,"precio": 89.0},
}

def crear_suscripcion(cliente_id: int, tipo_plan: str,
                      fecha_inicio: str = None, notas: str = None) -> int:
    plan = PLANES.get(tipo_plan)
    if not plan:
        raise ValueError(f"Plan desconocido: {tipo_plan}")
    if not fecha_inicio:
        fecha_inicio = date.today().isoformat()
    with get_master_db() as conn:
        # Desactivar suscripciones anteriores
        conn.execute("""
            UPDATE suscripciones SET estado = 'cancelada'
            WHERE cliente_id = ? AND estado = 'activa'
        """, (cliente_id,))
        cur = conn.execute("""
            INSERT INTO suscripciones (cliente_id, tipo_plan, listados_incluidos,
                                       precio_usd, fecha_inicio, estado, notas)
            VALUES (?, ?, ?, ?, ?, 'activa', ?)
        """, (cliente_id, tipo_plan, plan["listados"], plan["precio"],
              fecha_inicio, notas))
        conn.commit()
        return cur.lastrowid


# ── CONTEO Y BLOQUEO ──────────────────────────────────────────────────────────

def get_o_crear_conteo(cliente_id: int, periodo: str = None):
    """Obtiene o crea el registro de conteo del periodo actual."""
    if not periodo:
        periodo = get_periodo_actual()
    with get_master_db() as conn:
        row = conn.execute("""
            SELECT * FROM conteo_listados
            WHERE cliente_id = ? AND periodo = ?
        """, (cliente_id, periodo)).fetchone()

        if not row:
            # Obtener límite del plan activo
            sub = conn.execute("""
                SELECT listados_incluidos FROM suscripciones
                WHERE cliente_id = ? AND estado = 'activa'
                ORDER BY creado_en DESC LIMIT 1
            """, (cliente_id,)).fetchone()
            limite = sub["listados_incluidos"] if sub else 20

            conn.execute("""
                INSERT INTO conteo_listados (cliente_id, periodo, listados_generados,
                                             listados_limite, bloqueado)
                VALUES (?, ?, 0, ?, 0)
            """, (cliente_id, periodo, limite))
            conn.commit()
            row = conn.execute("""
                SELECT * FROM conteo_listados
                WHERE cliente_id = ? AND periodo = ?
            """, (cliente_id, periodo)).fetchone()
    return row


def puede_generar(cliente_id: int) -> dict:
    """
    Verifica si el cliente puede generar un listado.
    Retorna: {"puede": bool, "generados": int, "limite": int, "porcentaje": int, "bloqueado": bool}
    """
    conteo = get_o_crear_conteo(cliente_id)
    generados = conteo["listados_generados"]
    limite = conteo["listados_limite"]
    bloqueado = bool(conteo["bloqueado"])
    porcentaje = int((generados / limite) * 100) if limite > 0 else 0

    return {
        "puede": not bloqueado and generados < limite,
        "generados": generados,
        "limite": limite,
        "porcentaje": porcentaje,
        "bloqueado": bloqueado,
    }


def registrar_listado_generado(cliente_id: int):
    """Incrementa el contador y bloquea si alcanza el límite."""
    periodo = get_periodo_actual()
    conteo = get_o_crear_conteo(cliente_id, periodo)
    nuevos = conteo["listados_generados"] + 1
    bloqueado = 1 if nuevos >= conteo["listados_limite"] else 0

    with get_master_db() as conn:
        conn.execute("""
            UPDATE conteo_listados
            SET listados_generados = ?, bloqueado = ?
            WHERE cliente_id = ? AND periodo = ?
        """, (nuevos, bloqueado, cliente_id, periodo))
        conn.commit()

    return nuevos, bloqueado


def aprobar_topup(cliente_id: int, cantidad: int, precio_usd: float,
                  metodo_pago: str, referencia: str, admin_id: int,
                  notas: str = None):
    """Aprueba una compra de listados adicionales y actualiza el límite."""
    periodo = get_periodo_actual()
    with get_master_db() as conn:
        conn.execute("""
            INSERT INTO listados_adicionales
            (cliente_id, periodo, cantidad, precio_usd, metodo_pago,
             referencia_pago, aprobado_por, notas)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (cliente_id, periodo, cantidad, precio_usd, metodo_pago,
              referencia, admin_id, notas))

        conn.execute("""
            UPDATE conteo_listados
            SET listados_limite = listados_limite + ?,
                bloqueado = 0
            WHERE cliente_id = ? AND periodo = ?
        """, (cantidad, cliente_id, periodo))
        conn.commit()


# ── LOG ───────────────────────────────────────────────────────────────────────

def log(cliente_id: int = None, admin_id: int = None,
        accion: str = "", session_id_prop: str = None, detalles: str = None):
    with get_master_db() as conn:
        conn.execute("""
            INSERT INTO log_actividad
            (cliente_id, admin_id, accion, session_id_prop, detalles)
            VALUES (?, ?, ?, ?, ?)
        """, (cliente_id, admin_id, accion, session_id_prop, detalles))
        conn.commit()


# ── ADMINS ────────────────────────────────────────────────────────────────────

def crear_admin(nombre: str, email: str, password: str, rol: str = "admin") -> int:
    with get_master_db() as conn:
        cur = conn.execute("""
            INSERT INTO admins (nombre, email, password_hash, rol)
            VALUES (?, ?, ?, ?)
        """, (nombre, email, hash_password(password), rol))
        conn.commit()
        return cur.lastrowid


def autenticar_admin(email: str, password: str):
    with get_master_db() as conn:
        row = conn.execute("""
            SELECT * FROM admins WHERE email = ? AND activo = 1
        """, (email,)).fetchone()
    if row and verify_password(password, row["password_hash"]):
        return row
    return None


# Inicializar la DB maestra al importar
init_master_db()
