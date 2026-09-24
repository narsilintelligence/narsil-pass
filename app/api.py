"""Puente entre la interfaz (JavaScript en la ventana) y el núcleo. Lo expone pywebview como
`window.pywebview.api`, sin servidor ni puerto: la única vía de entrada es la propia ventana.

Cada método devuelve `{"ok": True, ...}` o `{"ok": False, "error": <código>}`; la interfaz traduce
el código. Los registros nunca incluyen valores de la base, contraseñas ni rutas de claves.
"""
from __future__ import annotations

import logging
import os
import threading
from functools import wraps
from pathlib import Path

from nucleo import generador
from nucleo.base import escribir_privado
from nucleo.boveda import Boveda, CambioExterno, NoEncontrado
from nucleo.claves import FicheroClaveInvalido, fichero_clave_xml_v2
from nucleo.errores import CredencialesIncorrectas, FicheroDanado, FormatoNoSoportado, NoEsKdbx

from .config import VERSION, Preferencias
from .portapapeles import Portapapeles

registro = logging.getLogger(__name__)

ERRORES = ((CredencialesIncorrectas, "credenciales"), (FicheroClaveInvalido, "fichero_clave"),
           (CambioExterno, "cambio_externo"), (NoEsKdbx, "no_kdbx"), (FormatoNoSoportado, "no_soportado"),
           (FicheroDanado, "danado"), (NoEncontrado, "no_encontrado"), (FileNotFoundError, "no_existe"),
           (PermissionError, "permiso"), (IsADirectoryError, "no_existe"))

PAPELERA = {"es": "Papelera", "en": "Recycle Bin", "fr": "Corbeille", "de": "Papierkorb", "it": "Cestino",
            "pt": "Reciclagem"}
SECCIONES = {
    "es": {"interno": "Servicios internos", "externo": "Servicios externos", "identidades": "Identidades operativas"},
    "en": {"interno": "Internal services", "externo": "External services", "identidades": "Operational identities"},
    "fr": {"interno": "Services internes", "externo": "Services externes", "identidades": "Identités opérationnelles"},
    "de": {"interno": "Interne Dienste", "externo": "Externe Dienste", "identidades": "Operative Identitäten"},
    "it": {"interno": "Servizi interni", "externo": "Servizi esterni", "identidades": "Identità operative"},
    "pt": {"interno": "Serviços internos", "externo": "Serviços externos", "identidades": "Identidades operacionais"},
}
# pywebview valida cada filtro con «Descripción (*.ext;*.ext)», descripción de letras y espacios:
# «* (*.*)» no pasa y el diálogo fallaría antes de abrirse.
TODOS = "Todos los ficheros (*.*)"
KDBX = "KeePass (*.kdbx)"
IMAGENES = "Imagenes (*.jpg;*.jpeg;*.png;*.webp;*.gif;*.bmp)"
MAX_ADJUNTO = 64 * 1024 * 1024


def _operacion(muta: bool = False):
    """Serializa el acceso a la bóveda, traduce errores y, si hace cambios, autoguarda."""
    def decorador(fn):
        @wraps(fn)
        def envoltura(self, *args, **kwargs):
            with self._cerrojo:
                try:
                    resultado = fn(self, *args, **kwargs)
                    salida = {"ok": True, **(resultado if isinstance(resultado, dict) else {"valor": resultado})}
                    if muta and self._boveda is not None:
                        salida.update(self._autoguardar())
                    return salida
                except Exception as e:
                    for tipo, codigo in ERRORES:
                        if isinstance(e, tipo):
                            return {"ok": False, "error": codigo}
                    registro.exception("fallo interno en %s", fn.__name__)
                    return {"ok": False, "error": "interno"}
        return envoltura
    return decorador


