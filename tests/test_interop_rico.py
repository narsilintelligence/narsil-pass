"""Compatibilidad profunda con KeePassXC: una base rica creada por KeePassXC (historial, adjuntos,
etiquetas, campos protegidos, caducidad, AutoType, CustomData, subgrupos) pasa por NARSIL Pass y
KeePassXC la sigue viendo idéntica salvo lo que se editó a propósito. KeePassXC importa en 4.0; la
3.1 (adjuntos en Meta/Binaries) se prueba con una base creada por db-create y enriquecida con su CLI.

Es la prueba que importa para el usuario que migra: su base no pierde nada al abrirla aquí."""
from __future__ import annotations

import base64
import shutil

import pytest
from lxml import etree

from nucleo.base import Base
from nucleo.boveda import Boveda
from tests.test_interoperabilidad import CLAVE, _cli, _exportar

pytestmark = pytest.mark.skipif(shutil.which("keepassxc-cli") is None, reason="keepassxc-cli no instalado")

ADJUNTO = "Informe reservado\nlínea 2 · ñ €\n".encode("utf-8") * 40
B64 = lambda b: base64.b64encode(b).decode()  # noqa: E731
U1, U2, U3, UG1, UG2 = (B64(bytes([i]) * 16) for i in (1, 2, 3, 4, 5))


def _cadena(k, v, protegido=False):
    return f'<String><Key>{k}</Key><Value{" ProtectInMemory=\"True\"" if protegido else ""}>{v}</Value></String>'


def _version(titulo, clave, fecha):
    return (f"<Entry><UUID>{U1}</UUID><Times><LastModificationTime>{fecha}</LastModificationTime></Times>"
            f"{_cadena('Title', titulo)}{_cadena('UserName', 'agente')}{_cadena('Password', clave, True)}</Entry>")


XML = f"""<?xml version="1.0" encoding="utf-8" standalone="yes"?>
<KeePassFile><Meta><Generator>Prueba</Generator><DatabaseName>Base rica</DatabaseName>
<RecycleBinEnabled>True</RecycleBinEnabled>
<Binaries><Binary ID="0" Compressed="False">{B64(ADJUNTO)}</Binary></Binaries></Meta>
<Root><Group><UUID>{UG1}</UUID><Name>Raíz</Name>
 <Entry><UUID>{U1}</UUID><Tags>osint;humint</Tags>
  <Times><Expires>True</Expires><ExpiryTime>2031-05-06T07:08:09Z</ExpiryTime></Times>
  {_cadena('Title', 'Cuenta principal')}{_cadena('UserName', 'agente')}{_cadena('Password', 'v3-actual', True)}
  {_cadena('URL', 'https://ejemplo.es')}{_cadena('Notes', 'Notas &amp; &lt;xml&gt;\nsegunda línea')}
  {_cadena('Alias', 'Marta R.')}{_cadena('PIN', '4321', True)}
  <Binary><Key>informe.txt</Key><Value Ref="0"/></Binary>
  <AutoType><Enabled>True</Enabled><DataTransferObfuscation>0</DataTransferObfuscation>
   <DefaultSequence>{{USERNAME}}{{TAB}}{{PASSWORD}}{{ENTER}}</DefaultSequence>
   <Association><Window>Firefox - Ejemplo</Window><KeystrokeSequence/></Association></AutoType>
  <CustomData><Item><Key>plugin.x</Key><Value>valor opaco</Value></Item></CustomData>
  <History>{_version('Cuenta principal', 'v1', '2025-01-01T00:00:00Z')}{_version('Cuenta principal', 'v2', '2025-06-01T00:00:00Z')}</History>
 </Entry>
 <Group><UUID>{UG2}</UUID><Name>Operación Norte</Name>
  <Entry><UUID>{U2}</UUID>{_cadena('Title', 'A editar')}{_cadena('Password', 'x', True)}{_cadena('Notes', 'antes')}</Entry>
  <Entry><UUID>{U3}</UUID>{_cadena('Title', 'Intacta')}{_cadena('Password', 'y', True)}</Entry>
 </Group>
</Group></Root></KeePassFile>"""


def _adjunto(ruta, e, nombre) -> bytes:
    """El XML que exporta KeePassXC no lleva el contenido de los adjuntos: se piden uno a uno."""
    grupos = [g.findtext("Name") for g in e.iterancestors("Group")][::-1][1:]
    camino = "/".join([*grupos, e.findtext("String[Key='Title']/Value")])
    destino = ruta.with_suffix(".adjunto")
    _cli("attachment-export", "-q", str(ruta), camino, nombre, str(destino), entrada=f"{CLAVE}\n")
    return destino.read_bytes()


def _entrada(ruta, e) -> dict:
    return {
        "campos": {s.findtext("Key"): s.findtext("Value") or "" for s in e.findall("String")},
        "etiquetas": e.findtext("Tags") or "",
        "caduca": (e.findtext("Times/Expires"), e.findtext("Times/ExpiryTime")),
        "adjuntos": {b.findtext("Key"): _adjunto(ruta, e, b.findtext("Key")) for b in e.findall("Binary")},
        "autotype": etree.tostring(e.find("AutoType"), method="c14n") if e.find("AutoType") is not None else b"",
        "custom": {i.findtext("Key"): i.findtext("Value") for i in e.iterfind("CustomData/Item")
                   if i.findtext("Key") != "_LAST_MODIFIED"},  # sello que pone KeePassXC al exportar
        "historial": [{s.findtext("Key"): s.findtext("Value") or "" for s in h.findall("String")}
                      for h in e.findall("History/Entry")],
    }


