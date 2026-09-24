"""El puente de la ventana: errores traducidos, autoguardado, portapapeles y valores protegidos."""
from __future__ import annotations

import pytest

from app.api import Api
from app.config import Preferencias
from nucleo import kdf
from nucleo.base import Base
from tests.test_interoperabilidad import CLAVE, _kdf_rapido


@pytest.fixture
def entorno(tmp_path, monkeypatch):
    monkeypatch.setenv("NARSIL_PASS_DATOS", str(tmp_path / "datos"))
    ruta = tmp_path / "b.kdbx"
    base = Base.nueva("Pruebas", CLAVE, parametros_kdf=_kdf_rapido(kdf.UUID_ARGON2ID))
    base.nueva_entrada(base.raiz, {"Title": "Correo", "UserName": "alias", "Password": "secreta"})
    base.guardar(ruta)
    elecciones = {}
    api = Api(preferencias=Preferencias(), dialogos=lambda tipo, **kw: elecciones.get(tipo))
    return api, ruta, elecciones


def test_desbloqueo_y_errores(entorno):
    api, ruta, _ = entorno
    assert api.desbloquear(str(ruta), "mala") == {"ok": False, "error": "credenciales"}
    assert api.desbloquear(str(ruta) + ".no", CLAVE)["error"] == "no_existe"
    r = api.desbloquear(str(ruta), CLAVE)
    assert r["ok"] and r["info"]["formato"] == "KDBX 4.0"
    assert api.estado()["recientes"] == [str(ruta)]


def test_contrasenas_no_salen_en_listados(entorno):
    api, ruta, _ = entorno
    api.desbloquear(str(ruta), CLAVE)
    lista = api.entradas()["lista"]
    detalle = api.entrada(lista[0]["uuid"])["entrada"]
    assert "secreta" not in repr(lista) and "secreta" not in repr(detalle)
    assert api.revelar(lista[0]["uuid"], "Password")["valor"] == "secreta"


def test_autoguardado_tras_cambio(entorno):
    api, ruta, _ = entorno
    api.desbloquear(str(ruta), CLAVE)
    r = api.crear_entrada(None, [{"clave": "Title", "valor": "Nueva"}, {"clave": "Password", "valor": "x", "protegido": True}])
    assert r["ok"] and r["cambios"] is False
    otra = Base.abrir(ruta.read_bytes(), CLAVE)
    assert any(e.findtext("String/Value") for e in otra.entradas())
    assert len(list(otra.entradas())) == 2


def test_bloquear_descarta_la_base(entorno):
    api, ruta, _ = entorno
    api.desbloquear(str(ruta), CLAVE)
    api.bloquear()
    assert api.entradas() == {"ok": False, "error": "no_encontrado"}


def test_crear_base_y_fichero_de_clave(entorno, tmp_path):
    api, _, elecciones = entorno
    elecciones["guardar"] = str(tmp_path / "clave.keyx")
    clave = api.crear_fichero_clave()["ruta"]
    nueva = tmp_path / "nueva.kdbx"
    r = api.crear_base(str(nueva), "Nueva", "otra-clave", clave)
    assert r["ok"] and nueva.exists()
    assert api.crear_base(str(nueva), "x", "y")["error"] == "permiso"  # nunca sobrescribe


def test_generador(entorno):
    api, _, _ = entorno
    assert len(api.generar({"longitud": 32})["texto"]) == 32
    assert api.generar({"modo": "frase", "palabras": 5})["bits"] >= 64
