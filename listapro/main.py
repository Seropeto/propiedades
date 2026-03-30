from fastapi import FastAPI, File, UploadFile, Form
import asyncio
from functools import partial
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from openai import OpenAI
from typing import List, Optional
from PIL import Image as PILImage, ImageDraw, ImageFilter, ImageFont
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle, HRFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT
import os
import uuid
import shutil
import httpx
import sqlite3
from datetime import datetime

load_dotenv()

# ── Base de datos ──────────────────────────────────────────────────────────────
DB_PATH = "/data/db/listapro.db"
os.makedirs("/data/db", exist_ok=True)

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db() as conn:
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
        # Migración: agregar columna si la BD ya existía sin ella
        try:
            conn.execute("ALTER TABLE propiedades ADD COLUMN estado_publicacion TEXT DEFAULT 'Activa'")
        except Exception:
            pass  # ya existe
        conn.commit()

init_db()
# ──────────────────────────────────────────────────────────────────────────────

app = FastAPI(title="ToxiroPropiedades - Generador de Propiedades")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")
app.mount("/generated", StaticFiles(directory="generated"), name="generated")

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

AMENIDADES_LABELS = {
    "alberca": "Piscina",
    "jardin": "Jardín",
    "seguridad": "Seguridad 24h",
    "gimnasio": "Gimnasio",
    "estacionamiento_visitas": "Estacionamiento para visitas",
    "area_juegos": "Área de juegos",
    "salon_eventos": "Salón de eventos",
    "roof_garden": "Terraza",
    "bodega": "Bodega",
    "elevador": "Elevador",
}


@app.get("/", response_class=HTMLResponse)
async def index():
    with open("static/index.html", encoding="utf-8") as f:
        return f.read()


@app.get("/resultados", response_class=HTMLResponse)
async def resultados():
    with open("static/results.html", encoding="utf-8") as f:
        return f.read()


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard():
    with open("static/dashboard.html", encoding="utf-8") as f:
        return f.read()


@app.get("/api/propiedades")
async def listar_propiedades(q: Optional[str] = None):
    with get_db() as conn:
        if q and q.strip():
            term = f"%{q.strip()}%"
            rows = conn.execute("""
                SELECT session_id, creado_en, tipo_propiedad, operacion,
                       direccion, ciudad, estado, precio,
                       COALESCE(estado_publicacion, 'Activa') AS estado_publicacion
                FROM propiedades
                WHERE tipo_propiedad LIKE ? OR operacion LIKE ? OR direccion LIKE ?
                   OR ciudad LIKE ? OR estado LIKE ? OR precio LIKE ?
                   OR nombre_agente LIKE ?
                ORDER BY creado_en DESC
            """, (term, term, term, term, term, term, term)).fetchall()
        else:
            rows = conn.execute("""
                SELECT session_id, creado_en, tipo_propiedad, operacion,
                       direccion, ciudad, estado, precio,
                       COALESCE(estado_publicacion, 'Activa') AS estado_publicacion
                FROM propiedades ORDER BY creado_en DESC
            """).fetchall()
    return JSONResponse([dict(r) for r in rows])


@app.get("/api/propiedades/{session_id}")
async def obtener_propiedad(session_id: str):
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM propiedades WHERE session_id = ?", (session_id,)
        ).fetchone()
    if not row:
        return JSONResponse({"error": "No encontrada"}, status_code=404)
    return JSONResponse(dict(row))


@app.get("/api/propiedades/{session_id}/fotos")
async def obtener_fotos(session_id: str):
    uploads_dir = f"uploads/{session_id}"
    if not os.path.exists(uploads_dir):
        return JSONResponse([])
    extras = sorted([
        f"/{uploads_dir}/{f}"
        for f in os.listdir(uploads_dir)
        if f.startswith("extra_")
    ])
    return JSONResponse(extras)


@app.patch("/api/propiedades/{session_id}/estado")
async def cambiar_estado(session_id: str, estado_publicacion: str = Form(...)):
    estados_validos = {"Activa", "Cerrada", "Retirada"}
    if estado_publicacion not in estados_validos:
        return JSONResponse({"error": "Estado inválido"}, status_code=400)
    with get_db() as conn:
        conn.execute(
            "UPDATE propiedades SET estado_publicacion=? WHERE session_id=?",
            (estado_publicacion, session_id)
        )
        conn.commit()
    return JSONResponse({"ok": True})


