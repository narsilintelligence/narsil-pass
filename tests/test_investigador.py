"""Funciones para el investigador: secciones, identidades operativas con servicios y fotos, salud de
las contraseñas (repetidas, débiles, caducidad, renovación) y filtros. Contrastado con KeePassXC."""
from __future__ import annotations

import base64
import shutil
from datetime import datetime, timedelta, timezone

import pytest
import webview.util

from app.api import Api
from app.config import Preferencias
from nucleo import kdf
from nucleo.base import Base, texto_fecha_kdbx
from nucleo.boveda import CAMPO_TIPO, Boveda
from tests.test_interoperabilidad import CLAVE, _cli, _exportar, _kdf_rapido

CLI = shutil.which("keepassxc-cli")
PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==")


def _c(**kw):
    return [{"clave": k, "valor": v, "protegido": k == "Password" or k.endswith(".contrasena")} for k, v in kw.items()]


def _identidad(**extra):
    return _c(**{"Title": "Marta Ribas", CAMPO_TIPO: "identidad", "Ficha.nombre": "Marta", "Ficha.estado": "activa",
                 "Ficha.biografia": "Fotógrafa de viajes.", "Servicio.1.nombre": "Instagram",
                 "Servicio.1.url": "https://www.instagram.com/", "Servicio.1.usuario": "marta.viajes",
                 "Servicio.1.contrasena": "Compartida-2026!", "Servicio.2.nombre": "Correo",
                 "Servicio.2.usuario": "marta.ribas@correo.example", "Servicio.2.contrasena": "kH3!pQ9z#Lm2-x8Vr", **extra})


@pytest.fixture
def boveda(tmp_path):
    base = Base.nueva("Unidad", CLAVE, parametros_kdf=_kdf_rapido(kdf.UUID_ARGON2ID))
    b = Boveda(base=base, ruta=str(tmp_path / "u.kdbx"))
    b._papelera("Papelera")
    b.preparar_secciones({"interno": "Servicios internos", "externo": "Servicios externos",
                          "identidades": "Identidades operativas"})
    b.guardar(forzar=True)
    return b


def test_filtros_de_los_dialogos_son_validos_para_pywebview(tmp_path, monkeypatch):
    """«* (*.*)» no pasa la validación de pywebview y el diálogo no llegaría a abrirse."""
    monkeypatch.setenv("NARSIL_PASS_DATOS", str(tmp_path / "datos"))
    vistos = []

    def dialogos(tipo, **kw):
        for f in kw.get("file_types", ()):
            webview.util.parse_file_type(f)  # lanza ValueError si pywebview lo rechaza
            vistos.append(f)
        return None
    api = Api(preferencias=Preferencias(), dialogos=dialogos)
    for metodo in ("elegir_base", "elegir_fichero_clave", "elegir_destino", "crear_fichero_clave"):
        assert getattr(api, metodo)()["ok"], metodo
    ruta = tmp_path / "b.kdbx"
    Base.nueva("x", CLAVE, parametros_kdf=_kdf_rapido(kdf.UUID_ARGON2ID)).guardar(ruta)
    api.desbloquear(str(ruta), CLAVE)
    u = api.crear_entrada(None, _c(Title="t"))["uuid"]
    for metodo, args in (("agregar_adjunto", (u,)), ("agregar_imagenes", (u,)), ("guardar_adjunto", (u, "x")),
                         ("guardar_como", ())):
        assert getattr(api, metodo)(*args)["ok"], metodo
    assert len(vistos) >= 8


def test_secciones_se_guardan_y_sobreviven_a_keepassxc(boveda, tmp_path):
    secciones = boveda.secciones()
    assert all(secciones.values())
    nombres = {g["nombre"] for g in boveda.grupos()["hijos"]}
    assert {"Servicios internos", "Servicios externos", "Identidades operativas"} <= nombres
    if CLI:  # KeePassXC edita la base y la marca de secciones sigue ahí
        _cli("add", "-q", "-u", "x", boveda.ruta, "Desde KeePassXC", entrada=f"{CLAVE}\n")
    assert Boveda.abrir(boveda.ruta, CLAVE).secciones() == secciones
    otro = boveda.crear_grupo(None, "Proveedores")
    boveda.asignar_seccion("externo", otro)
    assert boveda.secciones()["externo"] == otro


def test_identidad_con_servicios_legible_en_keepassxc(boveda):
    u = boveda.crear_entrada(boveda.secciones()["identidades"], _identidad())
    boveda.guardar()
    r = boveda.entradas(boveda.secciones()["identidades"])[0]
    assert r["tipo"] == "identidad" and r["servicios"] == 2 and r["estado"] == "activa"
    assert "Compartida-2026!" not in repr(boveda.entrada(u))
    if CLI:
        e = next(x for x in _exportar(boveda.ruta).iter("Entry") if x.findtext("UUID") == u)
        campos = {s.findtext("Key"): s.findtext("Value") for s in e.findall("String")}
        assert campos["Servicio.1.contrasena"] == "Compartida-2026!" and campos["Ficha.biografia"] == "Fotógrafa de viajes."


