"""Operaciones de edición, contrastadas con KeePassXC cuando está instalado."""
from __future__ import annotations

import shutil

import pytest

from nucleo import generador, totp
from nucleo.base import Base, campos_entrada
from nucleo.boveda import Boveda, CambioExterno
from nucleo import kdf
from tests.test_interoperabilidad import CLAVE, _cli, _entradas_exportadas, _exportar, _kdf_rapido

CLI = shutil.which("keepassxc-cli")


def _boveda(tmp_path) -> Boveda:
    ruta = tmp_path / "b.kdbx"
    base = Base.nueva("Pruebas", CLAVE, parametros_kdf=_kdf_rapido(kdf.UUID_ARGON2ID))
    b = Boveda(base=base, ruta=str(ruta))
    b._papelera("Papelera")
    b.guardar(forzar=True)
    return b


def _campos(**kw):
    return [{"clave": k, "valor": v, "protegido": k == "Password"} for k, v in kw.items()]


def test_crear_editar_historial_y_revelar(tmp_path):
    b = _boveda(tmp_path)
    u = b.crear_entrada(None, _campos(Title="Correo operativo", UserName="alias", Password="uno"), ["osint", "correo"])
    b.editar_entrada(u, _campos(Title="Correo operativo", UserName="alias", Password="dos"))
    d = b.entrada(u)
    assert [c["valor"] for c in d["campos"] if c["clave"] == "Password"] == [None]  # no sale en claro
    assert b.revelar(u, "Password") == "dos"
    assert len(d["historial"]) == 1 and b.revelar(u, "Password", historial=0) == "uno"
    b.restaurar_historial(u, 0)
    assert b.revelar(u, "Password") == "uno" and len(b.entrada(u)["historial"]) == 2
    b.guardar()
    if CLI:
        xml = _exportar(b.ruta)
        viva = next(e for e in xml.iter("Entry") if e.findtext("UUID") == u and e.getparent().tag != "History")
        assert len(viva.findall("History/Entry")) == 2  # KeePassXC ve el historial


def test_busqueda_sin_acentos_y_sin_contrasenas(tmp_path):
    b = _boveda(tmp_path)
    b.crear_entrada(None, _campos(Title="Teléfono de contacto", Password="secreto-unico"))
    assert [e["titulo"] for e in b.entradas(texto="telefono")] == ["Teléfono de contacto"]
    assert b.entradas(texto="secreto-unico") == []


def test_papelera_y_borrado_definitivo(tmp_path):
    b = _boveda(tmp_path)
    u = b.crear_entrada(None, _campos(Title="A borrar"))
    b.eliminar_entrada(u)
    assert b.entrada(u)["en_papelera"]
    assert b.entradas(texto="borrar") == []  # la búsqueda ignora la papelera
    b.eliminar_entrada(u)  # desde la papelera: definitivo
    assert all(e.findtext("UUID") != u for e in b.base.entradas())
    assert any(d.findtext("UUID") == u for d in b.base.xml.getroot().iter("DeletedObject"))
    b.guardar()
    if CLI:
        assert u not in _entradas_exportadas(_exportar(b.ruta))


def test_grupos(tmp_path):
    b = _boveda(tmp_path)
    g = b.crear_grupo(None, "Operación Norte")
    h = b.crear_grupo(g, "Fuentes")
    u = b.crear_entrada(h, _campos(Title="Fuente 1"))
    b.renombrar_grupo(h, "Fuentes abiertas")
    arbol = b.grupos()
    nombres = [x["nombre"] for x in arbol["hijos"]]
    assert nombres[-1] == "Papelera"  # la papelera queda al final
    with pytest.raises(Exception):
        b.mover_grupo(g, h)  # dentro de sí mismo
    b.eliminar_grupo(g)
    assert b.entrada(u)["en_papelera"]


def test_adjuntos_y_limpieza(tmp_path):
    b = _boveda(tmp_path)
    u = b.crear_entrada(None, _campos(Title="Con adjunto"))
    b.agregar_adjunto(u, "captura.png", b"\x89PNG" + bytes(200))
    assert b.leer_adjunto(u, "captura.png").startswith(b"\x89PNG")
    b.guardar()
    if CLI:
        salida = tmp_path / "out.bin"
        _cli("attachment-export", "-q", b.ruta, "Con adjunto", "captura.png", str(salida), entrada=f"{CLAVE}\n")
        assert salida.read_bytes() == b"\x89PNG" + bytes(200)


def test_cambio_externo_detectado(tmp_path):
    b = _boveda(tmp_path)
    b.crear_entrada(None, _campos(Title="x"))
    otra = Boveda.abrir(b.ruta, CLAVE)
    otra.crear_entrada(None, _campos(Title="desde otro programa"))
    otra.guardar()
    with pytest.raises(CambioExterno):
        b.guardar()


def test_31_mantiene_formato_al_editar(tmp_path):
    if not CLI:
        pytest.skip("keepassxc-cli no instalado")
    ruta = tmp_path / "v31.kdbx"
    _cli("db-create", "-q", "-p", "-t", "100", str(ruta), entrada=f"{CLAVE}\n{CLAVE}\n")
    b = Boveda.abrir(str(ruta), CLAVE)
    u = b.crear_entrada(None, _campos(Title="En 3.1", Password="p"))
    b.editar_entrada(u, _campos(Title="En 3.1", Password="q"), expira="2030-01-01T00:00:00+00:00")
    b.guardar()
    assert Base.abrir(ruta.read_bytes(), CLAVE).version_texto == "KDBX 3.1"
    exportada = _exportar(ruta)
    entrada = next(e for e in exportada.iter("Entry") if e.findtext("UUID") == u and e.getparent().tag != "History")
    assert entrada.findtext("Times/Expires") == "True" and entrada.findtext("Times/ExpiryTime").startswith("2030-01-01")


def test_totp_formatos():
    # Vector de la RFC 6238 (SHA1, secreto «12345678901234567890», t=59 → 94287082 con 8 dígitos).
    secreto = "GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ"
    cfg = totp.leer({"otp": f"otpauth://totp/x?secret={secreto}&digits=8&period=30"})
    assert cfg.codigo(59) == "94287082"
    assert totp.leer({"TOTP Seed": secreto, "TOTP Settings": "30;8"}).codigo(59) == "94287082"
    assert totp.leer({"TimeOtp-Secret-Base32": secreto, "TimeOtp-Length": "8"}).codigo(59) == "94287082"
    assert totp.leer({"Title": "sin totp"}) is None


def test_generador():
    c = generador.contrasena(20, simbolos=False, excluir_parecidos=True)
    assert len(c) == 20 and not set(c) & generador.PARECIDOS
    assert len(generador.frase(5, "·").split("·")) == 5
    assert generador.entropia_frase(6) > 77
