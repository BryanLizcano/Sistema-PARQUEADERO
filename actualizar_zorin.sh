#!/bin/bash
set -e

# ==========================================================
# Script de Actualización Segura para el PC del Parqueadero
# Preserva intacta la base de datos parqueadero.db existente
# ==========================================================

echo "=================================================="
echo " Actualizando Sistema — PARQUEADERO BAHONDO"
echo "=================================================="

# 1. Crear respaldo automático de la base de datos antes de actualizar
mkdir -p backups
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
if [ -f "parqueadero.db" ]; then
    echo "[1/5] Creando copia de seguridad de parqueadero.db..."
    cp parqueadero.db "backups/parqueadero_${TIMESTAMP}.db"
    echo "      Backup guardado en: backups/parqueadero_${TIMESTAMP}.db"
fi

# 2. Descargar los últimos cambios desde Git sin perder la BD local
echo "[2/5] Descargando nueva versión desde Git..."
git fetch origin
BRANCH=$(git rev-parse --abbrev-ref HEAD)
git pull origin "$BRANCH"

# Si git eliminó parqueadero.db del índice al dejar de rastrearlo, restaurar desde el backup
if [ ! -f "parqueadero.db" ] && [ -f "backups/parqueadero_${TIMESTAMP}.db" ]; then
    echo "      Restaurando base de datos local parqueadero.db..."
    cp "backups/parqueadero_${TIMESTAMP}.db" parqueadero.db
fi

# 3. Activar entorno virtual e instalar nuevas librerías (bcrypt, xlsxwriter, reportlab, pyyaml)
echo "[3/5] Actualizando librerías en el entorno virtual (.venv)..."
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
fi
source .venv/bin/activate
pip install -r requirements.txt

# 4. Reiniciar el servicio en segundo plano (ejecuta migraciones y seed automáticamente)
echo "[4/5] Reiniciando servicio parqueadero.service..."
sudo systemctl restart parqueadero.service

# 5. Verificar estado del servicio
echo "[5/5] Verificando estado del servidor..."
sudo systemctl is-active --quiet parqueadero.service && echo "✅ Servicio activo y corriendo en http://127.0.0.1:8000"

echo ""
echo "=================================================="
echo " ¡ACTUALIZACIÓN COMPLETADA CON ÉXITO!"
echo "=================================================="
echo "- Tus tickets y tarifas anteriores se conservaron intactos."
echo "- Abre el navegador y presiona Ctrl + Shift + R para cargar la nueva interfaz."
echo "- Usuario Admin inicial: Admin  | Contraseña: admin"
echo "- Usuario Cajero inicial: Cajero | Contraseña: 123456"
