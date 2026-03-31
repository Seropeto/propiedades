"""
admin/router.py — Panel de administración de Toxiro Digital
Acceso exclusivo para el equipo de Toxiro. Gestiona clientes, suscripciones,
conteo de listados, top-ups y métricas globales.
"""
from fastapi import APIRouter, Request, Form, Response
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
import os
import json
import secrets
from datetime import date

from master_db import (
    get_master_db, autenticar_admin, crear_cliente, crear_suscripcion,
    aprobar_topup, get_o_crear_conteo, puede_generar, PLANES,
    get_periodo_actual, hash_password, _init_cliente_db
)

router = APIRouter(prefix="/admin")

# ── Sesión simple con cookie ──────────────────────────────────────────────────
ADMIN_SESSIONS: dict = {}   # {token: admin_id}

def _get_admin_session(request: Request):
    token = request.cookies.get("toxiro_admin")
    if token and token in ADMIN_SESSIONS:
        with get_master_db() as conn:
            row = conn.execute(
                "SELECT * FROM admins WHERE id = ? AND activo = 1",
                (ADMIN_SESSIONS[token],)
            ).fetchone()
        return row
    return None

def _require_admin(request: Request):
    admin = _get_admin_session(request)
    if not admin:
        return None
    return admin


# ── LOGIN ─────────────────────────────────────────────────────────────────────

@router.get("/login", response_class=HTMLResponse)
async def admin_login_page():
    with open(os.path.join(os.path.dirname(__file__), "static/login.html"), encoding="utf-8") as f:
        return f.read()


@router.post("/login")
async def admin_login(response: Response, email: str = Form(...), password: str = Form(...)):
    from master_db import autenticar_admin
    admin = autenticar_admin(email, password)
    if not admin:
        return RedirectResponse("/admin/login?error=1", status_code=303)
    token = secrets.token_hex(32)
    ADMIN_SESSIONS[token] = admin["id"]
    resp = RedirectResponse("/admin/dashboard", status_code=303)
    resp.set_cookie("toxiro_admin", token, httponly=True, max_age=86400)
    return resp


@router.get("/logout")
async def admin_logout(request: Request):
    token = request.cookies.get("toxiro_admin")
    if token:
        ADMIN_SESSIONS.pop(token, None)
    resp = RedirectResponse("/admin/login", status_code=303)
    resp.delete_cookie("toxiro_admin")
    return resp


# ── DASHBOARD ─────────────────────────────────────────────────────────────────

@router.get("/dashboard", response_class=HTMLResponse)
async def admin_dashboard(request: Request):
    admin = _require_admin(request)
    if not admin:
        return RedirectResponse("/admin/login")
    with open(os.path.join(os.path.dirname(__file__), "static/dashboard.html"), encoding="utf-8") as f:
        return f.read()


# ── API: MÉTRICAS GLOBALES ────────────────────────────────────────────────────

@router.get("/api/metricas")
async def api_metricas(request: Request):
    admin = _require_admin(request)
    if not admin:
        return JSONResponse({"error": "no autorizado"}, status_code=401)

    periodo = get_periodo_actual()
    with get_master_db() as conn:
        total_clientes = conn.execute(
            "SELECT COUNT(*) as n FROM clientes WHERE activo=1"
        ).fetchone()["n"]

        clientes_suspendidos = conn.execute(
            "SELECT COUNT(*) as n FROM clientes WHERE activo=0"
        ).fetchone()["n"]

        total_listados_mes = conn.execute("""
            SELECT COALESCE(SUM(listados_generados),0) as n
            FROM conteo_listados WHERE periodo=?
        """, (periodo,)).fetchone()["n"]

        clientes_al_limite = conn.execute("""
            SELECT COUNT(*) as n FROM conteo_listados
            WHERE periodo=? AND bloqueado=1
        """, (periodo,)).fetchone()["n"]

        clientes_cerca = conn.execute("""
            SELECT COUNT(*) as n FROM conteo_listados
            WHERE periodo=? AND bloqueado=0
            AND CAST(listados_generados AS REAL)/listados_limite >= 0.8
        """, (periodo,)).fetchone()["n"]

        ingresos_mes = conn.execute("""
            SELECT COALESCE(SUM(precio_usd),0) as n
            FROM listados_adicionales WHERE periodo=?
        """, (periodo,)).fetchone()["n"]

    return JSONResponse({
        "periodo": periodo,
        "total_clientes": total_clientes,
        "clientes_suspendidos": clientes_suspendidos,
        "total_listados_mes": total_listados_mes,
        "clientes_al_limite": clientes_al_limite,
        "clientes_cerca_limite": clientes_cerca,
        "ingresos_topups_mes": ingresos_mes,
    })


