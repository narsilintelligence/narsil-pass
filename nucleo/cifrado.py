"""Cifrado de la carga útil (AES-256-CBC, ChaCha20) y flujo interior de valores protegidos."""
from __future__ import annotations

import hashlib
import uuid

from cryptography.hazmat.primitives import padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from .errores import FicheroDanado, FormatoNoSoportado

UUID_AES256 = uuid.UUID("31c1f2e6-bf71-4350-be58-05216afc5aff").bytes
UUID_CHACHA20 = uuid.UUID("d6038a2b-8b6f-4cb5-a524-339a31dbb59a").bytes
UUID_TWOFISH = uuid.UUID("ad68f29f-576f-4bb9-a36a-d47af965346c").bytes

NOMBRES = {UUID_AES256: "AES-256", UUID_CHACHA20: "ChaCha20", UUID_TWOFISH: "Twofish"}
TAM_IV = {UUID_AES256: 16, UUID_CHACHA20: 12}

FLUJO_SALSA20 = 2
FLUJO_CHACHA20 = 3


def _chacha(clave: bytes, iv12: bytes):
    # `cryptography` recibe 16 bytes: contador de 32 bits (0) seguido del nonce de 12 bytes.
    return Cipher(algorithms.ChaCha20(clave, b"\x00" * 4 + iv12), mode=None)


def descifrar(ident: bytes, clave: bytes, iv: bytes, datos: bytes) -> bytes:
    if ident == UUID_AES256:
        d = Cipher(algorithms.AES(clave), modes.CBC(iv)).decryptor()
        bruto = d.update(datos) + d.finalize()
        quitar = padding.PKCS7(128).unpadder()
        try:
            return quitar.update(bruto) + quitar.finalize()
        except ValueError as e:  # la HMAC ya pasó: un relleno roto es corrupción, no clave errónea
            raise FicheroDanado("relleno AES inválido") from e
    if ident == UUID_CHACHA20:
        d = _chacha(clave, iv).decryptor()
        return d.update(datos) + d.finalize()
    raise FormatoNoSoportado(f"cifrado {NOMBRES.get(ident, ident.hex())}")


def cifrar(ident: bytes, clave: bytes, iv: bytes, datos: bytes) -> bytes:
    if ident == UUID_AES256:
        poner = padding.PKCS7(128).padder()
        relleno = poner.update(datos) + poner.finalize()
        c = Cipher(algorithms.AES(clave), modes.CBC(iv)).encryptor()
        return c.update(relleno) + c.finalize()
    if ident == UUID_CHACHA20:
        c = _chacha(clave, iv).encryptor()
        return c.update(datos) + c.finalize()
    raise FormatoNoSoportado(f"cifrado {NOMBRES.get(ident, ident.hex())}")


NONCE_SALSA20 = bytes.fromhex("E830094B97205D2A")


class FlujoInterior:
    """Flujo de cifrado de los valores protegidos (contraseñas y campos marcados).

    Es un único flujo continuo: cada valor consume su longitud en orden de documento, así que se
    descifra y se recifra recorriendo el XML en el mismo orden que KeePass. ChaCha20 es el de KDBX 4;
    Salsa20, el de KDBX 3.1 (vía pycryptodomex, porque `cryptography` no lo incluye).
    """

    def __init__(self, ident: int, clave: bytes):
        if ident == FLUJO_CHACHA20:
            h = hashlib.sha512(clave).digest()
            self._c = _chacha(h[:32], h[32:44]).encryptor()
            self._aplicar = self._c.update
        elif ident == FLUJO_SALSA20:
            from Cryptodome.Cipher import Salsa20
            s = Salsa20.new(key=hashlib.sha256(clave).digest(), nonce=NONCE_SALSA20)
            self._aplicar = s.encrypt
        else:
            raise FormatoNoSoportado(f"flujo interior {ident}")

    def aplicar(self, datos: bytes) -> bytes:
        return self._aplicar(datos)
