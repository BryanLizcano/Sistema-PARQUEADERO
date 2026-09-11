# Guía de Instalación del Parqueadero POS en Zorin OS

Esta guía te explica cómo transferir e instalar este sistema de caja en el computador del parqueadero (Zorin OS) para que funcione **24 horas al día, 7 días a la semana**, reinicie automáticamente junto con el PC, y sea a prueba de fallos humanos (sin pantallas negras de terminal abiertas).

---

## 1. Mover los archivos al Computador del Parqueadero
1. En tu PC con Windows, copia la carpeta entera `parqueadero` en una memoria USB (Pendrive).
2. Conecta la USB en el computador del celador (Zorin OS).
3. Copia la carpeta `parqueadero` y pégala en un lugar seguro donde no la vayan a borrar por accidente. **Recomendación:** Pégala en `Documentos` o dentro de la carpeta personal del usuario (ej. `/home/usuario/parqueadero`).

---

## 2. Ejecutar la Instalación Automática
El proyecto incluye un script mágico llamado `instalar_zorin.sh` que hará todo el trabajo difícil por ti.

1. En Zorin OS, haz **clic derecho** sobre una parte vacía dentro de la carpeta `parqueadero` y selecciona **"Abrir en una Terminal"** (Open in Terminal).
2. En la terminal que se abre, escribe el siguiente comando para darle permisos de ejecución al instalador:
   ```bash
   chmod +x instalar_zorin.sh
   ```
3. Ahora, ejecuta la instalación:
   ```bash
   bash instalar_zorin.sh
   ```
4. Te pedirá la contraseña del administrador del PC (para poder instalarlo como servicio del sistema). Escríbela (no se verán asteriscos mientras escribes) y presiona **Enter**.
5. Espera unos segundos a que termine de descargar las librerías de Python. Al final te saldrá un mensaje diciendo `¡INSTALACIÓN COMPLETADA EXITOSAMENTE!`.

---

## 3. ¿Qué sucedió y cómo usarlo?

¡El sistema ya está funcionando! No verás ninguna ventana rara abierta porque ahora el servidor se comporta como una parte fundamental de Zorin OS.

*   **Arranque Automático:** Si se va la luz o reinician el PC, no te preocupes. Zorin OS encenderá el servidor de FastAPI en segundo plano automáticamente incluso antes de que el celador ponga su clave para entrar al escritorio.
*   **Recuperación de Fallos:** Si por algún motivo la aplicación se cuelga, el sistema operativo detectará que se apagó y la volverá a encender en 3 segundos.
*   **Acceso Directo:** En el escritorio de Zorin OS ahora hay un ícono llamado **Caja Parqueadero**. El celador solo tiene que hacer doble clic en él para que se abra el navegador web directamente en la pantalla de cobros, listo para facturar e imprimir tickets térmicos.

---

## Mantenimiento y Comandos Útiles (Solo para ti como Administrador)

Dado que el programa ahora corre como un "Servicio del Sistema" llamado `parqueadero`, el celador no puede cerrarlo por error. 
Si alguna vez necesitas actualizar el código o revisar algo, usa estos comandos en la terminal de Zorin OS:

*   **Ver si el servidor está corriendo bien:**
    ```bash
    sudo systemctl status parqueadero
    ```
*   **Reiniciar el servidor (si cambiaste algún código):**
    ```bash
    sudo systemctl restart parqueadero
    ```
*   **Apagar el servidor por completo:**
    ```bash
    sudo systemctl stop parqueadero
    ```
*   **Ver el historial de errores o cobros de la terminal:**
    ```bash
    sudo journalctl -u parqueadero -f
    ```

