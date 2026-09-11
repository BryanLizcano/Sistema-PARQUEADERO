#!/bin/bash

# ==========================================
# Script de Instalación Automática para Zorin OS / Ubuntu
# ==========================================

echo "Iniciando configuración del Parqueadero POS..."

# 1. Instalar dependencias del sistema operativo (Python venv) si no existen
sudo apt update
sudo apt install -y python3-venv python3-pip

# 2. Crear y configurar entorno virtual
echo "Creando entorno virtual de Python..."
python3 -m venv .venv
source .venv/bin/activate
pip install fastapi uvicorn pydantic sqlalchemy

# Obtener ruta actual y usuario
CURRENT_DIR=$(pwd)
CURRENT_USER=$(whoami)

# 3. Crear el servicio (Demonio) de systemd
# Esto garantiza que inicie solo al prender el PC y reviva si falla.
echo "Configurando servicio en segundo plano..."
cat <<EOF | sudo tee /etc/systemd/system/parqueadero.service
[Unit]
Description=Servidor API Parqueadero
After=network.target

[Service]
User=$CURRENT_USER
WorkingDirectory=$CURRENT_DIR
# Usamos el uvicorn del entorno virtual
ExecStart=$CURRENT_DIR/.venv/bin/python -m uvicorn main:app --host 127.0.0.1 --port 8000
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

# 4. Habilitar e iniciar el servicio
sudo systemctl daemon-reload
sudo systemctl enable parqueadero.service
sudo systemctl start parqueadero.service

# 5. Crear Acceso Directo (Icono en el Escritorio)
echo "Creando acceso directo..."
# Detectar carpeta de escritorio (puede llamarse Escritorio o Desktop)
DESKTOP_DIR="$HOME/Escritorio"
if [ ! -d "$DESKTOP_DIR" ]; then
    DESKTOP_DIR="$HOME/Desktop"
fi

DESKTOP_FILE="$DESKTOP_DIR/Parqueadero.desktop"

# Creamos un archivo .desktop que abrirá el navegador en modo app (sin barra de URLs) o pestaña normal
cat <<EOF > "$DESKTOP_FILE"
[Desktop Entry]
Version=1.0
Name=Caja Parqueadero
Comment=Sistema POS
# Intentamos abrirlo en Chrome en modo kiosco/app. Si prefieres Firefox, usa: firefox http://127.0.0.1:8000
Exec=xdg-open http://127.0.0.1:8000/
Icon=browser
Terminal=false
Type=Application
Categories=Utility;
EOF

# Dar permisos de ejecución al acceso directo para que Zorin permita abrirlo
chmod +x "$DESKTOP_FILE"
gio set "$DESKTOP_FILE" metadata::trusted true 2>/dev/null

echo ""
echo "=================================================="
echo "¡INSTALACIÓN COMPLETADA EXITOSAMENTE!"
echo "=================================================="
echo "- El servidor ya está corriendo invisible en el fondo."
echo "- Se iniciará solo cada vez que enciendas el computador."
echo "- Tienes un icono llamado 'Caja Parqueadero' en tu escritorio."
echo ""
echo "Si algún día necesitas ver los errores o reiniciar manualmente:"
echo "sudo systemctl status parqueadero"
echo "sudo systemctl restart parqueadero"

