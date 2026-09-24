"""Funciones de derivación de clave de KDBX 4: Argon2d, Argon2id y AES-KDF.

Argon2 lo calcula argon2-cffi (la implementación de referencia); AES-KDF, `cryptography`.
"""
from __future__ import annotations

import hashlib
import os
import time
import uuid

from argon2.low_level import Type, hash_secret_raw
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from argon2.exceptions import HashingError

from .errores import FicheroDanado, FormatoNoSoportado
from .formato import VD_BYTES, VD_UINT32, VD_UINT64, Variante

UUID_AES_KDF = uuid.UUID("c9d9f39a-628a-4460-bf74-0d08c18a4fea").bytes
UUID_ARGON2D = uuid.UUID("ef636ddf-8c29-444b-91f7-a9a403e30a0c").bytes
UUID_ARGON2ID = uuid.UUID("9e298b19-56db-4773-b23d-fc3ec6f0a1e6").bytes

NOMBRES = {UUID_AES_KDF: "AES-KDF", UUID_ARGON2D: "Argon2d", UUID_ARGON2ID: "Argon2id"}


def transformar(compuesta: bytes, parametros: Variante) -> bytes:
    """Aplica la KDF de la base a la clave compuesta y devuelve la clave transformada (32 bytes)."""
    ident = parametros.get("$UUID")
    if ident in (UUID_ARGON2D, UUID_ARGON2ID):
        if parametros.get("K") or parametros.get("A"):
            raise FormatoNoSoportado("Argon2 con clave secreta o datos asociados")
        sal, memoria = parametros.get("S"), parametros.get("M")
        iteraciones, hilos, version = parametros.get("I"), parametros.get("P"), parametros.get("V", 0x13)
        # Parámetros leídos de la cabecera antes de autenticarla: se validan tipo y rango mínimo.
        if (not isinstance(sal, bytes) or len(sal) < 8 or not all(isinstance(x, int) for x in
                (memoria, iteraciones, hilos, version)) or iteraciones < 1 or not 1 <= hilos <= 0xFFFFFF
                or version not in (0x10, 0x13) or memoria < 8 * 1024 * hilos):
            raise FicheroDanado("parámetros de Argon2 inválidos")
        if memoria % 1024:
            raise FormatoNoSoportado("memoria de Argon2 no múltiplo de 1 KiB")
        try:
            return hash_secret_raw(
                secret=compuesta,
                salt=sal,
                time_cost=iteraciones,
                memory_cost=memoria // 1024,
                parallelism=hilos,
                hash_len=32,
                type=Type.D if ident == UUID_ARGON2D else Type.ID,
                version=version,
            )
        except (HashingError, OverflowError) as e:
            raise FicheroDanado("parámetros de Argon2 no admitidos") from e
    if ident == UUID_AES_KDF:
        if not isinstance(parametros.get("S"), bytes) or len(parametros.get("S")) != 32 \
                or not isinstance(parametros.get("R"), int) or parametros.get("R") < 0:
            raise FicheroDanado("parámetros de AES-KDF inválidos")
        cifrador = Cipher(algorithms.AES(parametros.get("S")), modes.ECB()).encryptor()
        clave = compuesta
        for _ in range(int(parametros.get("R"))):
            clave = cifrador.update(clave)
        return hashlib.sha256(clave).digest()
    raise FormatoNoSoportado("función de derivación de clave desconocida")


def renovar_sal(parametros: Variante) -> None:
    """Sal nueva para la KDF: al cambiar la clave maestra o los parámetros (como KeePassXC)."""
    parametros.poner(VD_BYTES, "S", os.urandom(32))


def argon2id_por_defecto(memoria_mib: int = 64, paralelismo: int = 2, iteraciones: int = 10) -> Variante:
    v = Variante()
    v.poner(VD_BYTES, "$UUID", UUID_ARGON2ID)
    v.poner(VD_UINT32, "V", 0x13)
    v.poner(VD_BYTES, "S", os.urandom(32))
    v.poner(VD_UINT32, "P", paralelismo)
    v.poner(VD_UINT64, "M", memoria_mib * 1024 * 1024)
    v.poner(VD_UINT64, "I", iteraciones)
    return v


def calibrar_iteraciones(objetivo_s: float = 1.0, memoria_mib: int = 64, paralelismo: int = 2) -> int:
    """Iteraciones de Argon2id para que desbloquear tarde unos `objetivo_s` segundos en este equipo."""
    prueba = argon2id_por_defecto(memoria_mib, paralelismo, 2)
    t0 = time.perf_counter()
    transformar(b"\x00" * 32, prueba)
    por_iteracion = max((time.perf_counter() - t0) / 2, 1e-4)
    return max(2, int(objetivo_s / por_iteracion))
