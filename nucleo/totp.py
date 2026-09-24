"""Códigos TOTP (RFC 6238) con los tres formatos de guardado que existen en bases KeePass:

- KeePassXC: atributo `otp` con una URI `otpauth://totp/...?secret=...&period=30&digits=6`.
- KeePassXC antiguo: `TOTP Seed` + `TOTP Settings` («30;6», o «30;S» para Steam).
- KeePass 2.47+: `TimeOtp-Secret-Base32` (o -Hex, -Base64, en claro) + -Length, -Period, -Algorithm.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import struct
import time
from dataclasses import dataclass
from urllib.parse import parse_qs, quote, urlparse

STEAM = "23456789BCDFGHJKMNPQRTVWXY"
ALGORITMOS = {"SHA1": hashlib.sha1, "SHA256": hashlib.sha256, "SHA512": hashlib.sha512}


@dataclass
class ConfigTotp:
    secreto: bytes
    periodo: int = 30
    digitos: int = 6
    algoritmo: str = "SHA1"
    steam: bool = False

    def __post_init__(self):
        # Viene de la base, que puede ser ajena: 10**digitos con digitos enorme congela la
        # aplicación, y un periodo 0 o negativo revienta el cálculo. Fuera de rango = sin TOTP.
        if not 1 <= self.digitos <= 10 or not 1 <= self.periodo <= 86400 * 365 \
                or self.algoritmo not in ALGORITMOS:
            raise ValueError("configuración TOTP fuera de rango")

    def codigo(self, instante: float | None = None) -> str:
        t = int((time.time() if instante is None else instante) // self.periodo)
        mac = hmac.new(self.secreto, struct.pack(">Q", t), ALGORITMOS[self.algoritmo]).digest()
        desplazamiento = mac[-1] & 0x0F
        numero = struct.unpack(">I", mac[desplazamiento:desplazamiento + 4])[0] & 0x7FFFFFFF
        if self.steam:
            letras = []
            for _ in range(5):
                letras.append(STEAM[numero % len(STEAM)])
                numero //= len(STEAM)
            return "".join(letras)
        return str(numero % (10 ** self.digitos)).zfill(self.digitos)

    def restante(self, instante: float | None = None) -> int:
        ahora = time.time() if instante is None else instante
        return self.periodo - int(ahora) % self.periodo

    def uri(self, etiqueta: str = "NARSIL Pass") -> str:
        secreto = base64.b32encode(self.secreto).decode("ascii").rstrip("=")
        extra = "&encoder=steam" if self.steam else ""
        return (f"otpauth://totp/{quote(etiqueta)}?secret={secreto}&period={self.periodo}"
                f"&digits={self.digitos}&algorithm={self.algoritmo}{extra}")


def _base32(texto: str) -> bytes:
    limpio = "".join(texto.split()).upper().rstrip("=")
    return base64.b32decode(limpio + "=" * (-len(limpio) % 8))


def leer(campos: dict[str, str]) -> ConfigTotp | None:
    """Configuración TOTP de una entrada, en cualquiera de los tres formatos; None si no tiene."""
    try:
        if campos.get("otp", "").strip():
            valor = campos["otp"].strip()
            if valor.lower().startswith("otpauth://"):
                u = urlparse(valor)
                q = {k: v[0] for k, v in parse_qs(u.query).items()}
                return ConfigTotp(_base32(q["secret"]), int(q.get("period", 30)), int(q.get("digits", 6)),
                                  q.get("algorithm", "SHA1").upper(), q.get("encoder", "").lower() == "steam")
            return ConfigTotp(_base32(valor))
        if campos.get("TOTP Seed", "").strip():
            ajustes = campos.get("TOTP Settings", "30;6").split(";")
            periodo = int(ajustes[0] or 30)
            steam = len(ajustes) > 1 and ajustes[1].strip().upper() == "S"
            digitos = 5 if steam else int(ajustes[1]) if len(ajustes) > 1 and ajustes[1].strip() else 6
            return ConfigTotp(_base32(campos["TOTP Seed"]), periodo, digitos, "SHA1", steam)
        secreto = None
        if campos.get("TimeOtp-Secret-Base32", "").strip():
            secreto = _base32(campos["TimeOtp-Secret-Base32"])
        elif campos.get("TimeOtp-Secret-Hex", "").strip():
            secreto = bytes.fromhex("".join(campos["TimeOtp-Secret-Hex"].split()))
        elif campos.get("TimeOtp-Secret-Base64", "").strip():
            secreto = base64.b64decode(campos["TimeOtp-Secret-Base64"])
        elif campos.get("TimeOtp-Secret", ""):
            secreto = campos["TimeOtp-Secret"].encode("utf-8")
        if secreto is not None:
            algoritmo = campos.get("TimeOtp-Algorithm", "HMAC-SHA-1").upper().replace("HMAC-", "").replace("-", "")
            return ConfigTotp(secreto, int(campos.get("TimeOtp-Period", 30) or 30),
                              int(campos.get("TimeOtp-Length", 6) or 6),
                              algoritmo if algoritmo in ALGORITMOS else "SHA1")
    except (ValueError, KeyError, base64.binascii.Error):
        return None
    return None
