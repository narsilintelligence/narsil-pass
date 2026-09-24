"""Regresiones de la auditoría de seguridad: ficheros hostiles, TOTP fuera de rango, permisos del
guardado, fichero de clave privado, bloqueo con portapapeles y CI con mínimo privilegio."""
from __future__ import annotations

import hashlib
import os
import stat
import struct
import sys
from pathlib import Path

import pytest

from app.api import Api
from app.config import Preferencias
from nucleo import formato, kdf, totp
from nucleo.base import Base
from nucleo.errores import FicheroDanado
from tests.test_interoperabilidad import CLAVE, _kdf_rapido

POSIX = pytest.mark.skipif(sys.platform == "win32", reason="permisos POSIX")


def _vd(cuerpo: bytes) -> bytes:
    return struct.pack("<H", 0x0100) + cuerpo


@pytest.mark.parametrize("datos", [
    _vd(b"\x42\x01"),                                                              # longitud truncada
    _vd(b"\x42" + struct.pack("<i", 1) + b"\xff" + struct.pack("<i", 0) + b"\x00"),  # clave no UTF-8
    _vd(b"\x04" + struct.pack("<i", 1) + b"M" + struct.pack("<i", 2) + b"ab\x00"),   # uint32 de 2 bytes
    _vd(b"\x42" + struct.pack("<i", -9) + bytes(12)),                                # longitud negativa
])
def test_variantdictionary_hostil_es_fichero_danado(datos):
    with pytest.raises(FicheroDanado):
        formato.Variante.leer(datos)


def _base_con_kdf(tmp_path, parametros: formato.Variante) -> bytes:
    """KDBX 4 válido con la KDF de la cabecera sustituida y el hash (no la HMAC) recalculado:
    lo que puede fabricar cualquiera sin conocer la clave."""
    ruta = tmp_path / "b.kdbx"
    Base.nueva("x", CLAVE, parametros_kdf=_kdf_rapido(kdf.UUID_ARGON2ID)).guardar(ruta)
    datos = ruta.read_bytes()
    cab, pos = formato.leer_cabecera(datos)
    campos = [(i, parametros.escribir() if i == formato.CAB_KDF else v) for i, v in cab.campos]
    nueva = datos[:12] + formato.escribir_tlv(campos)
    return nueva + hashlib.sha256(nueva).digest() + datos[pos + 32:]


def test_parametros_kdf_hostiles_no_escapan_como_error_interno(tmp_path):
    p = _kdf_rapido(kdf.UUID_ARGON2ID)
    p.poner(formato.VD_UINT32, "P", 0)
    with pytest.raises(FicheroDanado):
        Base.abrir(_base_con_kdf(tmp_path, p), CLAVE)
    p = _kdf_rapido(kdf.UUID_ARGON2ID)
    p.poner(formato.VD_BYTES, "S", b"")
    with pytest.raises(FicheroDanado):
        Base.abrir(_base_con_kdf(tmp_path, p), CLAVE)


def test_xml_interior_con_dtd_se_rechaza(tmp_path):
    secreto = tmp_path / "secreto.txt"
    secreto.write_text("NO-DEBE-SALIR")
    xxe = (f'<?xml version="1.0"?><!DOCTYPE K [<!ENTITY x SYSTEM "{secreto.as_uri()}">]>'
           '<KeePassFile><Meta><DatabaseName>&x;</DatabaseName></Meta></KeePassFile>').encode()
    with pytest.raises(FicheroDanado):
        Base._parsear(xxe)
    risas = (b'<?xml version="1.0"?><!DOCTYPE l [<!ENTITY a "aaaaaaaaaa">'
             + b"".join(b'<!ENTITY %c "%s">' % (98 + i, (b"&%c;" % (97 + i)) * 10) for i in range(9))
             + b']><KeePassFile><Meta><DatabaseName>&j;</DatabaseName></Meta></KeePassFile>')
    with pytest.raises(FicheroDanado):
        Base._parsear(risas)


