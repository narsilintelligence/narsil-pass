"""Estructuras binarias de KDBX 4: cabeceras TLV, VariantDictionary y flujo de bloques con HMAC.

Referencia: formato KDBX 4.x de KeePass 2 (KdbxFile, VariantDictionary, HmacBlockStream), tal como
lo implementan KeePass y KeePassXC. Todos los enteros son little-endian.
"""
from __future__ import annotations

import hashlib
import hmac
import struct
from dataclasses import dataclass, field

from .errores import FicheroDanado, FormatoNoSoportado, NoEsKdbx

FIRMA_1 = 0x9AA2D903
FIRMA_2 = 0xB54BFB67
VERSION_3_1 = 0x00030001
VERSION_4_0 = 0x00040000
VERSION_4_1 = 0x00040001

# Campos de la cabecera exterior (KDBX 4).
CAB_FIN = 0
CAB_CIFRADO = 2
CAB_COMPRESION = 3
CAB_SEMILLA = 4
CAB_IV = 7
CAB_KDF = 11
CAB_DATOS_PUBLICOS = 12

# Campos exclusivos de KDBX 3.1 (en 4 pasaron a la KDF o a la cabecera interior).
CAB_COMENTARIO = 1
CAB_SEMILLA_TRANSFORMACION = 5
CAB_RONDAS = 6
CAB_CLAVE_FLUJO = 8
CAB_BYTES_INICIO = 9
CAB_FLUJO_ID = 10

# Campos de la cabecera interior.
INT_FIN = 0
INT_FLUJO_ID = 1
INT_FLUJO_CLAVE = 2
INT_ADJUNTO = 3

INDICE_CABECERA = 0xFFFFFFFFFFFFFFFF


# ── VariantDictionary ────────────────────────────────────────────────────────

VD_VERSION = 0x0100
VD_UINT32, VD_UINT64, VD_BOOL, VD_INT32, VD_INT64, VD_STRING, VD_BYTES = 0x04, 0x05, 0x08, 0x0C, 0x0D, 0x18, 0x42


@dataclass
class Variante:
    """Diccionario tipado de KDBX 4. Conserva orden y tipos para reescribirlo idéntico."""

    items: list[tuple[int, str, object]] = field(default_factory=list)

    def get(self, clave: str, defecto=None):
        for _, k, v in self.items:
            if k == clave:
                return v
        return defecto

    def poner(self, tipo: int, clave: str, valor) -> None:
        for i, (_, k, _) in enumerate(self.items):
            if k == clave:
                self.items[i] = (tipo, clave, valor)
                return
        self.items.append((tipo, clave, valor))

    @classmethod
    def leer(cls, datos: bytes) -> "Variante":
        if len(datos) < 2:
            raise FicheroDanado("VariantDictionary vacío")
        (version,) = struct.unpack_from("<H", datos, 0)
        if (version & 0xFF00) > (VD_VERSION & 0xFF00):
            raise FormatoNoSoportado(f"VariantDictionary versión {version:#06x}")
        pos, items = 2, []
        # Se lee antes de autenticar nada (la HMAC depende de la KDF que describe): todo tamaño se
        # valida y cualquier incoherencia es FicheroDanado, nunca un error de Python sin clasificar.
        try:
            while True:
                if pos >= len(datos):
                    raise FicheroDanado("VariantDictionary sin terminador")
                tipo = datos[pos]
                pos += 1
                if tipo == 0:
                    break
                (lk,) = struct.unpack_from("<i", datos, pos)
                pos += 4
                if lk < 0 or pos + lk > len(datos):
                    raise FicheroDanado("VariantDictionary truncado")
                clave = datos[pos:pos + lk].decode("utf-8")
                pos += lk
                (lv,) = struct.unpack_from("<i", datos, pos)
                pos += 4
                if lv < 0 or pos + lv > len(datos):
                    raise FicheroDanado("VariantDictionary truncado")
                bruto = datos[pos:pos + lv]
                pos += lv
                items.append((tipo, clave, _decodificar(tipo, bruto)))
        except (struct.error, UnicodeDecodeError) as e:
            raise FicheroDanado("VariantDictionary mal formado") from e
        return cls(items)

    def escribir(self) -> bytes:
        partes = [struct.pack("<H", VD_VERSION)]
        for tipo, clave, valor in self.items:
            k = clave.encode("utf-8")
            v = _codificar(tipo, valor)
            partes += [bytes([tipo]), struct.pack("<i", len(k)), k, struct.pack("<i", len(v)), v]
        partes.append(b"\x00")
        return b"".join(partes)


