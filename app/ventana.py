"""Ventana de NARSIL Pass (pywebview: WebView2 en Windows, WebKitGTK en Linux).

La interfaz es un único HTML con todo dentro (código, estilos, fuentes, escudo) y se carga como
`file://`: pywebview solo levanta su servidor HTTP interno si la URL es una ruta suelta, así que la
aplicación no abre ningún puerto. `private_mode=True`: el motor web no guarda nada en disco.
"""
from __future__ import annotations

import sys
from pathlib import Path

from .config import recursos

TITULO = "NARSIL Pass"
TAMANO = (1280, 820)
MINIMO = (980, 640)
FONDO = "#090D18"


def html_interfaz() -> Path:
    return recursos() / "ui" / "dist" / "index.html"


def icono() -> str | None:
    nombre = "narsil.ico" if sys.platform == "win32" else "narsil-256.png"
    ruta = recursos() / "empaquetado" / nombre
    return str(ruta) if ruta.exists() else None


def _medidas(webview) -> dict:
    ancho, alto = TAMANO
    try:
        pantalla = webview.screens[0]
        ancho = min(ancho, int(pantalla.width * 0.92))
        alto = min(alto, int(pantalla.height * 0.9))
        return {"width": ancho, "height": alto, "screen": pantalla,
                "x": pantalla.x + (pantalla.width - ancho) // 2, "y": pantalla.y + (pantalla.height - alto) // 2}
    except Exception:
        return {"width": ancho, "height": alto}


def ejecutar(api, *, depurar: bool = False, al_arrancar=None) -> None:
    import webview
    webview.settings["ALLOW_DOWNLOADS"] = False
    webview.settings["OPEN_DEVTOOLS_IN_DEBUG"] = depurar
    url = html_interfaz().resolve().as_uri()
    ventana = webview.create_window(TITULO, url=url, js_api=api, min_size=MINIMO, background_color=FONDO,
                                    text_select=True, **_medidas(webview))
    api._ventana = ventana
    webview.start(al_arrancar, (ventana,) if al_arrancar else None, private_mode=True, debug=depurar,
                  icon=icono())


def cerrar_todas() -> None:
    try:
        import webview
        for w in list(getattr(webview, "windows", []) or []):
            try:
                w.destroy()
            except Exception:
                pass
    except Exception:
        pass