@pytest.mark.parametrize("uri", [
    "otpauth://totp/x?secret=GEZDGNBVGY3TQOJQ&digits=1000000000",
    "otpauth://totp/x?secret=GEZDGNBVGY3TQOJQ&period=0",
    "otpauth://totp/x?secret=GEZDGNBVGY3TQOJQ&period=-30",
    "otpauth://totp/x?secret=GEZDGNBVGY3TQOJQ&algorithm=MD5",
])
def test_totp_fuera_de_rango_no_congela(uri):
    assert totp.leer({"otp": uri}) is None


def test_totp_valido_sigue_funcionando():
    assert totp.leer({"otp": "otpauth://totp/x?secret=GEZDGNBVGY3TQOJQ&digits=8&algorithm=sha256"}) is not None


def _modo(ruta) -> int:
    return stat.S_IMODE(os.stat(ruta).st_mode)


@POSIX
def test_guardado_privado_y_conserva_permisos(tmp_path):
    ruta = tmp_path / "b.kdbx"
    base = Base.nueva("x", CLAVE, parametros_kdf=_kdf_rapido(kdf.UUID_ARGON2ID))
    viejo = os.umask(0o022)
    try:
        base.guardar(ruta)
        assert _modo(ruta) == 0o600  # base nueva: solo el propietario
        os.chmod(ruta, 0o640)
        base.guardar(ruta, copia_previa=True)
        assert _modo(ruta) == 0o640 and _modo(str(ruta) + ".bak") == 0o640  # respeta lo que eligió
    finally:
        os.umask(viejo)
    assert Base.abrir(ruta.read_bytes(), CLAVE).nombre == "x"


@POSIX
def test_guardado_no_sigue_enlace_plantado(tmp_path):
    ruta = tmp_path / "b.kdbx"
    victima = tmp_path / "victima.txt"
    victima.write_text("intacto")
    os.symlink(victima, tmp_path / f".b.kdbx.{os.getpid()}.tmp")
    base = Base.nueva("x", CLAVE, parametros_kdf=_kdf_rapido(kdf.UUID_ARGON2ID))
    with pytest.raises(OSError):
        base.guardar(ruta)
    assert victima.read_text() == "intacto" and not ruta.exists()


class _PortapapelesFalso:
    def __init__(self):
        self.limpiado = 0

    def disponible(self):
        return True

    def limpiar_ya(self):
        self.limpiado += 1


@pytest.fixture
def api(tmp_path, monkeypatch):
    monkeypatch.setenv("NARSIL_PASS_DATOS", str(tmp_path / "datos"))
    elecciones = {}
    a = Api(preferencias=Preferencias(), dialogos=lambda tipo, **kw: elecciones.get(tipo))
    a._pp = _PortapapelesFalso()
    return a, elecciones


@POSIX
def test_fichero_de_clave_nace_privado(api, tmp_path):
    a, elecciones = api
    elecciones["guardar"] = str(tmp_path / "clave.keyx")
    assert a.crear_fichero_clave()["ok"]
    assert _modo(tmp_path / "clave.keyx") == 0o600
    assert a.crear_fichero_clave()["error"] == "permiso"  # nunca sobrescribe


def test_bloquear_con_guardado_fallido_no_finge_y_vacia_portapapeles(api, tmp_path):
    a, _ = api
    ruta = tmp_path / "b.kdbx"
    Base.nueva("x", CLAVE, parametros_kdf=_kdf_rapido(kdf.UUID_ARGON2ID)).guardar(ruta)
    a._pref.autoguardado = False
    assert a.desbloquear(str(ruta), CLAVE)["ok"]
    assert a.crear_grupo(None, "g")["ok"]
    ruta.write_bytes(ruta.read_bytes() + b"x")  # otro programa lo toca: el guardado se niega
    r = a.bloquear()
    assert r == {"ok": False, "error": "cambio_externo"}
    assert a._pp.limpiado == 1                   # el portapapeles se vacía igualmente
    assert a.info()["ok"]                        # y la base sigue abierta: la interfaz lo sabe
    assert a.bloquear(False)["ok"] and a.info()["error"] == "no_encontrado"


def test_ci_minimo_privilegio():
    yml = (Path(__file__).resolve().parent.parent / ".github/workflows/construir.yml").read_text(encoding="utf-8")
    cabecera = yml.split("jobs:")[0]
    assert "contents: read" in cabecera and "contents: write" not in cabecera
    assert yml.count("persist-credentials: false") == yml.count("actions/checkout@")