@app.put("/api/propiedades/{session_id}")
async def actualizar_propiedad(
    session_id: str,
    tipo_propiedad: str = Form(...),
    operacion: str = Form(...),
    direccion: str = Form(...),
    ciudad: str = Form(...),
    estado: str = Form(...),
    precio: str = Form(...),
    recamaras: Optional[str] = Form(None),
    banos: Optional[str] = Form(None),
    metros_construidos: Optional[str] = Form(None),
    metros_terreno: Optional[str] = Form(None),
    estacionamientos: Optional[str] = Form(None),
    amenidades: List[str] = Form(default=[]),
    descripcion_agente: str = Form(...),
    nombre_agente: str = Form(...),
    telefono_agente: str = Form(...),
    email_agente: str = Form(...),
    foto_portada: Optional[UploadFile] = File(None),
    fotos_extra: List[UploadFile] = File(default=[]),
):
    # Actualizar fotos si se subieron nuevas
    fotos_dir = f"uploads/{session_id}"
    os.makedirs(fotos_dir, exist_ok=True)

    if foto_portada and foto_portada.filename:
        portada_ext = foto_portada.filename.split(".")[-1]
        # Eliminar portada anterior
        for ext in ["jpg", "jpeg", "png", "webp"]:
            old = f"{fotos_dir}/portada.{ext}"
            if os.path.exists(old):
                os.remove(old)
        with open(f"{fotos_dir}/portada.{portada_ext}", "wb") as f:
            shutil.copyfileobj(foto_portada.file, f)

    valid_extras = [f for f in fotos_extra if f and f.filename]
    if valid_extras:
        for fname in os.listdir(fotos_dir):
            if fname.startswith("extra_"):
                os.remove(f"{fotos_dir}/{fname}")
        for i, foto in enumerate(valid_extras[:7]):
            ext = foto.filename.split(".")[-1]
            with open(f"{fotos_dir}/extra_{i}.{ext}", "wb") as f:
                shutil.copyfileobj(foto.file, f)

    # Construir amenidades
    amenidades_texto = ", ".join(
        AMENIDADES_LABELS.get(a, a) for a in amenidades if a
    )

    datos = {
        "tipo": tipo_propiedad, "operacion": operacion,
        "direccion": direccion, "ciudad": ciudad, "estado": estado,
        "precio": precio,
        "recamaras": recamaras or "N/A", "banos": banos or "N/A",
        "metros_construidos": metros_construidos or "N/A",
        "metros_terreno": metros_terreno or "N/A",
        "estacionamientos": estacionamientos or "N/A",
        "amenidades": amenidades_texto or "Sin amenidades especificadas",
        "descripcion_agente": descripcion_agente,
    }

    descripcion = await generar_descripcion(datos)
    copy_instagram = await generar_copy_instagram(datos)

    # Actualizar BD
    with get_db() as conn:
        conn.execute("""
            UPDATE propiedades SET
                tipo_propiedad=?, operacion=?, direccion=?, ciudad=?, estado=?,
                precio=?, recamaras=?, banos=?, metros_construidos=?,
                metros_terreno=?, estacionamientos=?, amenidades=?,
                descripcion_agente=?, nombre_agente=?, telefono_agente=?, email_agente=?
            WHERE session_id=?
        """, (
            tipo_propiedad, operacion, direccion, ciudad, estado, precio,
            recamaras or "", banos or "", metros_construidos or "",
            metros_terreno or "", estacionamientos or "",
            ",".join(amenidades) if amenidades else "",
            descripcion_agente, nombre_agente, telefono_agente, email_agente,
            session_id,
        ))
        conn.commit()

    # Reconstruir URLs de fotos
    portada_url = ""
    for ext in ["jpg", "jpeg", "png", "webp"]:
        p = f"{fotos_dir}/portada.{ext}"
        if os.path.exists(p):
            portada_url = f"/{p}"
            break

    extras_urls = [
        f"/{fotos_dir}/{fname}"
        for fname in sorted(os.listdir(fotos_dir))
        if fname.startswith("extra_")
    ]

    return JSONResponse({
        "session_id": session_id,
        "portada_url": portada_url,
        "extras_urls": extras_urls,
        "descripcion": descripcion,
        "copy_instagram": copy_instagram,
        "datos": {
            "tipo_propiedad": tipo_propiedad, "operacion": operacion,
            "direccion": direccion, "ciudad": ciudad, "estado": estado,
            "precio": precio, "recamaras": recamaras, "banos": banos,
            "metros_construidos": metros_construidos,
            "metros_terreno": metros_terreno,
            "estacionamientos": estacionamientos,
            "amenidades": amenidades_texto,
            "nombre_agente": nombre_agente,
            "telefono_agente": telefono_agente,
            "email_agente": email_agente,
        }
    })


