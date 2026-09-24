"""Ida y vuelta con KeePassXC, el oráculo de compatibilidad.

1. NARSIL Pass crea una base KDBX 4 y KeePassXC la abre: mismos campos, contraseña incluida.
2. KeePassXC escribe sobre esa base (añade una entrada) y NARSIL Pass la lee.
3. Variantes: AES-256 / ChaCha20, Argon2d / Argon2id / AES-KDF, con y sin compresión, fichero de clave.

Se salta si `keepassxc-cli` no está instalado (solo existe en la máquina de desarrollo).
"""
from __future__ import annotations

import shutil
import subprocess

import pytest
from lxml import etree

from nucleo import cifrado, kdf
from nucleo.base import Base, campos_entrada
from nucleo.claves import fichero_clave_xml_v2
from nucleo.errores import CredencialesIncorrectas
from nucleo.formato import VD_BYTES, VD_UINT32, VD_UINT64, Variante

CLI = shutil.which("keepassxc-cli")
pytestmark = pytest.mark.skipif(CLI is None, reason="keepassxc-cli no instalado")

CLAVE = "Prueba-ñ-€-漢字 larga 2026"
CAMPOS = {
    "Title": "Cuenta de investigación",
    "UserName": "agente.norte",
    "Password": "p@ss «con» símbolos & <xml> ünïcödé",
    "URL": "https://ejemplo.es/login",
    "Notes": "Primera línea\nSegunda línea con tildes: áéíóú",
    "Alias": "Marta R.",
    "Teléfono": "+34 600 000 000",
}


def _kdf_rapido(tipo: bytes) -> Variante:
    v = Variante()
    v.poner(VD_BYTES, "$UUID", tipo)
    if tipo == kdf.UUID_AES_KDF:
        v.poner(VD_BYTES, "S", bytes(32))
        v.poner(VD_UINT64, "R", 1000)
    else:
        v.poner(VD_UINT32, "V", 0x13)
        v.poner(VD_BYTES, "S", bytes(32))
        v.poner(VD_UINT32, "P", 1)
        v.poner(VD_UINT64, "M", 8 * 1024 * 1024)
        v.poner(VD_UINT64, "I", 2)
    return v


