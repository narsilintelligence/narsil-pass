"""Clave compuesta de KeePass: contraseña y/o fichero de clave.

Cada componente aporta 32 bytes y la clave compuesta es el SHA-256 de su concatenación, en el orden
de KeePass: primero la contraseña, después el fichero de clave.
"""
from __future__ import annotations

import base64
import binascii
import hashlib
import re

from lxml import etree

from .errores import ErrorKdbx


class FicheroClaveInvalido(ErrorKdbx):
    """El fichero de clave XML está mal formado o su suma de control no coincide."""


def componente_contrasena(contrasena: str) -> bytes:
    return hashlib.sha256(contrasena.encode("utf-8")).digest()


def componente_fichero(contenido: bytes) -> bytes:
    """Interpreta un fichero de clave como lo hacen KeePass y KeePassXC.

    XML v2.0 (hex con suma de control), XML v1.0 (base64), 32 bytes en bruto, 64 caracteres
    hexadecimales o, en cualquier otro caso, el SHA-256 del contenido.
    """
    if contenido.lstrip().startswith(b"<"):
        clave = _fichero_xml(contenido)
        if clave is not None:
            return clave
    if len(contenido) == 32:
        return bytes(contenido)
    if len(contenido) == 64 and re.fullmatch(rb"[0-9A-Fa-f]{64}", contenido):
        return bytes.fromhex(contenido.decode("ascii"))
    return hashlib.sha256(contenido).digest()


def _fichero_xml(contenido: bytes) -> bytes | None:
    try:
        raiz = etree.fromstring(contenido, etree.XMLParser(resolve_entities=False, no_network=True))
    except etree.XMLSyntaxError:
        return None
    if raiz.tag != "KeyFile":
        return None
    version = (raiz.findtext("Meta/Version") or "").strip()
    dato = raiz.find("Key/Data")
    if dato is None:
        raise FicheroClaveInvalido("fichero de clave XML sin Key/Data")
    texto = "".join((dato.text or "").split())
    if version.startswith("2."):
        try:
            clave = bytes.fromhex(texto)
        except ValueError as e:
            raise FicheroClaveInvalido("Key/Data no es hexadecimal") from e
        suma = dato.get("Hash")
        if suma and hashlib.sha256(clave).digest()[:4].hex().upper() != suma.strip().upper():
            raise FicheroClaveInvalido("la suma de control del fichero de clave no coincide")
        return clave
    if version.startswith("1."):
        try:
            return base64.b64decode(texto, validate=True)
        except binascii.Error as e:
            raise FicheroClaveInvalido("Key/Data no es base64") from e
    return None


def clave_compuesta(contrasena: str | None = None, fichero: bytes | None = None) -> bytes:
    """Devuelve los 32 bytes de la clave compuesta. Exige al menos un componente."""
    partes = []
    if contrasena is not None:
        partes.append(componente_contrasena(contrasena))
    if fichero is not None:
        partes.append(componente_fichero(fichero))
    if not partes:
        raise ValueError("hace falta contraseña, fichero de clave o ambos")
    return hashlib.sha256(b"".join(partes)).digest()


def fichero_clave_xml_v2(clave: bytes) -> bytes:
    """Genera un fichero de clave XML v2.0 como los de KeePassXC (para crear bases nuevas)."""
    hexa = clave.hex().upper()
    grupos = " ".join(hexa[i:i + 8] for i in range(0, len(hexa), 8))
    suma = hashlib.sha256(clave).digest()[:4].hex().upper()
    return (
        '<?xml version="1.0" encoding="utf-8"?>\n<KeyFile>\n\t<Meta>\n\t\t<Version>2.0</Version>\n'
        f'\t</Meta>\n\t<Key>\n\t\t<Data Hash="{suma}">\n\t\t\t{grupos}\n\t\t</Data>\n\t</Key>\n</KeyFile>\n'
    ).encode("utf-8")
