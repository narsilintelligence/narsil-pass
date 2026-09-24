"""Prueba de humo con la ventana REAL (pywebview + WebKitGTK), pensada para Xvfb en Linux:

    xvfb-run -a .venv/bin/python scripts/humo_ventana.py

1. Crea una base de prueba, arranca la ventana con la interfaz compilada (ui/dist/index.html).
2. Desde JavaScript rellena la contraseña y pulsa Enter, como un operador.
3. Comprueba que aparece la pantalla principal con la entrada de prueba.
4. Comprueba que el proceso no tiene sockets TCP/UDP en escucha ni conexiones abiertas.
Termina con 0 si todo va bien.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import threading
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
os.environ["NARSIL_PASS_DATOS"] = tempfile.mkdtemp(prefix="narsil-pass-humo-")

from app import ventana  # noqa: E402
from app.api import Api  # noqa: E402
from app.config import Preferencias  # noqa: E402
from nucleo import kdf  # noqa: E402
from nucleo.base import Base  # noqa: E402
from nucleo.formato import VD_BYTES, VD_UINT32, VD_UINT64, Variante  # noqa: E402

resultado = {"ok": False, "detalle": "sin empezar"}


def sockets_del_proceso() -> list[str]:
    """Sockets TCP/UDP del proceso (en escucha o conectados), leyendo /proc sin dependencias."""
    inodos = set()
    for fd in Path(f"/proc/{os.getpid()}/fd").iterdir():
        try:
            destino = os.readlink(fd)
        except OSError:
            continue
        if destino.startswith("socket:["):
            inodos.add(destino[8:-1])
    hallados = []
    for tabla in ("tcp", "tcp6", "udp", "udp6"):
        for linea in Path(f"/proc/net/{tabla}").read_text().splitlines()[1:]:
            campos = linea.split()
            if len(campos) > 9 and campos[9] in inodos:
                hallados.append(f"{tabla} {campos[1]} -> {campos[2]} estado {campos[3]}")
    return hallados


class Informe:
    """Recibe lo que la página comunica por el puente. La CSP estricta prohíbe eval, así que
    evaluate_js no sirve: se actúa con run_js (sin eval) y la página responde por el puente real,
    que es justo lo que hay que probar."""
    def __init__(self) -> None:
        self.textos: dict[str, str] = {}

    def recibir(self, clave: str, texto: str) -> None:
        self.textos[clave] = texto


informe = Informe()


def guion(w) -> None:
    def esperar(clave: str, selector: str, segundos: float = 30) -> str:
        fin = time.time() + segundos
        while time.time() < fin:
            w.run_js(f"""if (document.querySelector({json.dumps(selector)}) && window.pywebview && window.pywebview.api)
                window.pywebview.api.informe_humo({json.dumps(clave)}, document.body.innerText); void 0""")
            time.sleep(0.5)
            if clave in informe.textos:
                return informe.textos[clave]
        raise RuntimeError(f"no aparece {selector}")
    try:
        esperar("desbloqueo", "input[type=password]")
        w.run_js("""(() => { const i = document.querySelector('input[type=password]');
            const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;
            set.call(i, 'clave-humo'); i.dispatchEvent(new Event('input', { bubbles: true }));
            i.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true })); })()""")
        texto = esperar("principal", ".cabecera")
        time.sleep(1.0)
        informe.textos.pop("principal", None)
        texto = esperar("principal", ".cabecera")
        if "Entrada de humo" not in texto:
            raise RuntimeError("la entrada de prueba no aparece en la lista")
        # Una foto de ~2 MB por el puente, ida y vuelta: es el camino de arrastrar y pegar imágenes.
        w.run_js("""(async () => { const api = window.pywebview.api;
            const r = await api.crear_entrada(null, [{clave: 'Title', valor: 'Identidad de humo', protegido: false},
                {clave: 'NARSIL.Tipo', valor: 'identidad', protegido: false}], [], null);
            const bytes = new Uint8Array(2 * 1024 * 1024); for (let i = 0; i < bytes.length; i++) bytes[i] = (i * 31) & 255;
            let bin = ''; for (let i = 0; i < bytes.length; i += 8192) bin += String.fromCharCode(...bytes.subarray(i, i + 8192));
            const a = await api.agregar_adjunto_datos(r.uuid, 'foto.png', btoa(bin));
            const img = await api.imagen(r.uuid, 'foto.png');
            api.informe_humo('foto', JSON.stringify({ ok: a.ok && img.ok, largo: img.ok ? img.url.length : 0 })); })(); void 0""")
        fin = time.time() + 60
        while "foto" not in informe.textos and time.time() < fin:
            time.sleep(0.5)
        foto = json.loads(informe.textos.get("foto", "{}") or "{}")
        esperado = len("data:image/png;base64,") + 4 * ((2 * 1024 * 1024 + 2) // 3)
        if not foto.get("ok") or foto.get("largo") != esperado:
            raise RuntimeError(f"la foto no hace el viaje completo por el puente: {foto}")
        sockets = sockets_del_proceso()
        if sockets:
            raise RuntimeError("el proceso tiene sockets de red: " + "; ".join(sockets))
        resultado.update(ok=True, detalle="ventana real con la CSP de producción: puente activo, desbloqueo por Enter, "
                                          "lista visible, foto de 2 MB por el puente, cero sockets de red")
    except Exception as e:  # noqa: BLE001
        resultado.update(ok=False, detalle=f"{type(e).__name__}: {e}")
    finally:
        w.destroy()


def main() -> int:
    if not ventana.html_interfaz().exists():
        print("falta ui/dist/index.html: compile la interfaz primero")
        return 2
    tmp = Path(tempfile.mkdtemp(prefix="narsil-pass-base-"))
    ruta = tmp / "humo.kdbx"
    p = Variante()
    for t, k, v in ((VD_BYTES, "$UUID", kdf.UUID_ARGON2ID), (VD_UINT32, "V", 0x13), (VD_BYTES, "S", bytes(32)),
                    (VD_UINT32, "P", 1), (VD_UINT64, "M", 8 << 20), (VD_UINT64, "I", 2)):
        p.poner(t, k, v)
    base = Base.nueva("Humo", "clave-humo", parametros_kdf=p)
    base.nueva_entrada(base.raiz, {"Title": "Entrada de humo", "UserName": "u", "Password": "p"})
    base.guardar(ruta)
    api = Api(preferencias=Preferencias(recientes=[]))
    api.ruta_inicial = str(ruta)
    api.informe_humo = informe.recibir  # solo en esta prueba
    hilo = {"t": None}

    def arrancar(w):
        hilo["t"] = threading.Thread(target=guion, args=(w,), daemon=True)
        hilo["t"].start()

    ventana.ejecutar(api, al_arrancar=arrancar)
    print(json.dumps(resultado, ensure_ascii=False))
    return 0 if resultado["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
