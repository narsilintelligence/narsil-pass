"""Arranque de NARSIL Pass.

  narsil-pass [base.kdbx]   abre la ventana (con esa base preseleccionada, si se indica)
  narsil-pass --autoprueba  comprueba el núcleo sin ventana (crear, guardar, releer, 3.1 y 4,
                            TOTP, generador) y termina con 0 si todo está bien. La usa el CI.
"""
from __future__ import annotations

import logging
import sys
import tempfile
from logging.handlers import RotatingFileHandler
from pathlib import Path

from .config import VERSION, carpeta_datos


def _preparar_registro() -> None:
    """Todo al fichero de registro. Empaquetado sin consola, `sys.stdout`/`sys.stderr` son `None`:
    cualquier escritura ahí revienta el proceso sin que nadie lo vea. El registro nunca lleva
    valores de la base."""
    carpeta = carpeta_datos() / "registro"
    carpeta.mkdir(parents=True, exist_ok=True)
    fichero = carpeta / "narsil-pass.log"
    manejador = RotatingFileHandler(fichero, maxBytes=1_000_000, backupCount=2, encoding="utf-8")
    manejador.setFormatter(logging.Formatter("%(asctime)s  %(levelname)-5s  %(name)s  %(message)s"))
    raiz = logging.getLogger()
    raiz.addHandler(manejador)
    raiz.setLevel(logging.INFO)
    if sys.stdout is None:
        sys.stdout = open(fichero, "a", encoding="utf-8", buffering=1)  # noqa: SIM115
    if sys.stderr is None:
        sys.stderr = open(fichero, "a", encoding="utf-8", buffering=1)  # noqa: SIM115


def autoprueba() -> int:
    from nucleo import generador, kdf, totp
    from nucleo.base import ETIQUETAS_FECHA, Base, campos_entrada, fecha_kdbx, texto_fecha_iso
    from nucleo.boveda import Boveda
    from nucleo.formato import VD_BYTES, VD_UINT32, VD_UINT64, Variante

    def rapido(tipo):
        v = Variante()
        v.poner(VD_BYTES, "$UUID", tipo)
        if tipo == kdf.UUID_AES_KDF:
            v.poner(VD_BYTES, "S", bytes(32))
            v.poner(VD_UINT64, "R", 1000)
        else:
            for t, k, x in ((VD_UINT32, "V", 0x13), (VD_BYTES, "S", bytes(32)), (VD_UINT32, "P", 1),
                            (VD_UINT64, "M", 8 << 20), (VD_UINT64, "I", 2)):
                v.poner(t, k, x)
        return v

    with tempfile.TemporaryDirectory() as tmp:
        ruta = str(Path(tmp) / "prueba.kdbx")
        base = Base.nueva("Autoprueba", "clave-ñ", parametros_kdf=rapido(kdf.UUID_ARGON2ID))
        base.nueva_entrada(base.raiz, {"Title": "t", "Password": "p-€", "otp": "otpauth://totp/x?secret=GEZDGNBVGY3TQOJQ"})
        base.guardar(ruta)
        b = Boveda.abrir(ruta, "clave-ñ")
        assert [campos_entrada(e)["Password"] for e in b.base.entradas()] == ["p-€"]
        base.version = 0x00030001  # misma base en 3.1: guardar y releer
        base.kdf = rapido(kdf.UUID_AES_KDF)
        base.flujo_id = 2
        base._transformada = None
        for elem in base.xml.getroot().iter(*ETIQUETAS_FECHA):
            elem.text = texto_fecha_iso(fecha_kdbx(elem.text))
        base.guardar(ruta)
        assert Base.abrir(Path(ruta).read_bytes(), "clave-ñ").version_texto == "KDBX 3.1"
        assert totp.leer({"otp": "otpauth://totp/x?secret=GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ&digits=8"}).codigo(59) == "94287082"
        assert len(generador.contrasena(30)) == 30
    print(f"NARSIL Pass {VERSION}: autoprueba correcta")
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if "--autoprueba" in argv:
        return autoprueba()
    _preparar_registro()
    registro = logging.getLogger("narsil-pass")
    registro.info("arranque %s", VERSION)
    from . import ventana
    from .api import Api
    api = Api()
    rutas = [a for a in argv if not a.startswith("-") and a.lower().endswith(".kdbx")]
    api.ruta_inicial = str(Path(rutas[0]).resolve()) if rutas else None
    try:
        ventana.ejecutar(api, depurar="--depurar" in argv)
    finally:
        try:
            api._pp.limpiar_ya()
        except Exception:
            pass
        ventana.cerrar_todas()
    return 0
