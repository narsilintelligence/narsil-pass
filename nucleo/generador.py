"""Generador de contraseñas y frases de paso con `secrets` (azar criptográfico del sistema)."""
from __future__ import annotations

import math
import secrets
import string
from functools import lru_cache
from pathlib import Path

MINUSCULAS = string.ascii_lowercase
MAYUSCULAS = string.ascii_uppercase
DIGITOS = string.digits
SIMBOLOS = "!\"#$%&'()*+,-./:;<=>?@[\\]^_`{|}~"
PARECIDOS = set("Il1O0o|`'\"")


@lru_cache(maxsize=1)
def palabras() -> tuple[str, ...]:
    ruta = Path(__file__).with_name("datos") / "eff_large.txt"
    return tuple(p for p in ruta.read_text(encoding="utf-8").split() if p)


def contrasena(longitud: int = 24, minusculas: bool = True, mayusculas: bool = True, digitos: bool = True,
               simbolos: bool = True, excluir_parecidos: bool = False) -> str:
    grupos = [g for g, activo in ((MINUSCULAS, minusculas), (MAYUSCULAS, mayusculas), (DIGITOS, digitos),
                                  (SIMBOLOS, simbolos)) if activo]
    if not grupos:
        raise ValueError("elige al menos un tipo de carácter")
    if excluir_parecidos:
        grupos = ["".join(c for c in g if c not in PARECIDOS) for g in grupos]
    longitud = max(longitud, len(grupos))
    todos = "".join(grupos)
    # Al menos un carácter de cada grupo elegido, en posiciones al azar.
    elegidos = [secrets.choice(g) for g in grupos] + [secrets.choice(todos) for _ in range(longitud - len(grupos))]
    for i in range(len(elegidos) - 1, 0, -1):
        j = secrets.randbelow(i + 1)
        elegidos[i], elegidos[j] = elegidos[j], elegidos[i]
    return "".join(elegidos)


def frase(n_palabras: int = 6, separador: str = "-", mayuscula_inicial: bool = False, con_numero: bool = False) -> str:
    lista = palabras()
    trozos = [secrets.choice(lista) for _ in range(max(n_palabras, 1))]
    if mayuscula_inicial:
        trozos = [t.capitalize() for t in trozos]
    if con_numero:
        trozos[secrets.randbelow(len(trozos))] += str(secrets.randbelow(10))
    return separador.join(trozos)


def entropia_contrasena(longitud: int, minusculas=True, mayusculas=True, digitos=True, simbolos=True,
                        excluir_parecidos=False) -> float:
    alfabeto = "".join(g for g, a in ((MINUSCULAS, minusculas), (MAYUSCULAS, mayusculas), (DIGITOS, digitos),
                                      (SIMBOLOS, simbolos)) if a)
    if excluir_parecidos:
        alfabeto = "".join(c for c in alfabeto if c not in PARECIDOS)
    return longitud * math.log2(len(set(alfabeto))) if alfabeto else 0.0


def entropia_frase(n_palabras: int) -> float:
    return n_palabras * math.log2(len(palabras()))


def entropia_estimada(texto: str) -> float:
    """Estimación prudente para una contraseña escrita a mano (sin diccionarios): alfabeto × longitud,
    penalizando repeticiones. Sirve para la barra de calidad, no como garantía."""
    if not texto:
        return 0.0
    alfabeto = 0
    if any(c in MINUSCULAS for c in texto):
        alfabeto += 26
    if any(c in MAYUSCULAS for c in texto):
        alfabeto += 26
    if any(c in DIGITOS for c in texto):
        alfabeto += 10
    if any(c in SIMBOLOS for c in texto):
        alfabeto += len(SIMBOLOS)
    if any(ord(c) > 127 for c in texto):
        alfabeto += 64
    distintos = len(set(texto))
    return min(len(texto), distintos * 2) * math.log2(max(alfabeto, 2))
