"""Portapapeles con borrado automático.

- Tras N segundos se vacía, pero solo si sigue conteniendo lo que copiamos (si el usuario ha copiado
  otra cosa entretanto, no se le toca).
- En Windows se marca para que NO entre en el historial del portapapeles (Win+V) ni en el
  portapapeles en la nube, como hace KeePassXC.
- En Linux se usa GTK (el mismo motor de la ventana), siempre desde su hilo principal.
Si no hay implementación nativa, `disponible()` es False y la interfaz copia por su cuenta.
"""
from __future__ import annotations

import ctypes
import hashlib
import logging
import sys
import threading

registro = logging.getLogger(__name__)


class _Windows:
    CF_UNICODETEXT = 13
    GMEM_MOVEABLE = 0x0002

    def __init__(self):
        from ctypes import wintypes
        self.u32 = ctypes.WinDLL("user32", use_last_error=True)
        self.k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        self.u32.OpenClipboard.argtypes = [wintypes.HWND]
        self.u32.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]
        self.u32.SetClipboardData.restype = wintypes.HANDLE
        self.u32.GetClipboardData.argtypes = [wintypes.UINT]
        self.u32.GetClipboardData.restype = wintypes.HANDLE
        self.u32.RegisterClipboardFormatW.argtypes = [wintypes.LPCWSTR]
        self.u32.RegisterClipboardFormatW.restype = wintypes.UINT
        self.k32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
        self.k32.GlobalAlloc.restype = wintypes.HGLOBAL
        self.k32.GlobalLock.argtypes = [wintypes.HGLOBAL]
        self.k32.GlobalLock.restype = ctypes.c_void_p
        self.k32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
        self.excluir = [self.u32.RegisterClipboardFormatW(n) for n in (
            "ExcludeClipboardContentFromMonitorProcessing", "CanIncludeInClipboardHistory",
            "CanUploadToCloudClipboard")]

    def _bloque(self, datos: bytes):
        h = self.k32.GlobalAlloc(self.GMEM_MOVEABLE, len(datos))
        p = self.k32.GlobalLock(h)
        ctypes.memmove(p, datos, len(datos))
        self.k32.GlobalUnlock(h)
        return h

    def escribir(self, texto: str) -> None:
        if not self.u32.OpenClipboard(None):
            raise OSError("portapapeles ocupado")
        try:
            self.u32.EmptyClipboard()
            self.u32.SetClipboardData(self.CF_UNICODETEXT, self._bloque((texto + "\0").encode("utf-16-le")))
            # Presencia del primer formato = no monitorizar; los otros dos, DWORD 0 = no permitido.
            self.u32.SetClipboardData(self.excluir[0], self._bloque(b""))
            for fmt in self.excluir[1:]:
                self.u32.SetClipboardData(fmt, self._bloque(b"\0\0\0\0"))
        finally:
            self.u32.CloseClipboard()

    def leer(self) -> str | None:
        if not self.u32.OpenClipboard(None):
            return None
        try:
            h = self.u32.GetClipboardData(self.CF_UNICODETEXT)
            if not h:
                return None
            p = self.k32.GlobalLock(h)
            try:
                return ctypes.wstring_at(p)
            finally:
                self.k32.GlobalUnlock(h)
        finally:
            self.u32.CloseClipboard()

    def vaciar(self) -> None:
        if self.u32.OpenClipboard(None):
            try:
                self.u32.EmptyClipboard()
            finally:
                self.u32.CloseClipboard()


class _Gtk:
    def __init__(self):
        import gi
        gi.require_version("Gtk", "3.0")
        gi.require_version("Gdk", "3.0")
        from gi.repository import Gdk, GLib, Gtk
        self.Gdk, self.GLib, self.Gtk = Gdk, GLib, Gtk

    def _en_hilo_principal(self, fn):
        hecho, resultado = threading.Event(), {}

        def envoltura():
            try:
                resultado["v"] = fn()
            finally:
                hecho.set()
            return False
        self.GLib.idle_add(envoltura)
        hecho.wait(2.0)
        return resultado.get("v")

    def _cp(self):
        return self.Gtk.Clipboard.get(self.Gdk.SELECTION_CLIPBOARD)

    def escribir(self, texto: str) -> None:
        def fn():
            cp = self._cp()
            # Sin cp.store(): no se entrega el secreto al gestor de portapapeles del escritorio para
            # que sobreviva al cierre de la aplicación.
            cp.set_text(texto, -1)
        self._en_hilo_principal(fn)

    def leer(self) -> str | None:
        return self._en_hilo_principal(lambda: self._cp().wait_for_text())

    def vaciar(self) -> None:
        self._en_hilo_principal(lambda: self._cp().set_text("", -1))


class Portapapeles:
    def __init__(self):
        self._impl = None
        self._temporizador: threading.Timer | None = None
        self._huella: str | None = None
        try:
            self._impl = _Windows() if sys.platform == "win32" else _Gtk()
        except Exception as e:  # sin motor nativo: la interfaz copia por su cuenta
            registro.info("portapapeles nativo no disponible: %s", type(e).__name__)

    def disponible(self) -> bool:
        return self._impl is not None

    def copiar(self, texto: str, segundos: int) -> None:
        if self._impl is None:
            raise OSError("portapapeles no disponible")
        self._impl.escribir(texto)
        self._huella = hashlib.sha256(texto.encode("utf-8")).hexdigest()
        if self._temporizador:
            self._temporizador.cancel()
        self._temporizador = threading.Timer(segundos, self._limpiar)
        self._temporizador.daemon = True
        self._temporizador.start()

    def _limpiar(self) -> None:
        try:
            actual = self._impl.leer()
            if actual is not None and hashlib.sha256(actual.encode("utf-8")).hexdigest() == self._huella:
                self._impl.vaciar()
        except Exception:
            registro.warning("no se pudo vaciar el portapapeles", exc_info=True)
        finally:
            self._huella = None

    def limpiar_ya(self) -> None:
        """Al bloquear o cerrar: fuera lo que hubiéramos copiado."""
        if self._temporizador:
            self._temporizador.cancel()
        if self._huella and self._impl:
            self._limpiar()