def _foto(ruta) -> dict:
    xml = _exportar(ruta)
    entradas = {e.findtext("UUID"): _entrada(ruta, e) for e in xml.iter("Entry") if e.getparent().tag != "History"}
    grupos = {g.findtext("UUID"): g.findtext("Name") for g in xml.iter("Group")}
    return {"entradas": entradas, "grupos": grupos}


@pytest.fixture
def base_rica(tmp_path):
    origen = tmp_path / "rica.xml"
    origen.write_text(XML, encoding="utf-8")
    ruta = tmp_path / "rica.kdbx"
    _cli("import", "-q", "-p", "-t", "100", str(origen), str(ruta), entrada=f"{CLAVE}\n{CLAVE}\n")
    return ruta


def test_la_base_rica_llega_completa(base_rica):
    """Control de la propia prueba: KeePassXC ha importado todo lo que se pretende vigilar."""
    e = _foto(base_rica)["entradas"][U1]
    assert e["campos"]["PIN"] == "4321" and sorted(e["etiquetas"].replace(",", ";").split(";")) == ["humint", "osint"]
    assert e["adjuntos"]["informe.txt"] == ADJUNTO and len(e["historial"]) == 2 and e["custom"]
    assert b"Firefox - Ejemplo" in e["autotype"]


def test_editar_una_entrada_no_toca_nada_mas(base_rica):
    antes = _foto(base_rica)
    b = Boveda.abrir(str(base_rica), CLAVE)
    # Igual que el formulario (Api.para_editar): los protegidos se revelan antes de editar.
    campos = [{**c, "valor": b.revelar(U2, c["clave"]) if c["protegido"] else c["valor"]} for c in b.entrada(U2)["campos"]]
    for c in campos:
        if c["clave"] == "Notes":
            c["valor"] = "después"
    b.editar_entrada(U2, campos)
    b.guardar()
    assert Base.abrir(base_rica.read_bytes(), CLAVE).version_texto == "KDBX 4.0"

    despues = _foto(base_rica)
    assert despues["grupos"] == antes["grupos"]
    for uuid in (U1, U3):
        assert despues["entradas"][uuid] == antes["entradas"][uuid], f"cambió una entrada no editada: {uuid}"
    editada = despues["entradas"][U2]
    assert editada["campos"]["Notes"] == "después" and editada["campos"]["Password"] == "x"
    assert len(editada["historial"]) == len(antes["entradas"][U2]["historial"]) + 1
    assert editada["historial"][-1]["Notes"] == "antes"


def test_kdbx31_con_adjunto_e_historial(tmp_path):
    ruta = tmp_path / "v31.kdbx"
    _cli("db-create", "-q", "-p", "-t", "100", str(ruta), entrada=f"{CLAVE}\n{CLAVE}\n")
    _cli("add", "-q", "-u", "agente", "-p", str(ruta), "Con adjunto", entrada=f"{CLAVE}\nclave-1\nclave-1\n")
    fichero = tmp_path / "informe.txt"
    fichero.write_bytes(ADJUNTO)
    _cli("attachment-import", "-q", str(ruta), "Con adjunto", "informe.txt", str(fichero), entrada=f"{CLAVE}\n")
    assert Base.abrir(ruta.read_bytes(), CLAVE).version_texto == "KDBX 3.1"

    b = Boveda.abrir(str(ruta), CLAVE)
    uuid = next(e["uuid"] for e in b.entradas(None, "Con adjunto"))
    campos = [{**c, "valor": b.revelar(uuid, c["clave"]) if c["protegido"] else c["valor"]} for c in b.entrada(uuid)["campos"]]
    for c in campos:
        if c["clave"] == "Password":
            c["valor"] = "clave-2"
    b.editar_entrada(uuid, campos)
    b.guardar()

    assert Base.abrir(ruta.read_bytes(), CLAVE).version_texto == "KDBX 3.1"
    e = next(x for x in _exportar(ruta).iter("Entry") if x.getparent().tag != "History" and x.findtext("UUID") == uuid)
    assert _adjunto(ruta, e, "informe.txt") == ADJUNTO
    assert e.findtext("String[Key='Password']/Value") == "clave-2"
    assert [h.findtext("String[Key='Password']/Value") for h in e.findall("History/Entry")][-1] == "clave-1"


def test_kdbx31_con_adjunto_grande(tmp_path):
    """En 3.1 el adjunto va en base64 en un único nodo XML: 12 MB superan el tope por defecto de libxml2."""
    import os
    ruta = tmp_path / "grande.kdbx"
    _cli("db-create", "-q", "-p", "-t", "100", str(ruta), entrada=f"{CLAVE}\n{CLAVE}\n")
    _cli("add", "-q", "-u", "agente", str(ruta), "Con vídeo", entrada=f"{CLAVE}\n")
    datos = os.urandom(12 * 1024 * 1024)
    fichero = tmp_path / "video.bin"
    fichero.write_bytes(datos)
    _cli("attachment-import", "-q", str(ruta), "Con vídeo", "video.bin", str(fichero), entrada=f"{CLAVE}\n")
    b = Boveda.abrir(str(ruta), CLAVE)
    uuid = next(e["uuid"] for e in b.entradas(None, "Con vídeo"))
    assert b.leer_adjunto(uuid, "video.bin") == datos
    b.guardar(forzar=True)
    assert Boveda.abrir(str(ruta), CLAVE).leer_adjunto(uuid, "video.bin") == datos