def test_salud_repetidas_debiles_caducidad_y_renovacion(boveda):
    s = boveda.secciones()
    ident = boveda.crear_entrada(s["identidades"], _identidad())
    interna = boveda.crear_entrada(s["interno"], _c(Title="Intranet", UserName="analista", Password="Compartida-2026!"))
    debil = boveda.crear_entrada(s["externo"], _c(Title="Foro", UserName="x", Password="1234"))
    caduca = boveda.crear_entrada(s["externo"], _c(Title="Caducada", Password="Zq8!rT2#vB9$kL4m"),
                                  expira=(datetime.now(timezone.utc) - timedelta(days=1)).isoformat())
    pronto = boveda.crear_entrada(s["externo"], _c(Title="Pronto", Password="Hy7@pL3!xC6&nM1q"),
                                  expira=(datetime.now(timezone.utc) + timedelta(days=5)).isoformat())
    vieja = boveda.crear_entrada(s["interno"], _c(Title="Vieja", Password="Wm5#tR8!yU2@oP7s"))
    antes = texto_fecha_kdbx(datetime.now(timezone.utc) - timedelta(days=400))
    e = boveda._entrada(vieja)
    for etiqueta in ("CreationTime", "LastModificationTime"):
        e.find("Times/" + etiqueta).text = antes
    boveda._cambio()

    salud = boveda.salud()
    grupo = next(g for g in salud["repetidas"] if {r["uuid"] for r in g} == {ident, interna})
    assert {r["campo"] for r in grupo} == {"Servicio.1.contrasena", "Password"}
    assert [r["uuid"] for r in salud["debiles"]] == [debil]
    assert [r["uuid"] for r in salud["caducadas"]] == [caduca]
    assert [r["uuid"] for r in salud["por_caducar"]] == [pronto]
    assert [r["uuid"] for r in salud["renovar"]] == [vieja]
    assert "Compartida-2026!" not in repr(salud)

    # Cambiar la contraseña la saca de «renovar»; el historial guarda la vieja con su fecha.
    boveda.editar_entrada(vieja, _c(Title="Vieja", Password="Nueva-Larga-9!kQ2#vX"))
    assert vieja not in {r["uuid"] for r in boveda.salud()["renovar"]}
    # Editar otro campo sin tocar la contraseña NO la rejuvenece.
    boveda.editar_entrada(interna, _c(Title="Intranet 2", UserName="analista", Password="Compartida-2026!"))
    assert any({r["uuid"] for r in g} == {ident, interna} for g in boveda.salud()["repetidas"])
    boveda.fijar_renovar_dias(0)
    assert boveda.salud()["renovar"] == []


def test_edad_de_la_contrasena_no_cambia_al_editar_otro_campo(boveda):
    u = boveda.crear_entrada(None, _c(Title="a", Password="Wm5#tR8!yU2@oP7s"))
    e = boveda._entrada(u)
    antes = texto_fecha_kdbx(datetime.now(timezone.utc) - timedelta(days=300))
    e.find("Times/CreationTime").text = antes
    e.find("Times/LastModificationTime").text = antes
    boveda.editar_entrada(u, _c(Title="b", Password="Wm5#tR8!yU2@oP7s"))
    boveda.fijar_renovar_dias(200)
    assert u in {r["uuid"] for r in boveda.salud()["renovar"]}


def test_filtros_por_servicio_usuario_tipo_y_alerta(boveda):
    s = boveda.secciones()
    ident = boveda.crear_entrada(s["identidades"], _identidad())
    correo = boveda.crear_entrada(s["externo"], _c(Title="Correo", UserName="analista", URL="https://www.instagram.com/x",
                                                   Password="1234"))
    todo = lambda **f: {r["uuid"] for r in boveda.entradas(filtros=f)}  # noqa: E731
    assert todo(servicio="instagram.com") == {ident, correo}
    assert todo(servicio="correo") == {ident}
    assert todo(usuario="marta.viajes") == {ident}
    assert todo(tipo="identidad") == {ident}
    assert todo(estado="activa") == {ident}
    assert todo(alerta="debil") == {correo}
    assert todo(ambito=s["identidades"], servicio="instagram.com") == {ident}
    f = boveda.facetas()
    assert "instagram.com" in f["servicios"] and "correo" in f["servicios"] and "marta.viajes" in f["usuarios"]
    r = boveda.entradas(filtros={"tipo": "entrada"})
    assert {x["uuid"] for x in r} == {correo} and r[0]["alertas"] == ["debil"]


def test_fotos_en_bloque_numeradas_y_previsualizables(boveda):
    u = boveda.crear_entrada(boveda.secciones()["identidades"], _identidad())
    nombres = boveda.agregar_adjuntos(u, [("retrato.png", PNG), ("retrato.png", PNG), ("C:\\\\x\\\\perfil.jpg", b"\xff\xd8x")])
    assert nombres == ["retrato.png", "retrato (2).png", "perfil.jpg"]
    assert len(boveda._entrada(u).findall("History/Entry")) == 1  # una versión para todo el lote
    assert boveda.imagen(u, "retrato.png") == "data:image/png;base64," + base64.b64encode(PNG).decode()
    assert boveda.entradas(boveda.secciones()["identidades"])[0]["fotos"] == 3
    boveda.guardar()
    assert Boveda.abrir(boveda.ruta, CLAVE).leer_adjunto(u, "retrato (2).png") == PNG