def _decodificar(tipo: int, b: bytes):
    if tipo == VD_UINT32:
        return struct.unpack("<I", b)[0]
    if tipo == VD_UINT64:
        return struct.unpack("<Q", b)[0]
    if tipo == VD_BOOL:
        return b != b"\x00"
    if tipo == VD_INT32:
        return struct.unpack("<i", b)[0]
    if tipo == VD_INT64:
        return struct.unpack("<q", b)[0]
    if tipo == VD_STRING:
        return b.decode("utf-8")
    return bytes(b)  # VD_BYTES y tipos desconocidos: se conservan tal cual


def _codificar(tipo: int, v) -> bytes:
    if tipo == VD_UINT32:
        return struct.pack("<I", v)
    if tipo == VD_UINT64:
        return struct.pack("<Q", v)
    if tipo == VD_BOOL:
        return b"\x01" if v else b"\x00"
    if tipo == VD_INT32:
        return struct.pack("<i", v)
    if tipo == VD_INT64:
        return struct.pack("<q", v)
    if tipo == VD_STRING:
        return v.encode("utf-8")
    return bytes(v)


# ── Cabeceras TLV ────────────────────────────────────────────────────────────

def leer_tlv(datos: bytes, pos: int, *, fin: int, ancho: int = 4) -> tuple[list[tuple[int, bytes]], int]:
    """Lee campos (id:1, tamaño, datos) hasta el campo `fin`, incluido. El tamaño ocupa 4 bytes en
    KDBX 4 y 2 bytes en la cabecera de KDBX 3.1. Devuelve (campos, posición)."""
    campos = []
    fmt = "<I" if ancho == 4 else "<H"
    while True:
        if pos + 1 + ancho > len(datos):
            raise FicheroDanado("cabecera truncada")
        ident = datos[pos]
        (tam,) = struct.unpack_from(fmt, datos, pos + 1)
        pos += 1 + ancho
        valor = datos[pos:pos + tam]
        if len(valor) != tam:
            raise FicheroDanado("campo de cabecera truncado")
        pos += tam
        campos.append((ident, bytes(valor)))
        if ident == fin:
            return campos, pos


def escribir_tlv(campos: list[tuple[int, bytes]], ancho: int = 4) -> bytes:
    fmt = "<I" if ancho == 4 else "<H"
    return b"".join(bytes([i]) + struct.pack(fmt, len(v)) + v for i, v in campos)


@dataclass
class CabeceraExterior:
    version: int
    campos: list[tuple[int, bytes]]
    bruta: bytes  # bytes exactos de firma + versión + campos, sobre los que va el hash y la HMAC

    def campo(self, ident: int) -> bytes | None:
        for i, v in self.campos:
            if i == ident:
                return v
        return None


def leer_cabecera(datos: bytes) -> tuple[CabeceraExterior, int]:
    if len(datos) < 12:
        raise NoEsKdbx("fichero demasiado corto")
    f1, f2, version = struct.unpack_from("<III", datos, 0)
    if f1 != FIRMA_1 or f2 != FIRMA_2:
        raise NoEsKdbx("firma KeePass ausente")
    mayor = version >> 16
    if mayor < 3:
        raise FormatoNoSoportado(f"KDBX {mayor}.x (anterior a KeePass 2.20)")
    if mayor > 4:
        raise FormatoNoSoportado(f"KDBX {mayor}.x")
    campos, pos = leer_tlv(datos, 12, fin=CAB_FIN, ancho=4 if mayor == 4 else 2)
    return CabeceraExterior(version, campos, bytes(datos[:pos])), pos


# ── Claves de la carga útil y HMAC ──────────────────────────────────────────