def _cli(*args: str, entrada: str = "") -> str:
    r = subprocess.run([CLI, *args], input=entrada, capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, f"keepassxc-cli {args[0]} falló: {r.stderr.strip()}"
    return r.stdout


def _exportar(ruta, fichero_clave=None, contrasena=CLAVE) -> etree._Element:
    args = ["export", "-q", "-f", "xml"]
    if fichero_clave:
        args += ["-k", str(fichero_clave)]
    if contrasena is None:
        args.append("--no-password")
    salida = _cli(*args, str(ruta), entrada=(contrasena or "") + "\n")
    return etree.fromstring(salida.encode("utf-8"))


def _entradas_exportadas(xml: etree._Element) -> dict[str, dict[str, str]]:
    salida = {}
    for e in xml.iter("Entry"):
        if e.getparent().tag == "History":
            continue
        campos = {s.findtext("Key"): (s.findtext("Value") or "") for s in e.findall("String")}
        salida[e.findtext("UUID")] = campos
    return salida


@pytest.mark.parametrize("cifrado_id", [cifrado.UUID_CHACHA20, cifrado.UUID_AES256], ids=["chacha20", "aes256"])
@pytest.mark.parametrize("tipo_kdf", [kdf.UUID_ARGON2ID, kdf.UUID_ARGON2D, kdf.UUID_AES_KDF],
                         ids=["argon2id", "argon2d", "aeskdf"])
@pytest.mark.parametrize("compresion", [1, 0], ids=["gzip", "sin-compresion"])
def test_keepassxc_abre_lo_que_escribimos_y_nosotros_leemos_lo_que_escribe(tmp_path, cifrado_id, tipo_kdf, compresion):
    base = Base.nueva("Base de prueba", CLAVE, cifrado_id=cifrado_id, parametros_kdf=_kdf_rapido(tipo_kdf))
    base.compresion = compresion
    entrada = base.nueva_entrada(base.raiz, CAMPOS)
    uuid_nuestro = entrada.findtext("UUID")
    ruta = tmp_path / "base.kdbx"
    base.guardar(ruta)

    # 1. KeePassXC abre nuestra base y ve exactamente los mismos campos.
    exportadas = _entradas_exportadas(_exportar(ruta))
    assert exportadas[uuid_nuestro] == CAMPOS

    # 2. KeePassXC escribe sobre ella y nosotros leemos lo que ha escrito.
    _cli("add", "-q", "-u", "otro.usuario", "--url", "https://otra.es", "-p", str(ruta), "Añadida por KeePassXC",
         entrada=f"{CLAVE}\nclave-desde-keepassxc\n")
    releida = Base.abrir(ruta.read_bytes(), CLAVE)
    leidas = {e.findtext("UUID"): campos_entrada(e) for e in releida.entradas()}
    assert leidas[uuid_nuestro] == CAMPOS
    nuevas = [c for u, c in leidas.items() if u != uuid_nuestro]
    assert len(nuevas) == 1 and nuevas[0]["Password"] == "clave-desde-keepassxc"
    assert nuevas[0]["UserName"] == "otro.usuario"
    # Y lo que leemos coincide con lo que exporta KeePassXC, campo a campo.
    assert leidas == _entradas_exportadas(_exportar(ruta))


def test_fichero_de_clave_y_contrasena(tmp_path):
    clave_fichero = fichero_clave_xml_v2(bytes(range(32)))
    ruta_clave = tmp_path / "clave.keyx"
    ruta_clave.write_bytes(clave_fichero)
    base = Base.nueva("Con fichero", CLAVE, clave_fichero, parametros_kdf=_kdf_rapido(kdf.UUID_ARGON2ID))
    e = base.nueva_entrada(base.raiz, CAMPOS)
    ruta = tmp_path / "base.kdbx"
    base.guardar(ruta)
    assert _entradas_exportadas(_exportar(ruta, ruta_clave))[e.findtext("UUID")] == CAMPOS
    with pytest.raises(CredencialesIncorrectas):
        Base.abrir(ruta.read_bytes(), CLAVE)  # falta el fichero de clave
    assert campos_entrada(next(Base.abrir(ruta.read_bytes(), CLAVE, clave_fichero).entradas())) == CAMPOS


def test_contrasena_incorrecta(tmp_path):
    base = Base.nueva("x", CLAVE, parametros_kdf=_kdf_rapido(kdf.UUID_ARGON2ID))
    ruta = tmp_path / "b.kdbx"
    base.guardar(ruta)
    with pytest.raises(CredencialesIncorrectas):
        Base.abrir(ruta.read_bytes(), CLAVE + "x")


# ── KDBX 3.1 (el formato que crea keepassxc-cli y el de muchas bases antiguas) ───────────────────

def _base_31_de_keepassxc(tmp_path, contrasena=CLAVE):
    ruta = tmp_path / "v31.kdbx"
    _cli("db-create", "-q", "-p", "-t", "100", str(ruta), entrada=f"{contrasena}\n{contrasena}\n")
    _cli("add", "-q", "-u", "agente.31", "--url", "https://tres.es", "--notes", "Notas ñ 3.1", "-p", str(ruta),
         "Entrada de KeePassXC", entrada=f"{contrasena}\nclave-31-ñ\n")
    adjunto = tmp_path / "informe.txt"
    adjunto.write_bytes("Informe con acentos: áéíóú\n".encode("utf-8") * 50)
    _cli("attachment-import", "-q", str(ruta), "Entrada de KeePassXC", "informe.txt", str(adjunto),
         entrada=f"{contrasena}\n")
    return ruta, adjunto.read_bytes()


def test_kdbx31_de_keepassxc_se_lee(tmp_path):
    ruta, adjunto = _base_31_de_keepassxc(tmp_path)
    base = Base.abrir(ruta.read_bytes(), CLAVE)
    assert base.version_texto == "KDBX 3.1"
    leidas = {e.findtext("UUID"): campos_entrada(e) for e in base.entradas()}
    assert leidas == _entradas_exportadas(_exportar(ruta))
    entrada = next(e for e in base.entradas() if campos_entrada(e)["Title"] == "Entrada de KeePassXC")
    assert campos_entrada(entrada)["Password"] == "clave-31-ñ"
    ref = int(entrada.find("Binary/Value").get("Ref"))
    assert base.adjunto(ref) == adjunto


def test_kdbx31_se_guarda_en_31_y_keepassxc_lo_abre(tmp_path):
    ruta, adjunto = _base_31_de_keepassxc(tmp_path)
    base = Base.abrir(ruta.read_bytes(), CLAVE)
    nueva = base.nueva_entrada(base.raiz, CAMPOS)
    base.guardar(ruta)
    releida = Base.abrir(ruta.read_bytes(), CLAVE)
    assert releida.version_texto == "KDBX 3.1"  # respeta formato y versión
    exportadas = _entradas_exportadas(_exportar(ruta))
    assert exportadas[nueva.findtext("UUID")] == CAMPOS
    assert {e.findtext("UUID"): campos_entrada(e) for e in releida.entradas()} == exportadas
    # El adjunto sigue intacto para KeePassXC.
    salida = tmp_path / "salida.txt"
    _cli("attachment-export", "-q", str(ruta), "Entrada de KeePassXC", "informe.txt", str(salida), entrada=f"{CLAVE}\n")
    assert salida.read_bytes() == adjunto
    # Y KeePassXC puede seguir escribiendo encima.
    _cli("add", "-q", "-u", "tras.guardar", "-p", str(ruta), "Otra más", entrada=f"{CLAVE}\nx\n")
    assert any(campos_entrada(e)["Title"] == "Otra más" for e in Base.abrir(ruta.read_bytes(), CLAVE).entradas())


def test_kdbx31_se_convierte_a_4_sin_perder_nada(tmp_path):
    ruta, adjunto = _base_31_de_keepassxc(tmp_path)
    base = Base.abrir(ruta.read_bytes(), CLAVE)
    antes = _entradas_exportadas(_exportar(ruta))
    base.convertir_a_kdbx4(_kdf_rapido(kdf.UUID_ARGON2ID))
    base.guardar(ruta)
    assert Base.abrir(ruta.read_bytes(), CLAVE).version_texto == "KDBX 4.0"
    assert _entradas_exportadas(_exportar(ruta)) == antes
    salida = tmp_path / "salida.txt"
    _cli("attachment-export", "-q", str(ruta), "Entrada de KeePassXC", "informe.txt", str(salida), entrada=f"{CLAVE}\n")
    assert salida.read_bytes() == adjunto


def test_kdbx31_clave_incorrecta(tmp_path):
    ruta, _ = _base_31_de_keepassxc(tmp_path)
    with pytest.raises(CredencialesIncorrectas):
        Base.abrir(ruta.read_bytes(), "otra")
