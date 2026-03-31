"""
setup_inicial.py — Script de configuración inicial de Toxiro Propiedades
Ejecutar UNA VEZ para:
  1. Crear la DB maestra con todas las tablas
  2. Crear el admin de Toxiro Digital
  3. Migrar la instalación actual como primer cliente

Uso:
    cd listapro
    python setup_inicial.py
"""
import os
import sys
import sqlite3
from master_db import (
    init_master_db, crear_admin, crear_cliente, crear_suscripcion,
    get_master_db, hash_password
)

print("=" * 60)
print("  Toxiro Propiedades — Setup Inicial")
print("=" * 60)

# ── PASO 1: Inicializar DB maestra ────────────────────────────────────────────
print("\n[1/4] Inicializando base de datos maestra...")
init_master_db()
print("      ✓ toxiro_master.db creada con todas las tablas")

# ── PASO 2: Crear admin de Toxiro Digital ─────────────────────────────────────
print("\n[2/4] Creando admin de Toxiro Digital...")

with get_master_db() as conn:
    existing_admin = conn.execute(
        "SELECT id FROM admins WHERE email = 'contacto@toxirodigital.cloud'"
    ).fetchone()

if existing_admin:
    print("      ℹ  Admin ya existe, saltando...")
    admin_id = existing_admin["id"]
else:
    admin_id = crear_admin(
        nombre="Rodrigo Castañeda P.",
        email="contacto@toxirodigital.cloud",
        password="ToxiroAdmin2026!",   # ← CAMBIAR después del primer login
        rol="superadmin"
    )
    print(f"      ✓ Admin creado (ID: {admin_id})")
    print("      ⚠  IMPORTANTE: cambia la contraseña después del primer login")
    print("         Email:    contacto@toxirodigital.cloud")
    print("         Password: ToxiroAdmin2026!")

# ── PASO 3: Migrar instalación actual como primer cliente ─────────────────────
print("\n[3/4] Migrando instalación actual como primer cliente...")

with get_master_db() as conn:
    existing_client = conn.execute(
        "SELECT id FROM clientes WHERE slug = 'demo'"
    ).fetchone()

if existing_client:
    print("      ℹ  Cliente 'demo' ya existe, saltando...")
    cliente_id = existing_client["id"]
else:
    cliente_id = crear_cliente(
        slug="demo",
        nombre_corredora="Toxiro Demo",
        email_contacto="contacto@toxirodigital.cloud",
        telefono="+56972110564",
        razon_social="Toxiro Digital",
        creado_por=admin_id
    )
    print(f"      ✓ Cliente 'demo' creado (ID: {cliente_id})")

    # Configurar cuenta Instagram del cliente demo
    with get_master_db() as conn:
        conn.execute("""
            UPDATE configuracion_cliente
            SET cuenta_instagram = ?,
                uploadpost_api_key = ?,
                openai_api_key = ?,
                nombre_display = 'Toxiro Propiedades'
            WHERE cliente_id = ?
        """, (
            os.getenv("UPLOADPOST_USER", ""),
            os.getenv("UPLOADPOST_API_KEY", ""),
            os.getenv("OPENAI_API_KEY", ""),
            cliente_id
        ))
        conn.commit()

    # Crear suscripción profesional
    sub_id = crear_suscripcion(
        cliente_id=cliente_id,
        tipo_plan="profesional",
        notas="Cliente demo - instalación inicial"
    )
    print(f"      ✓ Suscripción Profesional creada (ID: {sub_id})")

    # Migrar propiedades existentes si la DB antigua existe
    old_db = "/data/db/listapro.db"
    new_db = "/data/db/demo.db"
    if os.path.exists(old_db) and not os.path.exists(new_db):
        import shutil
        shutil.copy2(old_db, new_db)
        print(f"      ✓ Propiedades migradas de listapro.db → demo.db")
    elif os.path.exists(new_db):
        print("      ℹ  demo.db ya existe, no se sobreescribe")

# ── PASO 4: Resumen ───────────────────────────────────────────────────────────
print("\n[4/4] Resumen de la instalación:")
with get_master_db() as conn:
    clientes = conn.execute("SELECT COUNT(*) as n FROM clientes").fetchone()["n"]
    admins   = conn.execute("SELECT COUNT(*) as n FROM admins").fetchone()["n"]
    subs     = conn.execute("SELECT COUNT(*) as n FROM suscripciones WHERE estado='activa'").fetchone()["n"]

print(f"      Admins:       {admins}")
print(f"      Clientes:     {clientes}")
print(f"      Suscripciones activas: {subs}")

print("\n" + "=" * 60)
print("  Setup completado exitosamente")
print("  Panel admin: http://localhost:8000/admin")
print("=" * 60 + "\n")