def clave_cifrado(semilla: bytes, clave_transformada: bytes) -> bytes:
    return hashlib.sha256(semilla + clave_transformada).digest()


def clave_hmac_base(semilla: bytes, clave_transformada: bytes) -> bytes:
    return hashlib.sha512(semilla + clave_transformada + b"\x01").digest()


def clave_bloque(base: bytes, indice: int) -> bytes:
    return hashlib.sha512(struct.pack("<Q", indice) + base).digest()


def hmac_cabecera(base: bytes, cabecera: bytes) -> bytes:
    return hmac.new(clave_bloque(base, INDICE_CABECERA), cabecera, hashlib.sha256).digest()


def leer_bloques(datos: bytes, pos: int, base: bytes) -> bytes:
    """Flujo HmacBlockStream: [HMAC 32][tamaño int32][datos]… hasta un bloque vacío."""
    partes, indice = [], 0
    while True:
        if pos + 36 > len(datos):
            raise FicheroDanado("flujo de bloques truncado")
        firma = datos[pos:pos + 32]
        (tam,) = struct.unpack_from("<i", datos, pos + 32)
        if tam < 0:
            raise FicheroDanado("tamaño de bloque negativo")
        cuerpo = datos[pos + 36:pos + 36 + tam]
        if len(cuerpo) != tam:
            raise FicheroDanado("bloque truncado")
        esperado = hmac.new(clave_bloque(base, indice),
                            struct.pack("<Qi", indice, tam) + cuerpo, hashlib.sha256).digest()
        if not hmac.compare_digest(esperado, firma):
            raise FicheroDanado(f"HMAC del bloque {indice} no coincide")
        pos += 36 + tam
        if tam == 0:
            return b"".join(partes)
        partes.append(bytes(cuerpo))
        indice += 1


def escribir_bloques(carga: bytes, base: bytes, tam_bloque: int = 1024 * 1024) -> bytes:
    partes, indice = [], 0
    trozos = [carga[i:i + tam_bloque] for i in range(0, len(carga), tam_bloque)] + [b""]
    for cuerpo in trozos:
        firma = hmac.new(clave_bloque(base, indice),
                         struct.pack("<Qi", indice, len(cuerpo)) + cuerpo, hashlib.sha256).digest()
        partes += [firma, struct.pack("<i", len(cuerpo)), cuerpo]
        indice += 1
    return b"".join(partes)


# ── Flujo de bloques con SHA-256 (KDBX 3.1) ──────────────────────────────────

def leer_bloques_sha(datos: bytes) -> bytes:
    """HashedBlockStream: [índice uint32][SHA-256 32][tamaño int32][datos]… hasta un bloque vacío."""
    partes, pos, esperado = [], 0, 0
    while True:
        if pos + 40 > len(datos):
            raise FicheroDanado("flujo de bloques truncado")
        indice, = struct.unpack_from("<I", datos, pos)
        suma = datos[pos + 4:pos + 36]
        tam, = struct.unpack_from("<i", datos, pos + 36)
        if indice != esperado or tam < 0:
            raise FicheroDanado("bloque fuera de orden")
        cuerpo = datos[pos + 40:pos + 40 + tam]
        if len(cuerpo) != tam:
            raise FicheroDanado("bloque truncado")
        pos += 40 + tam
        if tam == 0:
            if any(suma):
                raise FicheroDanado("bloque final con suma")
            return b"".join(partes)
        if hashlib.sha256(cuerpo).digest() != suma:
            raise FicheroDanado(f"SHA-256 del bloque {indice} no coincide")
        partes.append(bytes(cuerpo))
        esperado += 1


def escribir_bloques_sha(carga: bytes, tam_bloque: int = 1024 * 1024) -> bytes:
    partes, indice = [], 0
    for i in range(0, len(carga), tam_bloque):
        cuerpo = carga[i:i + tam_bloque]
        partes += [struct.pack("<I", indice), hashlib.sha256(cuerpo).digest(), struct.pack("<i", len(cuerpo)), cuerpo]
        indice += 1
    partes += [struct.pack("<I", indice), bytes(32), struct.pack("<i", 0)]
    return b"".join(partes)
