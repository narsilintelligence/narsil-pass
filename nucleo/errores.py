"""Errores del núcleo. Los mensajes son para el registro; la interfaz traduce por clase."""


class ErrorKdbx(Exception):
    """Base de todos los errores al leer o escribir una base KDBX."""


class FormatoNoSoportado(ErrorKdbx):
    """El fichero es KeePass, pero de una versión o con un algoritmo que esta versión no maneja."""


class NoEsKdbx(ErrorKdbx):
    """El fichero no es una base de KeePass."""


class CredencialesIncorrectas(ErrorKdbx):
    """La contraseña o el fichero de clave no abren la base (falla la HMAC de la cabecera)."""


class FicheroDanado(ErrorKdbx):
    """La base está corrupta o ha sido manipulada (falla un hash o una HMAC de bloque)."""