# ── API: LISTA DE CLIENTES ────────────────────────────────────────────────────

@router.get("/api/clientes")
async def api_clientes(request: Request):
    admin = _require_admin(request)
    if not admin:
        return JSONResponse({"error": "no autorizado"}, status_code=401)

    periodo = get_periodo_actual()
    with get_master_db() as conn:
        rows = conn.execute("""
            SELECT c.id, c.slug, c.nombre_corredora, c.email_contacto,
                   c.telefono_contacto, c.activo, c.creado_en,
                   cc.subdominio, cc.cuenta_instagram, cc.nombre_display,
                   s.tipo_plan, s.listados_incluidos, s.precio_usd, s.fecha_inicio,
                   COALESCE(cl.listados_generados, 0) as listados_generados,
                   COALESCE(cl.listados_limite, s.listados_incluidos, 0) as listados_limite,
                   COALESCE(cl.bloqueado, 0) as bloqueado
            FROM clientes c
            LEFT JOIN configuracion_cliente cc ON cc.cliente_id = c.id
            LEFT JOIN suscripciones s ON s.cliente_id = c.id AND s.estado='activa'
            LEFT JOIN conteo_listados cl ON cl.cliente_id = c.id AND cl.periodo=?
            ORDER BY c.creado_en DESC
        """, (periodo,)).fetchall()

    resultado = []
    for r in rows:
        d = dict(r)
        if d["listados_limite"] and d["listados_limite"] > 0:
            d["uso_pct"] = int((d["listados_generados"] / d["listados_limite"]) * 100)
        else:
            d["uso_pct"] = 0
        resultado.append(d)

    return JSONResponse(resultado)


# ── API: CREAR CLIENTE ────────────────────────────────────────────────────────

@router.post("/api/clientes")
async def api_crear_cliente(
    request: Request,
    slug: str = Form(...),
    nombre_corredora: str = Form(...),
    email_contacto: str = Form(...),
    telefono_contacto: str = Form(None),
    razon_social: str = Form(None),
    tipo_plan: str = Form("profesional"),
    cuenta_instagram: str = Form(None),
):
    admin = _require_admin(request)
    if not admin:
        return JSONResponse({"error": "no autorizado"}, status_code=401)

    # Validar slug único
    slug = slug.lower().strip().replace(" ", "-")
    with get_master_db() as conn:
        existe = conn.execute(
            "SELECT id FROM clientes WHERE slug=?", (slug,)
        ).fetchone()
    if existe:
        return JSONResponse({"error": f"El slug '{slug}' ya está en uso"}, status_code=400)

    cliente_id = crear_cliente(
        slug=slug,
        nombre_corredora=nombre_corredora,
        email_contacto=email_contacto,
        telefono=telefono_contacto,
        razon_social=razon_social,
        creado_por=admin["id"]
    )

    # Configurar Instagram si se proporcionó
    if cuenta_instagram:
        with get_master_db() as conn:
            conn.execute("""
                UPDATE configuracion_cliente SET cuenta_instagram=?
                WHERE cliente_id=?
            """, (cuenta_instagram, cliente_id))
            conn.commit()

    # Crear suscripción
    sub_id = crear_suscripcion(
        cliente_id=cliente_id,
        tipo_plan=tipo_plan,
        creado_por=admin["id"] if hasattr(admin, "__getitem__") else None
    )

    return JSONResponse({
        "ok": True,
        "cliente_id": cliente_id,
        "slug": slug,
        "subdominio": f"{slug}.toxirodigital.cloud",
        "suscripcion_id": sub_id,
    })


# ── API: CAMBIAR PLAN ─────────────────────────────────────────────────────────

@router.post("/api/clientes/{cliente_id}/plan")
async def api_cambiar_plan(
    request: Request,
    cliente_id: int,
    tipo_plan: str = Form(...),
    notas: str = Form(None),
):
    admin = _require_admin(request)
    if not admin:
        return JSONResponse({"error": "no autorizado"}, status_code=401)

    if tipo_plan not in PLANES:
        return JSONResponse({"error": f"Plan inválido: {tipo_plan}"}, status_code=400)

    sub_id = crear_suscripcion(
        cliente_id=cliente_id,
        tipo_plan=tipo_plan,
        notas=notas
    )
    return JSONResponse({"ok": True, "suscripcion_id": sub_id})


