#!/usr/bin/env bash
# Construye el ejecutable único de NARSIL Pass en Linux para la arquitectura de la máquina:
#   dist/narsil-pass-linux-x86_64 · dist/narsil-pass-linux-aarch64
# Requiere Python 3.11+, la interfaz compilada (ui/dist/index.html) y WebKitGTK del sistema
# (Debian/Ubuntu: python3-gi gir1.2-gtk-3.0 gir1.2-webkit2-4.1).
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
RAIZ="$(pwd)"
test -f ui/dist/index.html || { echo "Falta ui/dist/index.html: cd ui && npm ci && npm run build"; exit 1; }
VENV=.venv-build
[ -x "$VENV/bin/python" ] || python3 -m venv --system-site-packages "$VENV"
"$VENV/bin/pip" install --disable-pip-version-check --quiet --upgrade pip
"$VENV/bin/pip" install --disable-pip-version-check --quiet -r requirements.txt -r empaquetado/requirements-build.txt
NOMBRE="narsil-pass-linux-$(uname -m)"
rm -rf dist build
"$VENV/bin/python" -m PyInstaller --noconfirm --clean --onefile --windowed \
    --name "$NOMBRE" --distpath dist --workpath build --specpath build \
    --paths "$RAIZ" \
    --add-data "$RAIZ/ui/dist/index.html:ui/dist" \
    --add-data "$RAIZ/nucleo/datos:nucleo/datos" \
    --add-data "$RAIZ/empaquetado/narsil-256.png:empaquetado" \
    --collect-submodules app --collect-submodules nucleo \
    --collect-all webview --collect-all argon2 \
    --exclude-module numpy --exclude-module tkinter --exclude-module PIL --exclude-module matplotlib \
    --hidden-import gi.repository.Gtk --hidden-import gi.repository.WebKit2 \
    "$RAIZ/narsil_pass.py"
"dist/$NOMBRE" --autoprueba
echo "CONSTRUIDO $(pwd)/dist/$NOMBRE"
