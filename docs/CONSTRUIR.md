# Construir NARSIL Pass

Cada ejecutable se construye en su propia plataforma (PyInstaller no hace compilación cruzada). La
integración continua del repositorio lo hace en cada versión para Windows x86-64, Linux x86-64 y
Linux ARM64.

## Requisitos

- Python 3.12 y Node.js 22.
- **Linux:** WebKitGTK para la ventana (`sudo apt install python3-gi gir1.2-gtk-3.0 gir1.2-webkit2-4.1`) y,
  para las pruebas de compatibilidad, KeePassXC (`sudo apt install keepassxc`), que se usa como oráculo.
- **Windows:** WebView2 (incluido en Windows 10 y 11).

## Desarrollo

```bash
python3 -m venv --system-site-packages .venv
.venv/bin/pip install -r requirements-dev.txt
(cd ui && npm ci && npm run build)          # interfaz: ui/dist/index.html
.venv/bin/python narsil_pass.py             # abre la ventana
.venv/bin/python narsil_pass.py --autoprueba   # comprueba el núcleo sin ventana y sale
```

`--depurar` abre la ventana con las herramientas de desarrollo del motor web.

## Ejecutable

```bash
bash empaquetado/construir.sh               # Linux → dist/narsil-pass-linux-<arquitectura>
```

```powershell
powershell -ExecutionPolicy Bypass -File empaquetado\construir.ps1   # Windows → dist\narsil-pass-windows-x86_64.exe
```

Ambos scripts crean su propio entorno de construcción, compilan con PyInstaller en un único fichero
con la interfaz, la lista de palabras del generador y el icono dentro, y ejecutan `--autoprueba`
sobre el resultado.

## Pruebas

| Qué | Cómo |
|---|---|
| Núcleo, puente y compatibilidad con KeePassXC | `.venv/bin/python -m pytest -q` |
| Modelo de la ficha de identidad (lectura y escritura sin pérdidas) | `node scripts/prueba_identidad.mjs` |
| Listado agrupado por sección | `node scripts/prueba_listado.mjs` |
| Ventana real: puente, desbloqueo, foto de 2 MB, cero sockets | `xvfb-run -a .venv/bin/python scripts/humo_ventana.py` |
| Recorrido de la interfaz con capturas (33 pantallas) | `(cd ui && npm run build:demo && node ../scripts/capturas.mjs)` |

Las capturas usan una compilación de demostración (`npm run build:demo`) con un puente simulado y
datos inventados; ese código no entra en el ejecutable.

## Base de ejemplo

```bash
.venv/bin/python scripts/base_ejemplo.py ejemplos
```

Regenera `ejemplos/NARSIL-ejemplo-KDBX4.kdbx`, `ejemplos/NARSIL-ejemplo-KDBX31.kdbx` y su inventario.
Necesita `keepassxc-cli` para crear la variante 3.1. Las fechas de caducidad y renovación son
relativas al momento de generarla.

## Versiones

Una etiqueta `v*` (por ejemplo `v1.0.0`) lanza la integración continua completa: pruebas, los tres
ejecutables con su autoprueba y la publicación de la versión con `SHA256SUMS`. La versión de la
aplicación está en `app/config.py`.