@app.post("/api/generar")
async def generar_listado(
    tipo_propiedad: str = Form(...),
    operacion: str = Form(...),
    direccion: str = Form(...),
    ciudad: str = Form(...),
    estado: str = Form(...),
    precio: str = Form(...),
    recamaras: Optional[str] = Form(None),
    banos: Optional[str] = Form(None),
    metros_construidos: Optional[str] = Form(None),
    metros_terreno: Optional[str] = Form(None),
    estacionamientos: Optional[str] = Form(None),
    amenidades: List[str] = Form(default=[]),
    descripcion_agente: str = Form(...),
    nombre_agente: str = Form(...),
    telefono_agente: str = Form(...),
    email_agente: str = Form(...),
    foto_portada: UploadFile = File(...),
    fotos_extra: List[UploadFile] = File(default=[]),
):
    # Guardar fotos
    session_id = str(uuid.uuid4())[:8]
    fotos_dir = f"uploads/{session_id}"
    os.makedirs(fotos_dir, exist_ok=True)

    portada_ext = foto_portada.filename.split(".")[-1]
    portada_path = f"{fotos_dir}/portada.{portada_ext}"
    with open(portada_path, "wb") as f:
        shutil.copyfileobj(foto_portada.file, f)

    extras_paths = []
    for i, foto in enumerate(fotos_extra[:7]):  # máx 7 fotos adicionales
        if foto.filename:
            ext = foto.filename.split(".")[-1]
            path = f"{fotos_dir}/extra_{i}.{ext}"
            with open(path, "wb") as f:
                shutil.copyfileobj(foto.file, f)
            extras_paths.append(path)

    # Construir amenidades legibles
    amenidades_texto = ", ".join(
        AMENIDADES_LABELS.get(a, a) for a in amenidades if a
    )

    # Construir datos para el prompt
    datos = {
        "tipo": tipo_propiedad,
        "operacion": operacion,
        "direccion": direccion,
        "ciudad": ciudad,
        "estado": estado,
        "precio": precio,
        "recamaras": recamaras or "N/A",
        "banos": banos or "N/A",
        "metros_construidos": metros_construidos or "N/A",
        "metros_terreno": metros_terreno or "N/A",
        "estacionamientos": estacionamientos or "N/A",
        "amenidades": amenidades_texto or "Sin amenidades especificadas",
        "descripcion_agente": descripcion_agente,
    }

    # Generar descripción profesional
    descripcion = await generar_descripcion(datos)

    # Generar copy para Instagram
    copy_instagram = await generar_copy_instagram(datos)

    # Guardar en BD
    with get_db() as conn:
        conn.execute("""
            INSERT OR REPLACE INTO propiedades VALUES
            (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            session_id,
            datetime.now().strftime("%Y-%m-%d %H:%M"),
            tipo_propiedad, operacion, direccion, ciudad, estado, precio,
            recamaras or "", banos or "", metros_construidos or "",
            metros_terreno or "", estacionamientos or "",
            ",".join(amenidades) if amenidades else "",
            descripcion_agente, nombre_agente, telefono_agente, email_agente,
            "Activa",
        ))
        conn.commit()

    return JSONResponse({
        "session_id": session_id,
        "portada_url": f"/{portada_path}",
        "extras_urls": [f"/{p}" for p in extras_paths],
        "descripcion": descripcion,
        "copy_instagram": copy_instagram,
        "datos": {
            "tipo_propiedad": tipo_propiedad,
            "operacion": operacion,
            "direccion": direccion,
            "ciudad": ciudad,
            "estado": estado,
            "precio": precio,
            "recamaras": recamaras,
            "banos": banos,
            "metros_construidos": metros_construidos,
            "metros_terreno": metros_terreno,
            "estacionamientos": estacionamientos,
            "amenidades": amenidades_texto,
            "nombre_agente": nombre_agente,
            "telefono_agente": telefono_agente,
            "email_agente": email_agente,
        }
    })


async def generar_descripcion(datos: dict) -> str:
    prompt = f"""Eres un experto en marketing inmobiliario latinoamericano.
Genera una descripción profesional, atractiva y persuasiva para la siguiente propiedad.
La descripción debe tener entre 150-200 palabras. Escribe en español.

REGLAS OBLIGATORIAS (no las ignores):
- Usa SIEMPRE "Dormitorios", NUNCA "recámaras" ni "habitaciones"
- El precio es {datos['precio']} — inclúyelo exactamente así, SIN agregar "MXN", "pesos" ni ninguna moneda
- Las amenidades son exactamente: {datos['amenidades']} — usa esos nombres exactos, no los traduzcas ni cambies
- No menciones país ni moneda

Datos:
- Tipo: {datos['tipo']} en {datos['operacion']}
- Ubicación: {datos['direccion']}, {datos['ciudad']}, {datos['estado']}
- Precio: {datos['precio']}
- Dormitorios: {datos['recamaras']}
- Baños: {datos['banos']}
- Metros construidos: {datos['metros_construidos']} m²
- Metros de terreno: {datos['metros_terreno']} m²
- Estacionamientos: {datos['estacionamientos']}
- Amenidades: {datos['amenidades']}
- Notas del agente: {datos['descripcion_agente']}

Genera SOLO la descripción, sin títulos ni encabezados."""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
        max_tokens=400,
    )
    return response.choices[0].message.content.strip()


async def generar_copy_instagram(datos: dict) -> str:
    prompt = f"""Eres un experto en redes sociales y marketing inmobiliario latinoamericano.
Genera un copy atractivo para Instagram. Escribe en español.

REGLAS OBLIGATORIAS (no las ignores):
- Usa SIEMPRE "Dormitorios", NUNCA "recámaras" ni "habitaciones"
- El precio es {datos['precio']} — escríbelo exactamente así, SIN agregar "MXN", "pesos" ni moneda
- Las amenidades son: {datos['amenidades']} — usa esos nombres exactos
- Incluye 15 hashtags inmobiliarios genéricos (sin país específico)
- Máximo 150 palabras + hashtags
- Termina con llamado a la acción

Datos:
- Tipo: {datos['tipo']} en {datos['operacion']}
- Ubicación: {datos['ciudad']}, {datos['estado']}
- Precio: {datos['precio']}
- Dormitorios: {datos['recamaras']} | Baños: {datos['banos']}
- Metros construidos: {datos['metros_construidos']} m²
- Amenidades: {datos['amenidades']}

Genera SOLO el copy con hashtags."""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.8,
        max_tokens=400,
    )
    return response.choices[0].message.content.strip()


@app.get("/api/imagen/{session_id}")
async def descargar_imagen(session_id: str):
    img_path = f"generated/{session_id}_instagram.jpg"
    if not os.path.exists(img_path):
        return JSONResponse({"error": "Imagen no encontrada"}, status_code=404)
    return FileResponse(img_path, media_type="image/jpeg",
                        filename=f"insta_{session_id}.jpg")


@app.post("/api/generar-imagen")
async def generar_imagen_endpoint(
    session_id: str = Form(...),
    tipo_propiedad: str = Form(...),
    operacion: str = Form(...),
    ciudad: str = Form(...),
    estado: str = Form(...),
    precio: str = Form(...),
    recamaras: Optional[str] = Form(None),
    banos: Optional[str] = Form(None),
    metros_construidos: Optional[str] = Form(None),
):
    portada_dir = f"uploads/{session_id}"
    portada_path = None
    for ext in ["jpg", "jpeg", "png", "webp"]:
        candidate = f"{portada_dir}/portada.{ext}"
        if os.path.exists(candidate):
            portada_path = candidate
            break

    if not portada_path:
        return JSONResponse({"error": "No se encontró la foto de portada"}, status_code=400)

    img_path = f"generated/{session_id}_instagram.jpg"
    os.makedirs("generated", exist_ok=True)

    try:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, partial(crear_imagen_instagram,
            portada_path=portada_path,
            img_path=img_path,
            operacion=operacion,
            precio=formatear_precio(precio),
            ciudad=ciudad,
            estado=estado,
            recamaras=recamaras or "",
            banos=banos or "",
            metros=metros_construidos or "",
        ))
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JSONResponse({"error": str(e)}, status_code=500)

    return JSONResponse({"imagen_url": f"/api/imagen/{session_id}"})


def crear_imagen_instagram(portada_path, img_path, operacion, precio,
                            ciudad, estado, recamaras, banos, metros):
    SIZE = 1080

    # Cargar y recortar foto al cuadrado
    foto = PILImage.open(portada_path).convert("RGB")
    w, h = foto.size
    lado = min(w, h)
    left = (w - lado) // 2
    top = (h - lado) // 2
    foto = foto.crop((left, top, left + lado, top + lado))
    foto = foto.resize((SIZE, SIZE), PILImage.LANCZOS)

    # Gradiente oscuro de abajo hacia arriba
    gradiente = PILImage.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    draw_grad = ImageDraw.Draw(gradiente)
    for y in range(SIZE):
        alpha = int(220 * (y / SIZE) ** 0.7)
        draw_grad.line([(0, y), (SIZE, y)], fill=(0, 0, 0, alpha))

    base = foto.convert("RGBA")
    base.paste(gradiente, (0, 0), gradiente)
    canvas = base.convert("RGB")
    draw = ImageDraw.Draw(canvas)

    # Intentar cargar fuente del sistema, si no usar default
    def get_font(size):
        font_paths = [
            "C:/Windows/Fonts/arialbd.ttf",
            "C:/Windows/Fonts/arial.ttf",
            "C:/Windows/Fonts/segoeui.ttf",
        ]
        for fp in font_paths:
            try:
                return ImageFont.truetype(fp, size)
            except Exception:
                continue
        return ImageFont.load_default()

    font_badge   = get_font(32)
    font_precio  = get_font(72)
    font_ciudad  = get_font(38)
    font_datos   = get_font(34)
    font_logo    = get_font(28)

    BLANCO  = (255, 255, 255)
    AMARILLO = (255, 215, 0)
    AZUL_BADGE = (43, 108, 176)

    # Badge operación (arriba izquierda)
    badge_text = f"  En {operacion}  "
    bbox = draw.textbbox((0, 0), badge_text, font=font_badge)
    bw = bbox[2] - bbox[0] + 20
    bh = bbox[3] - bbox[1] + 14
    draw.rounded_rectangle([30, 30, 30 + bw, 30 + bh], radius=8, fill=AZUL_BADGE)
    draw.text((40, 37), badge_text.strip(), font=font_badge, fill=BLANCO)

    # Logo (arriba derecha)
    logo_text = "ToxiroPropiedades"
    lb = draw.textbbox((0, 0), logo_text, font=font_logo)
    lw = lb[2] - lb[0]
    draw.text((SIZE - lw - 30, 38), logo_text, font=font_logo, fill=(255, 255, 255, 180))

    # Precio (grande, abajo)
    precio_text = f"{precio}"
    pb = draw.textbbox((0, 0), precio_text, font=font_precio)
    pw = pb[2] - pb[0]
    draw.text(((SIZE - pw) // 2, SIZE - 310), precio_text, font=font_precio, fill=AMARILLO)

    # Ciudad
    ciudad_text = f"{ciudad}, {estado}"
    cb = draw.textbbox((0, 0), ciudad_text, font=font_ciudad)
    cw = cb[2] - cb[0]
    draw.text(((SIZE - cw) // 2, SIZE - 230), ciudad_text, font=font_ciudad, fill=BLANCO)

    # Datos (dormitorios | baños | m²)
    partes = []
    if recamaras: partes.append(f"{recamaras} Dorm.")
    if banos:     partes.append(f"{banos} Ba\u00f1os")
    if metros:    partes.append(f"{metros} m2")
    datos_text = "   |   ".join(partes)
    if datos_text:
        db = draw.textbbox((0, 0), datos_text, font=font_datos)
        dw = db[2] - db[0]
        draw.text(((SIZE - dw) // 2, SIZE - 170), datos_text, font=font_datos, fill=BLANCO)

    # Línea separadora
    draw.line([(80, SIZE - 100), (SIZE - 80, SIZE - 100)], fill=(255, 255, 255, 80), width=1)

    canvas.save(img_path, "JPEG", quality=92)


@app.get("/api/pdf/{session_id}")
async def descargar_pdf(session_id: str):
    pdf_path = f"generated/{session_id}.pdf"
    if not os.path.exists(pdf_path):
        return JSONResponse({"error": "PDF no encontrado"}, status_code=404)
    return FileResponse(pdf_path, media_type="application/pdf",
                        filename=f"propiedad_{session_id}.pdf")


@app.post("/api/generar-pdf")
async def generar_pdf_endpoint(
    session_id: str = Form(...),
    tipo_propiedad: str = Form(...),
    operacion: str = Form(...),
    direccion: str = Form(...),
    ciudad: str = Form(...),
    estado: str = Form(...),
    precio: str = Form(...),
    recamaras: Optional[str] = Form(None),
    banos: Optional[str] = Form(None),
    metros_construidos: Optional[str] = Form(None),
    metros_terreno: Optional[str] = Form(None),
    estacionamientos: Optional[str] = Form(None),
    amenidades: Optional[str] = Form(None),
    descripcion: str = Form(...),
    nombre_agente: str = Form(...),
    telefono_agente: str = Form(...),
    email_agente: str = Form(...),
):
    portada_dir = f"uploads/{session_id}"
    portada_path = None
    for ext in ["jpg", "jpeg", "png", "webp"]:
        candidate = f"{portada_dir}/portada.{ext}"
        if os.path.exists(candidate):
            portada_path = candidate
            break

    pdf_path = f"generated/{session_id}.pdf"
    os.makedirs("generated", exist_ok=True)

    try:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, partial(crear_pdf,
            pdf_path=pdf_path,
            tipo_propiedad=tipo_propiedad,
            operacion=operacion,
            direccion=direccion,
            ciudad=ciudad,
            estado=estado,
            precio=precio,
            recamaras=recamaras,
            banos=banos,
            metros_construidos=metros_construidos,
            metros_terreno=metros_terreno,
            estacionamientos=estacionamientos,
            amenidades=amenidades,
            descripcion=descripcion,
            nombre_agente=nombre_agente,
            telefono_agente=telefono_agente,
            email_agente=email_agente,
            portada_path=portada_path,
        ))
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JSONResponse({"error": str(e)}, status_code=500)

    return JSONResponse({"pdf_url": f"/api/pdf/{session_id}"})


AMENIDADES_DISPLAY = {
    "alberca": "Piscina", "Alberca": "Piscina",
    "roof_garden": "Terraza", "Roof Garden": "Terraza",
}

def normalizar_amenidades(texto):
    if not texto:
        return ""
    for k, v in AMENIDADES_DISPLAY.items():
        texto = texto.replace(k, v)
    return texto

def formatear_precio(precio):
    try:
        num = int(float(str(precio).replace(",", "").replace(".", "")))
        return f"${num:,}".replace(",", ".")
    except Exception:
        return f"${precio}"

def sanitizar(texto):
    """Elimina caracteres fuera de Latin-1 que rompen ReportLab."""
    if not texto:
        return ""
    return texto.encode("latin-1", errors="replace").decode("latin-1")


def crear_pdf(pdf_path, tipo_propiedad, operacion, direccion, ciudad, estado,
              precio, recamaras, banos, metros_construidos, metros_terreno,
              estacionamientos, amenidades, descripcion, nombre_agente,
              telefono_agente, email_agente, portada_path):

    # Sanitizar todos los textos
    tipo_propiedad = sanitizar(tipo_propiedad)
    operacion      = sanitizar(operacion)
    direccion      = sanitizar(direccion)
    ciudad         = sanitizar(ciudad)
    estado         = sanitizar(estado)
    precio         = sanitizar(precio)
    recamaras      = sanitizar(recamaras or "")
    banos          = sanitizar(banos or "")
    metros_construidos = sanitizar(metros_construidos or "")
    metros_terreno = sanitizar(metros_terreno or "")
    estacionamientos = sanitizar(estacionamientos or "")
    amenidades     = sanitizar(normalizar_amenidades(amenidades or ""))
    descripcion    = sanitizar(descripcion)
    nombre_agente  = sanitizar(nombre_agente)
    telefono_agente = sanitizar(telefono_agente)
    email_agente   = sanitizar(email_agente)

    AZUL = colors.HexColor("#1a365d")
    AZUL_CLARO = colors.HexColor("#2b6cb0")
    GRIS = colors.HexColor("#4a5568")
    GRIS_CLARO = colors.HexColor("#f7fafc")

    doc = SimpleDocTemplate(
        pdf_path,
        pagesize=A4,
        rightMargin=1.5*cm,
        leftMargin=1.5*cm,
        topMargin=1.5*cm,
        bottomMargin=1.5*cm,
    )

    styles = getSampleStyleSheet()
    style_titulo = ParagraphStyle("titulo", fontSize=20, textColor=colors.white,
                                   fontName="Helvetica-Bold", alignment=TA_CENTER,
                                   spaceAfter=4)
    style_subtitulo = ParagraphStyle("subtitulo", fontSize=11, textColor=colors.white,
                                      fontName="Helvetica", alignment=TA_CENTER)
    style_seccion = ParagraphStyle("seccion", fontSize=11, textColor=AZUL,
                                    fontName="Helvetica-Bold", spaceBefore=12, spaceAfter=6)
    style_body = ParagraphStyle("body", fontSize=10, textColor=GRIS,
                                 fontName="Helvetica", leading=16, spaceAfter=8)
    style_agente = ParagraphStyle("agente", fontSize=10, textColor=colors.white,
                                   fontName="Helvetica", alignment=TA_CENTER, leading=16)

    story = []

    # ── ENCABEZADO ──────────────────────────────────────────
    encabezado = Table(
        [[Paragraph("ToxiroPropiedades", style_titulo)],
         [Paragraph(f"{tipo_propiedad} en {operacion} · {ciudad}, {estado}", style_subtitulo)]],
        colWidths=[doc.width]
    )
    encabezado.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), AZUL),
        ("TOPPADDING", (0, 0), (-1, -1), 14),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 14),
        ("LEFTPADDING", (0, 0), (-1, -1), 12),
        ("RIGHTPADDING", (0, 0), (-1, -1), 12),
        ("ROUNDEDCORNERS", [8]),
    ]))
    story.append(encabezado)
    story.append(Spacer(1, 0.4*cm))

    # ── FOTO PORTADA ─────────────────────────────────────────
    if portada_path and os.path.exists(portada_path):
        img = Image(portada_path, width=doc.width, height=8*cm)
        img.hAlign = "CENTER"
        story.append(img)
        story.append(Spacer(1, 0.4*cm))

    # ── DATOS CLAVE ──────────────────────────────────────────
    story.append(Paragraph("Datos de la Propiedad", style_seccion))

    stats = []
    if precio:
        stats.append(["Precio", formatear_precio(precio)])
    if recamaras:
        stats.append(["Dormitorios", recamaras])
    if banos:
        stats.append(["Ba\xf1os", banos])
    if metros_construidos:
        stats.append(["M2 Construidos", f"{metros_construidos} m2"])
    if metros_terreno:
        stats.append(["M2 Terreno", f"{metros_terreno} m2"])
    if estacionamientos:
        stats.append(["Estacionamientos", estacionamientos])

    if stats:
        # Distribuir en 2 columnas
        rows = []
        for i in range(0, len(stats), 2):
            left = stats[i]
            right = stats[i+1] if i+1 < len(stats) else ["", ""]
            rows.append([
                Paragraph(f"<b>{left[0]}</b>", style_body),
                Paragraph(left[1], style_body),
                Paragraph(f"<b>{right[0]}</b>", style_body),
                Paragraph(right[1], style_body),
            ])

        tabla_stats = Table(rows, colWidths=[doc.width*0.25, doc.width*0.25,
                                              doc.width*0.25, doc.width*0.25])
        tabla_stats.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), GRIS_CLARO),
            ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.white, GRIS_CLARO]),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ]))
        story.append(tabla_stats)
        story.append(Spacer(1, 0.3*cm))

    # ── DIRECCIÓN ────────────────────────────────────────────
    story.append(Paragraph(f"Ubicacion: {direccion}, {ciudad}, {estado}", style_body))

    # ── AMENIDADES ───────────────────────────────────────────
    if amenidades:
        story.append(Paragraph("Amenidades", style_seccion))
        story.append(Paragraph(amenidades, style_body))

    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#e2e8f0"),
                              spaceAfter=8))

    # ── DESCRIPCIÓN ──────────────────────────────────────────
    story.append(Paragraph("Descripción", style_seccion))
    story.append(Paragraph(descripcion, style_body))

    story.append(Spacer(1, 0.5*cm))

    # ── CONTACTO ─────────────────────────────────────────────
    contacto = Table(
        [[Paragraph(f"<b>{nombre_agente}</b>", style_agente)],
         [Paragraph(f"📞 {telefono_agente}   ✉️ {email_agente}", style_agente)]],
        colWidths=[doc.width]
    )
    contacto.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), AZUL_CLARO),
        ("TOPPADDING", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
        ("ROUNDEDCORNERS", [6]),
    ]))
    story.append(contacto)

    doc.build(story)


@app.post("/api/publicar-instagram")
async def publicar_instagram(
    session_id: str = Form(...),
    copy_instagram: str = Form(...),
):
    UPLOADPOST_API_KEY = os.getenv("UPLOADPOST_API_KEY")
    if not UPLOADPOST_API_KEY:
        return JSONResponse({"error": "UPLOADPOST_API_KEY no configurado"}, status_code=500)

    img_path = f"generated/{session_id}_instagram.jpg"
    print(f"[PUBLICAR] session_id={session_id}, buscando={img_path}, existe={os.path.exists(img_path)}")
    if not os.path.exists(img_path):
        img_path = f"generated/{session_id}_insta.jpg"
        print(f"[PUBLICAR] fallback={img_path}, existe={os.path.exists(img_path)}")
    if not os.path.exists(img_path):
        return JSONResponse({"error": "Imagen no encontrada. Genera la imagen primero."}, status_code=404)

    UPLOADPOST_USER = os.getenv("UPLOADPOST_USER", "@barriovecino")

    try:
        with open(img_path, "rb") as f:
            img_bytes = f.read()

        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                "https://api.upload-post.com/api/upload_photos",
                headers={"Authorization": f"Apikey {UPLOADPOST_API_KEY}"},
                data={
                    "user": UPLOADPOST_USER,
                    "platform[]": "instagram",
                    "title": copy_instagram,
                },
                files={"photos[]": (f"{session_id}.jpg", img_bytes, "image/jpeg")},
            )

        if response.status_code == 200:
            return JSONResponse({"success": True, "data": response.json()})
        elif response.status_code in (401, 403):
            return JSONResponse(
                {"error": "API key de Upload Post vencida o inválida. Renuévala en upload-post.com."},
                status_code=401
            )
        else:
            return JSONResponse(
                {"error": f"Error de Upload Post ({response.status_code}): {response.text}"},
                status_code=response.status_code
            )
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.post("/api/generar-video")
async def generar_video(
    session_id: str = Form(...),
    precio: str = Form(...),
    ciudad: str = Form(...),
    estado: str = Form(...),
    operacion: str = Form(...),
    recamaras: Optional[str] = Form(None),
    banos: Optional[str] = Form(None),
    metros_construidos: Optional[str] = Form(None),
    nombre_agente: str = Form(...),
    telefono_agente: str = Form(...),
    email_agente: str = Form(...),
    music_src: Optional[str] = Form(None),
):
    import subprocess
    import json as json_mod

    # Recopilar fotos de la sesión
    uploads_dir = f"uploads/{session_id}"
    photos = []
    base_url = "http://localhost:8000"
    for ext in ["jpg", "jpeg", "png", "webp"]:
        p = f"{uploads_dir}/portada.{ext}"
        if os.path.exists(p):
            photos.append(f"{base_url}/{p}")
            break
    for fname in sorted(os.listdir(uploads_dir)) if os.path.exists(uploads_dir) else []:
        if fname.startswith("extra_"):
            photos.append(f"{base_url}/{uploads_dir}/{fname}")

    if not photos:
        return JSONResponse({"error": "No se encontraron fotos para el video."}, status_code=404)

    output_path = os.path.abspath(f"generated/{session_id}_video.mp4")
    os.makedirs("generated", exist_ok=True)

    video_dir = os.path.abspath("video")
    render_script = os.path.join(video_dir, "render.js")
    node_path = r"C:\Program Files\nodejs\node.exe"
    if not os.path.exists(node_path):
        node_path = "node"

    render_args = json_mod.dumps({
        "photos": photos,
        "precio": formatear_precio(precio),
        "ciudad": ciudad,
        "estado": estado,
        "recamaras": recamaras or "",
        "banos": banos or "",
        "metros": metros_construidos or "",
        "operacion": operacion,
        "nombre": nombre_agente,
        "telefono": telefono_agente,
        "email": email_agente,
        "musicSrc": music_src or None,
        "outputPath": output_path,
        "PHOTO_DURATION": 90,
        "CONTACT_DURATION": 90,
    })

    import subprocess as sp

    def _render():
        return sp.run(
            [node_path, render_script, render_args],
            cwd=video_dir,
            capture_output=True,
            timeout=300,
        )

    try:
        loop = asyncio.get_event_loop()
        proc_result = await loop.run_in_executor(None, _render)

        stdout_text = proc_result.stdout.decode(errors="replace").strip()
        stderr_text = proc_result.stderr.decode(errors="replace").strip()

        if proc_result.returncode != 0:
            err_detail = stderr_text[-500:] or stdout_text[-200:]
            return JSONResponse({"error": f"Error al renderizar: {err_detail}"}, status_code=500)

        if not stdout_text:
            return JSONResponse({"error": f"Sin respuesta del renderizador. stderr: {stderr_text[-300:]}"}, status_code=500)

        result = json_mod.loads(stdout_text)
        if not result.get("success"):
            return JSONResponse({"error": result.get("error", "Error desconocido")}, status_code=500)

        return JSONResponse({"video_url": f"/api/video/{session_id}"})

    except sp.TimeoutExpired:
        return JSONResponse({"error": "Timeout: el video tardó demasiado en renderizar."}, status_code=500)
    except Exception as e:
        import traceback
        print(f"[VIDEO ERROR] {type(e).__name__}: {e}\n{traceback.format_exc()}")
        return JSONResponse({"error": f"{type(e).__name__}: {str(e)}"}, status_code=500)


@app.get("/api/video/{session_id}")
async def descargar_video(session_id: str):
    video_path = f"generated/{session_id}_video.mp4"
    if not os.path.exists(video_path):
        return JSONResponse({"error": "Video no encontrado"}, status_code=404)
    return FileResponse(video_path, media_type="video/mp4", filename=f"reel_{session_id}.mp4")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