# ── API: ACTIVAR / SUSPENDER CLIENTE ─────────────────────────────────────────

@router.post("/api/clientes/{cliente_id}/estado")
async def api_estado_cliente(
    request: Request,
    cliente_id: int,
    activo: int = Form(...),
):
    admin = _require_admin(request)
    if not admin:
        return JSONResponse({"error": "no autorizado"}, status_code=401)

    with get_master_db() as conn:
        conn.execute(
            "UPDATE clientes SET activo=? WHERE id=?",
            (activo, cliente_id)
        )
        conn.commit()

    estado_txt = "activado" if activo else "suspendido"
    return JSONResponse({"ok": True, "estado": estado_txt})


# ── API: DESBLOQUEAR / AJUSTAR LÍMITE ────────────────────────────────────────

@router.post("/api/clientes/{cliente_id}/desbloquear")
async def api_desbloquear(request: Request, cliente_id: int):
    admin = _require_admin(request)
    if not admin:
        return JSONResponse({"error": "no autorizado"}, status_code=401)

    periodo = get_periodo_actual()
    with get_master_db() as conn:
        conn.execute("""
            UPDATE conteo_listados SET bloqueado=0
            WHERE cliente_id=? AND periodo=?
        """, (cliente_id, periodo))
        conn.commit()

    return JSONResponse({"ok": True})


# ── API: APROBAR TOP-UP ───────────────────────────────────────────────────────

@router.post("/api/clientes/{cliente_id}/topup")
async def api_topup(
    request: Request,
    cliente_id: int,
    cantidad: int = Form(...),
    precio_usd: float = Form(...),
    metodo_pago: str = Form("transferencia"),
    referencia_pago: str = Form(None),
    notas: str = Form(None),
):
    admin = _require_admin(request)
    if not admin:
        return JSONResponse({"error": "no autorizado"}, status_code=401)

    aprobar_topup(
        cliente_id=cliente_id,
        cantidad=cantidad,
        precio_usd=precio_usd,
        metodo_pago=metodo_pago,
        referencia=referencia_pago or "",
        admin_id=admin["id"],
        notas=notas
    )

    return JSONResponse({"ok": True, "listados_agregados": cantidad})


# ── API: USO DEL MES DE UN CLIENTE ───────────────────────────────────────────

@router.get("/api/clientes/{cliente_id}/uso")
async def api_uso_cliente(request: Request, cliente_id: int):
    admin = _require_admin(request)
    if not admin:
        return JSONResponse({"error": "no autorizado"}, status_code=401)

    estado = puede_generar(cliente_id)
    conteo = get_o_crear_conteo(cliente_id)

    with get_master_db() as conn:
        topups = conn.execute("""
            SELECT * FROM listados_adicionales
            WHERE cliente_id=? AND periodo=?
            ORDER BY creado_en DESC
        """, (cliente_id, get_periodo_actual())).fetchall()

        historial = conn.execute("""
            SELECT periodo, listados_generados, listados_limite, bloqueado
            FROM conteo_listados
            WHERE cliente_id=?
            ORDER BY periodo DESC LIMIT 6
        """, (cliente_id,)).fetchall()

    return JSONResponse({
        "estado_actual": estado,
        "topups_mes": [dict(t) for t in topups],
        "historial_6_meses": [dict(h) for h in historial],
    })


# ── API: LOG DE ACTIVIDAD ─────────────────────────────────────────────────────

@router.get("/api/log")
async def api_log(request: Request, cliente_id: int = None, limit: int = 50):
    admin = _require_admin(request)
    if not admin:
        return JSONResponse({"error": "no autorizado"}, status_code=401)

    with get_master_db() as conn:
        if cliente_id:
            rows = conn.execute("""
                SELECT l.*, c.nombre_corredora
                FROM log_actividad l
                LEFT JOIN clientes c ON c.id = l.cliente_id
                WHERE l.cliente_id=?
                ORDER BY l.creado_en DESC LIMIT ?
            """, (cliente_id, limit)).fetchall()
        else:
            rows = conn.execute("""
                SELECT l.*, c.nombre_corredora
                FROM log_actividad l
                LEFT JOIN clientes c ON c.id = l.cliente_id
                ORDER BY l.creado_en DESC LIMIT ?
            """, (limit,)).fetchall()

    return JSONResponse([dict(r) for r in rows])