def test_api_arrastrar_y_pegar_imagen(tmp_path, monkeypatch):
    monkeypatch.setenv("NARSIL_PASS_DATOS", str(tmp_path / "datos"))
    api = Api(preferencias=Preferencias(), dialogos=lambda *a, **k: None)
    ruta = tmp_path / "n.kdbx"
    r = api.crear_base(str(ruta), "Nueva", CLAVE)
    assert r["ok"] and all(r["info"]["secciones"].values())  # las bases nuevas nacen con secciones
    u = api.crear_entrada(r["info"]["secciones"]["identidades"], _identidad())["uuid"]
    assert api.agregar_adjunto_datos(u, "pegada.png", base64.b64encode(PNG).decode())["nombres"] == ["pegada.png"]
    assert api.agregar_adjunto_datos(u, "x.png", "no es base64!")["error"] == "permiso"
    assert api.imagen(u, "pegada.png")["url"].startswith("data:image/png;base64,")
    assert api.salud()["ok"] and api.facetas()["ok"]


def test_la_raiz_de_una_seccion_lista_tambien_sus_subgrupos(boveda):
    s = boveda.secciones()
    sub = boveda.crear_grupo(s["interno"], "Infraestructura")
    a = boveda.crear_entrada(s["interno"], _c(Title="Intranet"))
    b = boveda.crear_entrada(sub, _c(Title="VPN"))
    borrada = boveda.crear_entrada(sub, _c(Title="Vieja"))
    boveda.eliminar_entrada(borrada)
    assert {e["uuid"] for e in boveda.entradas(s["interno"])} == {a}
    assert {e["uuid"] for e in boveda.entradas(s["interno"], recursivo=True)} == {a, b}
    raiz = {e["uuid"] for e in boveda.entradas(None, recursivo=True)}
    assert borrada not in raiz and {a, b} <= raiz          # la papelera no se cuela en los listados
    assert borrada in {e["uuid"] for e in boveda.entradas(boveda.uuid_papelera, recursivo=True)}


def test_secciones_en_kdbx31(tmp_path):
    """Meta/CustomData existe también en KDBX 3.1: las secciones funcionan sin convertir la base."""
    if not CLI:
        pytest.skip("keepassxc-cli no instalado")
    ruta = tmp_path / "v31.kdbx"
    _cli("db-create", "-q", "-p", "-t", "100", str(ruta), entrada=f"{CLAVE}\n{CLAVE}\n")
    b = Boveda.abrir(str(ruta), CLAVE)
    s = b.preparar_secciones({"interno": "Internos", "externo": "Externos", "identidades": "Identidades"})
    b.crear_entrada(s["identidades"], _identidad())
    b.guardar()
    assert Base.abrir(ruta.read_bytes(), CLAVE).version_texto == "KDBX 3.1"
    _cli("add", "-q", "-u", "x", str(ruta), "Desde KeePassXC", entrada=f"{CLAVE}\n")   # KeePassXC la reescribe
    otra = Boveda.abrir(str(ruta), CLAVE)
    assert otra.secciones() == s
    assert otra.entradas(s["identidades"])[0]["tipo"] == "identidad"


def test_misma_cuenta_anotada_dos_veces_no_es_repetida(boveda):
    """La cuenta principal de una identidad y su servicio de correo (mismo usuario y clave) son una sola
    cuenta; la misma clave en dos servicios con usuarios distintos sí es reutilización."""
    s = boveda.secciones()["identidades"]
    u = boveda.crear_entrada(s, _c(**{"Title": "Ana", CAMPO_TIPO: "identidad", "UserName": "ana@correo.example", "Password": "Clave-Ana-2026!x",
                                      "Servicio.1.nombre": "Correo", "Servicio.1.usuario": "ANA@correo.example ",
                                      "Servicio.1.contrasena": "Clave-Ana-2026!x"}))
    assert boveda.salud()["repetidas"] == []
    boveda.editar_entrada(u, _c(**{"Title": "Ana", CAMPO_TIPO: "identidad", "UserName": "ana@correo.example", "Password": "Clave-Ana-2026!x",
                                   "Servicio.1.nombre": "Correo", "Servicio.1.usuario": "ana@correo.example", "Servicio.1.contrasena": "Clave-Ana-2026!x",
                                   "Servicio.2.nombre": "Foro", "Servicio.2.usuario": "ana_foro", "Servicio.2.contrasena": "Clave-Ana-2026!x"}))
    grupo = boveda.salud()["repetidas"][0]
    assert len(grupo) == 2 and {r["campo"] for r in grupo} == {"Password", "Servicio.2.contrasena"}