class Api:
    def __init__(self, ventana=None, preferencias: Preferencias | None = None, dialogos=None):
        self._ventana = ventana          # la pone el lanzador; hace falta para los diálogos
        self._dialogos = dialogos        # sustituto de los diálogos en las pruebas
        self._cerrojo = threading.RLock()
        self._boveda: Boveda | None = None
        self._pref = preferencias or Preferencias.cargar()
        self._pp = Portapapeles()
        self.ruta_inicial: str | None = None

    # ── Utilidades ───────────────────────────────────────────────────────────
    def _b(self) -> Boveda:
        if self._boveda is None:
            raise NoEncontrado("no hay base abierta")
        return self._boveda

    def _papelera(self) -> str:
        return PAPELERA.get(self._pref.idioma, "Papelera")

    def _autoguardar(self) -> dict:
        b = self._boveda
        if not self._pref.autoguardado or not b.cambios:
            return {"cambios": b.cambios}
        try:
            b.guardar(copia_previa=self._pref.copia_previa)
            return {"cambios": False}
        except CambioExterno:
            return {"cambios": True, "aviso": "cambio_externo"}
        except Exception:
            registro.exception("fallo al autoguardar")
            return {"cambios": True, "aviso": "guardado"}

    def _dialogo(self, tipo: str, multiple: bool = False, **kw):
        if self._dialogos is not None:
            r = self._dialogos(tipo, allow_multiple=multiple, **kw)
        else:
            import webview
            tipos = {"abrir": webview.FileDialog.OPEN, "guardar": webview.FileDialog.SAVE}
            r = self._ventana.create_file_dialog(tipos[tipo], allow_multiple=multiple, **kw)
        if not r:
            return [] if multiple else None
        lista = [r] if isinstance(r, str) else list(r)
        return lista if multiple else lista[0]

    def _papelera_y_secciones(self) -> dict:
        return SECCIONES.get(self._pref.idioma, SECCIONES["es"])

    @staticmethod
    def _leer_limitado(ruta: str) -> bytes:
        if os.path.getsize(ruta) > MAX_ADJUNTO:  # antes de leerlo entero en memoria
            raise PermissionError("adjunto demasiado grande")
        datos = Path(ruta).read_bytes()
        if len(datos) > MAX_ADJUNTO:
            raise PermissionError("adjunto demasiado grande")
        return datos

    # ── Estado y preferencias ────────────────────────────────────────────────
    @_operacion()
    def estado(self):
        p = self._pref
        return {"version": VERSION, "idioma": p.idioma,
                "recientes": [r for r in p.recientes if os.path.exists(r)],
                "inicial": self.ruta_inicial, "abierta": self._boveda is not None,
                "info": self._boveda.info() if self._boveda else None,
                "preferencias": {"recordar_recientes": p.recordar_recientes, "bloqueo_minutos": p.bloqueo_minutos,
                                 "portapapeles_segundos": p.portapapeles_segundos, "autoguardado": p.autoguardado,
                                 "copia_previa": p.copia_previa},
                "portapapeles_nativo": self._pp.disponible()}

    @_operacion()
    def guardar_preferencias(self, cambios: dict):
        for k in ("idioma", "recordar_recientes", "bloqueo_minutos", "portapapeles_segundos", "autoguardado",
                  "copia_previa"):
            if k in cambios:
                setattr(self._pref, k, type(getattr(self._pref, k))(cambios[k]))
        self._pref.guardar()
        return {}

    @_operacion()
    def olvidar_reciente(self, ruta: str):
        self._pref.recientes = [r for r in self._pref.recientes if r != ruta]
        self._pref.guardar()
        return {}

    # ── Diálogos de fichero ──────────────────────────────────────────────────
    @_operacion()
    def elegir_base(self):
        return {"ruta": self._dialogo("abrir", file_types=(KDBX, TODOS))}

    @_operacion()
    def elegir_fichero_clave(self):
        return {"ruta": self._dialogo("abrir", file_types=(TODOS,))}

    @_operacion()
    def elegir_destino(self, nombre: str = "NARSIL.kdbx"):
        ruta = self._dialogo("guardar", save_filename=nombre, file_types=(KDBX,))
        if ruta and not ruta.lower().endswith(".kdbx"):
            ruta += ".kdbx"
        return {"ruta": ruta}

    @_operacion()
    def crear_fichero_clave(self):
        """Genera un fichero de clave XML v2.0 (como KeePassXC) donde elija el usuario."""
        ruta = self._dialogo("guardar", save_filename="NARSIL.keyx", file_types=(TODOS,))
        if not ruta:
            return {"ruta": None}
        if os.path.lexists(ruta):
            raise PermissionError("no se sobrescribe un fichero de clave existente")
        try:  # es una credencial: 0600, sin seguir enlaces y sin carrera entre comprobar y crear
            escribir_privado(ruta, fichero_clave_xml_v2(os.urandom(32)))
        except FileExistsError as e:
            raise PermissionError("no se sobrescribe un fichero de clave existente") from e
        return {"ruta": ruta}

    # ── Abrir, crear, bloquear ───────────────────────────────────────────────
    @_operacion()
    def desbloquear(self, ruta: str, contrasena: str | None, ruta_clave: str | None = None):
        self._boveda = Boveda.abrir(ruta, contrasena if contrasena else None, ruta_clave or None) \
            if (contrasena or ruta_clave) else Boveda.abrir(ruta, "", None)
        self._pref.anotar_reciente(ruta)
        return {"info": self._boveda.info()}

    @_operacion()
    def crear_base(self, ruta: str, nombre: str, contrasena: str | None, ruta_clave: str | None = None):
        if os.path.exists(ruta):
            raise PermissionError("no se sobrescribe una base existente")
        self._boveda = Boveda.crear(ruta, nombre, contrasena or None, ruta_clave or None, self._papelera())
        self._boveda.preparar_secciones(self._papelera_y_secciones())
        self._boveda.guardar()
        self._pref.anotar_reciente(ruta)
        return {"info": self._boveda.info()}

    @_operacion()
    def bloquear(self, guardar: bool = True):
        """Descarta la base descifrada. Si hay cambios y se pide, se guardan antes. El portapapeles
        se vacía siempre; si el guardado falla, la base sigue abierta y se devuelve el error (como
        KeePassXC: no se pierden cambios), y la interfaz no debe mostrarse como bloqueada."""
        try:
            if self._boveda is not None and guardar and self._boveda.cambios:
                self._boveda.guardar(copia_previa=self._pref.copia_previa)
            self._boveda = None
        finally:
            self._pp.limpiar_ya()
        return {}

    # ── Consulta ─────────────────────────────────────────────────────────────
    @_operacion()
    def info(self):
        return {"info": self._b().info()}

    @_operacion()
    def grupos(self):
        return {"arbol": self._b().grupos()}

    @_operacion()
    def entradas(self, grupo: str | None = None, texto: str = "", filtros: dict | None = None, recursivo: bool = False):
        return {"lista": self._b().entradas(grupo, texto or "", recursivo=bool(recursivo), filtros=filtros or None)}

    @_operacion()
    def facetas(self, ambito: str | None = None):
        return self._b().facetas(ambito or None)

    @_operacion()
    def salud(self):
        return {"salud": self._b().salud()}

    @_operacion()
    def imagen(self, uuid: str, nombre: str):
        return {"url": self._b().imagen(uuid, nombre)}

    @_operacion()
    def entrada(self, uuid: str):
        return {"entrada": self._b().entrada(uuid)}

    @_operacion()
    def revelar(self, uuid: str, clave: str, historial: int | None = None):
        return {"valor": self._b().revelar(uuid, clave, historial)}

    @_operacion()
    def totp(self, uuid: str):
        return {"totp": self._b().totp(uuid)}

    @_operacion()
    def copiar(self, uuid: str, clave: str):
        """Copia un campo (o el código TOTP con clave «__totp__») al portapapeles nativo."""
        b = self._b()
        valor = (b.totp(uuid) or {}).get("codigo", "") if clave == "__totp__" else b.revelar(uuid, clave)
        if not self._pp.disponible():
            return {"nativo": False, "texto": valor, "segundos": self._pref.portapapeles_segundos}
        self._pp.copiar(valor, self._pref.portapapeles_segundos)
        return {"nativo": True, "segundos": self._pref.portapapeles_segundos}

    @_operacion()
    def copiar_texto(self, texto: str):
        if not self._pp.disponible():
            return {"nativo": False, "texto": texto, "segundos": self._pref.portapapeles_segundos}
        self._pp.copiar(texto, self._pref.portapapeles_segundos)
        return {"nativo": True, "segundos": self._pref.portapapeles_segundos}

    # ── Entradas ─────────────────────────────────────────────────────────────
    @_operacion(muta=True)
    def crear_entrada(self, grupo: str | None, campos: list, etiquetas: list | None = None, expira: str | None = None):
        return {"uuid": self._b().crear_entrada(grupo, campos, etiquetas, expira)}

    @_operacion(muta=True)
    def editar_entrada(self, uuid: str, campos: list, etiquetas: list | None = None, expira: str | None = None):
        self._b().editar_entrada(uuid, campos, etiquetas, expira)
        return {}

    @_operacion()
    def para_editar(self, uuid: str):
        """Todos los campos en claro, solo para el formulario de edición."""
        b = self._b()
        d = b.entrada(uuid)
        for c in d["campos"]:
            if c["protegido"]:
                c["valor"] = b.revelar(uuid, c["clave"])
        return {"entrada": d}

    @_operacion(muta=True)
    def duplicar_entrada(self, uuid: str):
        return {"uuid": self._b().duplicar_entrada(uuid)}

    @_operacion(muta=True)
    def mover_entrada(self, uuid: str, grupo: str | None):
        self._b().mover_entrada(uuid, grupo)
        return {}

    @_operacion(muta=True)
    def eliminar_entrada(self, uuid: str):
        self._b().eliminar_entrada(uuid, self._papelera())
        return {}

    @_operacion(muta=True)
    def restaurar_historial(self, uuid: str, indice: int):
        self._b().restaurar_historial(uuid, indice)
        return {}

    # ── Adjuntos ─────────────────────────────────────────────────────────────
    @_operacion(muta=True)
    def agregar_adjunto(self, uuid: str):
        rutas = self._dialogo("abrir", multiple=True, file_types=(TODOS,))
        if not rutas:
            return {"cancelado": True}
        return {"nombres": self._b().agregar_adjuntos(uuid, [(os.path.basename(r), self._leer_limitado(r)) for r in rutas])}

    @_operacion(muta=True)
    def agregar_imagenes(self, uuid: str):
        rutas = self._dialogo("abrir", multiple=True, file_types=(IMAGENES, TODOS))
        if not rutas:
            return {"cancelado": True}
        return {"nombres": self._b().agregar_adjuntos(uuid, [(os.path.basename(r), self._leer_limitado(r)) for r in rutas])}

    @_operacion(muta=True)
    def agregar_adjunto_datos(self, uuid: str, nombre: str, datos_b64: str):
        """Fichero soltado sobre la ventana o pegado del portapapeles: llega en base64 desde la página."""
        if len(datos_b64 or "") > MAX_ADJUNTO * 4 // 3 + 4:
            raise PermissionError("adjunto demasiado grande")
        import base64
        import binascii
        try:
            datos = base64.b64decode(datos_b64, validate=True)
        except (binascii.Error, ValueError) as e:
            raise PermissionError("datos de adjunto no válidos") from e
        return {"nombres": self._b().agregar_adjuntos(uuid, [(str(nombre or "adjunto"), datos)])}

    @_operacion()
    def guardar_adjunto(self, uuid: str, nombre: str):
        ruta = self._dialogo("guardar", save_filename=nombre, file_types=(TODOS,))
        if not ruta:
            return {"cancelado": True}
        Path(ruta).write_bytes(self._b().leer_adjunto(uuid, nombre))
        return {}

    @_operacion(muta=True)
    def quitar_adjunto(self, uuid: str, nombre: str):
        self._b().quitar_adjunto(uuid, nombre)
        return {}

    # ── Grupos ───────────────────────────────────────────────────────────────
    @_operacion(muta=True)
    def crear_grupo(self, padre: str | None, nombre: str):
        return {"uuid": self._b().crear_grupo(padre, nombre)}

    @_operacion(muta=True)
    def renombrar_grupo(self, uuid: str, nombre: str):
        self._b().renombrar_grupo(uuid, nombre)
        return {}

    @_operacion(muta=True)
    def mover_grupo(self, uuid: str, padre: str | None):
        self._b().mover_grupo(uuid, padre)
        return {}

    @_operacion(muta=True)
    def eliminar_grupo(self, uuid: str):
        self._b().eliminar_grupo(uuid, self._papelera())
        return {}

    @_operacion(muta=True)
    def vaciar_papelera(self):
        self._b().vaciar_papelera()
        return {}

    # ── Guardado y ajustes de la base ────────────────────────────────────────
    @_operacion()
    def guardar(self, forzar: bool = False):
        self._b().guardar(forzar=forzar, copia_previa=self._pref.copia_previa)
        return {"info": self._b().info()}

    @_operacion()
    def guardar_como(self):
        b = self._b()
        ruta = self._dialogo("guardar", save_filename=os.path.basename(b.ruta or "NARSIL.kdbx"),
                             file_types=(KDBX,))
        if not ruta:
            return {"cancelado": True}
        if not ruta.lower().endswith(".kdbx"):
            ruta += ".kdbx"
        b.guardar_como(ruta)
        self._pref.anotar_reciente(ruta)
        return {"info": b.info()}

    @_operacion(muta=True)
    def ajustar_base(self, nombre: str | None = None, descripcion: str | None = None):
        self._b().ajustar_base(nombre, descripcion)
        return {}

    @_operacion(muta=True)
    def cambiar_clave(self, contrasena: str | None, ruta_clave: str | None = None):
        if not contrasena and not ruta_clave:
            raise PermissionError("hace falta contraseña o fichero de clave")
        self._b().cambiar_clave(contrasena or None, ruta_clave or None)
        return {}

    @_operacion(muta=True)
    def ajustar_seguridad(self, cifrado: str | None = None, segundos: float | None = None):
        self._b().ajustar_seguridad(cifrado, segundos)
        return {}

    @_operacion(muta=True)
    def preparar_secciones(self):
        return {"secciones": self._b().preparar_secciones(self._papelera_y_secciones())}

    @_operacion(muta=True)
    def asignar_seccion(self, seccion: str, grupo: str | None):
        self._b().asignar_seccion(seccion, grupo or None)
        return {}

    @_operacion(muta=True)
    def fijar_renovacion(self, dias: int):
        self._b().fijar_renovar_dias(int(dias))
        return {}

    @_operacion(muta=True)
    def convertir_a_kdbx4(self):
        self._b().convertir_a_kdbx4()
        return {}

    # ── Generador ────────────────────────────────────────────────────────────
    @_operacion()
    def generar(self, opciones: dict):
        if opciones.get("modo") == "frase":
            n = int(opciones.get("palabras", 6))
            valor = generador.frase(n, opciones.get("separador", "-"), bool(opciones.get("mayuscula")),
                                    bool(opciones.get("numero")))
            return {"texto": valor, "bits": round(generador.entropia_frase(n))}
        args = dict(longitud=int(opciones.get("longitud", 24)), minusculas=bool(opciones.get("minusculas", True)),
                    mayusculas=bool(opciones.get("mayusculas", True)), digitos=bool(opciones.get("digitos", True)),
                    simbolos=bool(opciones.get("simbolos", True)), excluir_parecidos=bool(opciones.get("parecidos")))
        return {"texto": generador.contrasena(**args), "bits": round(generador.entropia_contrasena(**args))}

    @_operacion()
    def calidad(self, texto: str):
        return {"bits": round(generador.entropia_estimada(texto or ""))}
