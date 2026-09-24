"""Bóveda: una base abierta con su ruta, y las operaciones de edición que usa la interfaz.

Sigue la semántica de KeePass para que KeePassXC y KeePass vean lo mismo:
- Antes de modificar una entrada se guarda una copia en su historial (con los límites de la base).
- Eliminar manda a la papelera si está activa; eliminar desde la papelera borra y deja constancia
  en DeletedObjects (para que la sincronización de otros clientes no la resucite).
- Mover actualiza LocationChanged; editar, LastModificationTime y LastAccessTime.
Todo devuelve estructuras simples (dict/list) listas para JSON. Los valores protegidos no salen en
los listados ni en el detalle: se piden uno a uno con `revelar`.
"""
from __future__ import annotations

import base64
import copy
import hashlib
import json
import os
import re
import time
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from lxml import etree

from . import cifrado as _cifrado
from . import kdf as _kdf
from . import totp as _totp
from .base import (UUID_CERO, Base, campos_entrada, elemento_grupo, fecha_kdbx, insertar_entrada,
                   nuevo_uuid, texto_fecha_iso, texto_fecha_kdbx)
from . import generador as _generador
from .errores import ErrorKdbx

ESTANDAR = ("Title", "UserName", "Password", "URL", "Notes")

# Marcas propias de NARSIL Pass. Todo es KeePass estándar: KeePassXC lo conserva y lo muestra.
CAMPO_TIPO = "NARSIL.Tipo"               # campo de la entrada: «identidad» en las identidades operativas
CD_SECCIONES = "NARSIL.Secciones"        # Meta/CustomData: {"interno"|"externo"|"identidades": uuid de grupo}
CD_RENOVAR = "NARSIL.RenovarDias"        # Meta/CustomData: días para recordar renovar contraseñas (0 = nunca)
SECCIONES = ("interno", "externo", "identidades")
RENOVAR_POR_DEFECTO = 180
AVISO_CADUCIDAD_DIAS = 14
BITS_DEBIL = 60
MIME_IMAGEN = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp",
               ".gif": "image/gif", ".bmp": "image/bmp"}
MAX_IMAGEN = 32 * 1024 * 1024
_SERVICIO = re.compile(r"^Servicio\.(\d+)\.(\w+)$")


def es_contrasena(clave: str) -> bool:
    """Campos que cuentan como contraseña para la salud: el estándar y los de cada servicio."""
    return clave == "Password" or clave.endswith(".contrasena")


def mime_imagen(nombre: str) -> str | None:
    return MIME_IMAGEN.get(os.path.splitext(nombre)[1].lower())


def _host(url: str) -> str:
    url = (url or "").strip().lower()
    if not url:
        return ""
    url = re.sub(r"^[a-z][a-z0-9+.-]*://", "", url)
    host = re.split(r"[/?#:]", url, maxsplit=1)[0]
    return host[4:] if host.startswith("www.") else host


class CambioExterno(ErrorKdbx):
    """El fichero ha cambiado en disco desde que se abrió (otro programa lo ha guardado)."""


class NoEncontrado(ErrorKdbx):
    """No existe el grupo o la entrada pedidos."""


def _plano(texto: str) -> str:
    """Minúsculas y sin acentos: «Teléfono» encuentra «telefono»."""
    return "".join(c for c in unicodedata.normalize("NFD", texto.casefold()) if unicodedata.category(c) != "Mn")


def _huella(ruta: str) -> tuple[float, int, str] | None:
    try:
        datos = Path(ruta).read_bytes()
    except OSError:
        return None
    st = os.stat(ruta)
    return st.st_mtime, st.st_size, hashlib.sha256(datos).hexdigest()


@dataclass
class Boveda:
    base: Base
    ruta: str | None = None
    cambios: bool = False
    _huella_disco: tuple | None = field(default=None, repr=False)
    _rev: int = field(default=0, repr=False)
    _salud_cache: tuple | None = field(default=None, repr=False)
    _indice_cache: tuple | None = field(default=None, repr=False)

    # ── Abrir, crear, guardar ────────────────────────────────────────────────
    @classmethod
    def abrir(cls, ruta: str, contrasena: str | None, ruta_clave: str | None = None) -> "Boveda":
        datos = Path(ruta).read_bytes()
        fichero = Path(ruta_clave).read_bytes() if ruta_clave else None
        base = Base.abrir(datos, contrasena if contrasena is not None else None, fichero)
        return cls(base=base, ruta=ruta, _huella_disco=_huella(ruta))

    @classmethod
    def crear(cls, ruta: str, nombre: str, contrasena: str | None, ruta_clave: str | None = None,
              nombre_papelera: str = "Papelera") -> "Boveda":
        fichero = Path(ruta_clave).read_bytes() if ruta_clave else None
        b = cls(base=Base.nueva(nombre, contrasena, fichero), ruta=ruta)
        b._papelera(nombre_papelera)
        b.guardar()
        return b

    def guardar(self, *, forzar: bool = False, copia_previa: bool = False) -> None:
        if self.ruta is None:
            raise ErrorKdbx("la bóveda no tiene ruta")
        if not forzar and self._huella_disco is not None and _huella(self.ruta) not in (None, self._huella_disco):
            raise CambioExterno("el fichero ha cambiado en disco desde que se abrió")
        self.base.limpiar_adjuntos()
        self.base.guardar(self.ruta, copia_previa=copia_previa)
        self._huella_disco = _huella(self.ruta)
        self.cambios = False

    def guardar_como(self, ruta: str) -> None:
        self.ruta = ruta
        self._huella_disco = None
        self.guardar(forzar=True)

    def _cambio(self) -> None:
        self.cambios = True
        self._rev += 1

    # ── Utilidades ───────────────────────────────────────────────────────────
    @property
    def raiz(self) -> etree._Element:
        return self.base.raiz

    def _grupo(self, uuid: str | None) -> etree._Element:
        if not uuid:
            return self.raiz
        for g in self.raiz.iter("Group"):
            if g.findtext("UUID") == uuid:
                return g
        raise NoEncontrado(f"grupo {uuid}")

    def _entrada(self, uuid: str) -> etree._Element:
        for e in self.base.entradas():
            if e.findtext("UUID") == uuid:
                return e
        raise NoEncontrado(f"entrada {uuid}")

    def _fecha(self, momento: datetime) -> str:
        return texto_fecha_iso(momento) if self.base.es_v3 else texto_fecha_kdbx(momento)

    def _tocar(self, elem: etree._Element, *etiquetas: str) -> None:
        tiempos = elem.find("Times")
        if tiempos is None:
            return
        ahora = self.base.ahora()
        for etiqueta in etiquetas:
            t = tiempos.find(etiqueta)
            if t is None:
                t = etree.SubElement(tiempos, etiqueta)
            t.text = ahora

    @property
    def uuid_papelera(self) -> str | None:
        meta = self.base.meta
        if (meta.findtext("RecycleBinEnabled") or "True").strip().lower() != "true":
            return None
        u = meta.findtext("RecycleBinUUID")
        return u if u and u != UUID_CERO else None

    def _papelera(self, nombre: str = "Papelera") -> etree._Element | None:
        meta = self.base.meta
        if (meta.findtext("RecycleBinEnabled") or "True").strip().lower() != "true":
            return None
        u = self.uuid_papelera
        if u:
            try:
                return self._grupo(u)
            except NoEncontrado:
                pass
        g = elemento_grupo(nombre, self.base.ahora())
        g.find("IconID").text = "43"
        g.find("EnableAutoType").text = "false"
        g.find("EnableSearching").text = "false"
        self.raiz.append(g)
        for etiqueta, valor in (("RecycleBinUUID", g.findtext("UUID")), ("RecycleBinChanged", self.base.ahora())):
            e = meta.find(etiqueta)
            if e is None:
                e = etree.SubElement(meta, etiqueta)
            e.text = valor
        return g

    def _en_papelera(self, elem: etree._Element) -> bool:
        u = self.uuid_papelera
        if not u:
            return False
        p = elem.getparent()
        while p is not None and p.tag == "Group":
            if p.findtext("UUID") == u:
                return True
            p = p.getparent()
        return False

    # ── Consulta ─────────────────────────────────────────────────────────────
    def info(self) -> dict:
        b = self.base
        tipo_kdf = b.kdf.get("$UUID")
        return {
            "nombre": b.nombre, "descripcion": b.meta.findtext("DatabaseDescription") or "",
            "formato": b.version_texto, "es_v3": b.es_v3,
            "cifrado": _cifrado.NOMBRES.get(b.cifrado, "?"), "kdf": _kdf.NOMBRES.get(tipo_kdf, "?"),
            "kdf_iteraciones": b.kdf.get("I") if tipo_kdf != _kdf.UUID_AES_KDF else b.kdf.get("R"),
            "kdf_memoria_mib": (b.kdf.get("M") or 0) // (1024 * 1024) if tipo_kdf != _kdf.UUID_AES_KDF else None,
            "ruta": self.ruta, "cambios": self.cambios, "papelera": self.uuid_papelera,
            "raiz": self.raiz.findtext("UUID"), "entradas": sum(1 for _ in b.entradas()),
            "secciones": self.secciones(), "renovar_dias": self.renovar_dias(),
        }

    def grupos(self) -> dict:
        def nodo(g: etree._Element) -> dict:
            return {"uuid": g.findtext("UUID"), "nombre": g.findtext("Name") or "",
                    "entradas": len(g.findall("Entry")), "papelera": g.findtext("UUID") == self.uuid_papelera,
                    "hijos": [nodo(h) for h in g.findall("Group")]}
        return nodo(self.raiz)

    def _resumen(self, e: etree._Element) -> dict:
        c = campos_entrada(e)
        tiempos = e.find("Times")
        expira = tiempos is not None and (tiempos.findtext("Expires") or "").lower() == "true"
        fecha_exp = fecha_kdbx(tiempos.findtext("ExpiryTime")) if expira else None
        modif = fecha_kdbx(tiempos.findtext("LastModificationTime")) if tiempos is not None else None
        return {"uuid": e.findtext("UUID"), "titulo": c.get("Title", ""), "usuario": c.get("UserName", ""),
                "url": c.get("URL", ""), "grupo": e.getparent().findtext("UUID"),
                "etiquetas": [t for t in (e.findtext("Tags") or "").replace(",", ";").split(";") if t.strip()],
                "modificada": modif.isoformat() if modif else None,
                "expira": fecha_exp.isoformat() if fecha_exp else None,
                "caducada": bool(fecha_exp and fecha_exp <= datetime.now(timezone.utc)),
                "totp": _totp.leer(c) is not None, "adjuntos": len(e.findall("Binary")),
                "tipo": "identidad" if c.get(CAMPO_TIPO) == "identidad" else "entrada",
                "estado": c.get("Ficha.estado", ""),
                "servicios": len({m.group(1) for k in c if (m := _SERVICIO.match(k))}),
                "fotos": sum(1 for b in e.findall("Binary") if mime_imagen(b.findtext("Key") or "")),
                "alertas": sorted(self._indice_salud().get(e.findtext("UUID"), ()))}

    def entradas(self, grupo: str | None = None, texto: str = "", recursivo: bool = False,
                 filtros: dict | None = None) -> list[dict]:
        """Sin texto ni filtros: las entradas del grupo. Con texto o filtros: busca en el ámbito
        (filtros["ambito"], un grupo; si no, toda la base) menos la papelera, en título, usuario, URL,
        notas, etiquetas y campos no protegidos; nunca en contraseñas.

        Filtros: servicio (dominio o nombre de servicio), usuario, tipo («identidad»/«entrada»),
        estado (de la identidad) y alerta («repetida», «debil», «renovar», «caducada», «por_caducar»
        o «cualquiera»)."""
        filtros = {k: v for k, v in (filtros or {}).items() if v}
        if texto.strip() or set(filtros) - {"ambito"}:
            buscado = _plano(texto.strip())
            ambito = self._grupo(filtros["ambito"]) if filtros.get("ambito") else self.raiz
            salida = []
            for e in ambito.iter("Entry"):
                if e.getparent().tag != "Group" or self._en_papelera(e):
                    continue
                if buscado:
                    pajar = [e.findtext("Tags") or ""]
                    for s in e.findall("String"):
                        v = s.find("Value")
                        if v is not None and (v.get("Protected") or "").lower() != "true":
                            pajar.append(v.text or "")
                    if buscado not in _plano(" ".join(pajar)):
                        continue
                if not self._pasa_filtros(e, filtros):
                    continue
                salida.append(self._resumen(e))
            return salida
        g = self._grupo(grupo)
        if not recursivo:
            return [self._resumen(e) for e in g.findall("Entry")]
        dentro_papelera = self._en_papelera(g) or g.findtext("UUID") == self.uuid_papelera
        return [self._resumen(e) for e in g.iter("Entry")
                if e.getparent().tag == "Group" and (dentro_papelera or not self._en_papelera(e))]

    def _servicios_de(self, c: dict) -> set[str]:
        salida = {_host(c.get("URL", ""))}
        for k, v in c.items():
            m = _SERVICIO.match(k)
            if m and m.group(2) == "nombre" and v.strip():
                salida.add(v.strip().casefold())
            elif m and m.group(2) == "url":
                salida.add(_host(v))
        return {x for x in salida if x}

    def _usuarios_de(self, c: dict) -> set[str]:
        salida = {c.get("UserName", "").strip()}
        salida |= {v.strip() for k, v in c.items() if (m := _SERVICIO.match(k)) and m.group(2) in ("usuario", "alias")}
        return {x for x in salida if x}

    def _pasa_filtros(self, e: etree._Element, filtros: dict) -> bool:
        c = campos_entrada(e)
        if filtros.get("servicio") and filtros["servicio"].casefold() not in self._servicios_de(c):
            return False
        if filtros.get("usuario") and filtros["usuario"] not in self._usuarios_de(c):
            return False
        if filtros.get("tipo"):
            tipo = "identidad" if c.get(CAMPO_TIPO) == "identidad" else "entrada"
            if tipo != filtros["tipo"]:
                return False
        if filtros.get("estado") and c.get("Ficha.estado", "") != filtros["estado"]:
            return False
        if filtros.get("alerta"):
            alertas = self._indice_salud().get(e.findtext("UUID"), set())
            if not alertas if filtros["alerta"] == "cualquiera" else filtros["alerta"] not in alertas:
                return False
        return True

    def facetas(self, ambito: str | None = None) -> dict:
        """Valores distintos para los filtros de la lista: servicios y usuarios del ámbito."""
        raiz = self._grupo(ambito) if ambito else self.raiz
        servicios, usuarios = set(), set()
        for e in raiz.iter("Entry"):
            if e.getparent().tag != "Group" or self._en_papelera(e):
                continue
            c = campos_entrada(e)
            servicios |= self._servicios_de(c)
            usuarios |= self._usuarios_de(c)
        return {"servicios": sorted(servicios, key=_plano), "usuarios": sorted(usuarios, key=_plano)}

    def entrada(self, uuid: str) -> dict:
        e = self._entrada(uuid)
        campos = []
        for s in e.findall("String"):
            v = s.find("Value")
            protegido = v is not None and (v.get("Protected") or "").lower() == "true"
            campos.append({"clave": s.findtext("Key") or "", "protegido": protegido,
                           "valor": None if protegido else ((v.text or "") if v is not None else ""),
                           "vacio": not ((v.text or "") if v is not None else "")})
        tiempos = e.find("Times")
        fechas = {t.tag: (fecha_kdbx(t.text).isoformat() if fecha_kdbx(t.text) else None)
                  for t in (tiempos if tiempos is not None else []) if t.tag.endswith("Time") or t.tag == "LocationChanged"}
        historial = []
        for i, h in enumerate(e.findall("History/Entry")):
            ht = h.find("Times")
            m = fecha_kdbx(ht.findtext("LastModificationTime")) if ht is not None else None
            historial.append({"indice": i, "titulo": campos_entrada(h).get("Title", ""),
                              "modificada": m.isoformat() if m else None})
        resumen = self._resumen(e)
        return {**resumen, "campos": campos, "fechas": fechas, "historial": historial,
                "adjuntos_lista": [{"nombre": b.findtext("Key") or "", "tamano": self._tam_adjunto(b)}
                                   for b in e.findall("Binary")],
                "en_papelera": self._en_papelera(e)}

    def _tam_adjunto(self, b: etree._Element) -> int:
        v = b.find("Value")
        try:
            if v is not None and (v.get("Ref") or "").isdigit():
                return len(self.base.adjunto(int(v.get("Ref"))))
        except (KeyError, IndexError):
            pass
        return 0

    def revelar(self, uuid: str, clave: str, historial: int | None = None) -> str:
        e = self._entrada(uuid)
        if historial is not None:
            e = e.findall("History/Entry")[historial]
        return campos_entrada(e).get(clave, "")

    def totp(self, uuid: str) -> dict | None:
        cfg = _totp.leer(campos_entrada(self._entrada(uuid)))
        if cfg is None:
            return None
        return {"codigo": cfg.codigo(), "restante": cfg.restante(), "periodo": cfg.periodo}

    # ── Historial ────────────────────────────────────────────────────────────
    def _a_historial(self, e: etree._Element) -> None:
        historia = e.find("History")
        if historia is None:
            historia = etree.SubElement(e, "History")
        copia = copy.deepcopy(e)
        for h in copia.findall("History"):
            copia.remove(h)
        historia.append(copia)
        meta = self.base.meta
        maximo = int(meta.findtext("HistoryMaxItems") or "10")
        if maximo >= 0:
            while len(historia) > maximo:
                historia.remove(historia[0])
        tope = int(meta.findtext("HistoryMaxSize") or "6291456")
        if tope >= 0:
            while len(historia) > 1 and sum(len(etree.tostring(h)) for h in historia) > tope:
                historia.remove(historia[0])

    def restaurar_historial(self, uuid: str, indice: int) -> None:
        e = self._entrada(uuid)
        version = e.findall("History/Entry")[indice]
        self._a_historial(e)
        for etiqueta in ("String", "Binary", "Tags", "IconID", "ForegroundColor", "BackgroundColor", "OverrideURL"):
            for viejo in e.findall(etiqueta):
                e.remove(viejo)
        historia = e.find("History")
        for hijo in version:
            if hijo.tag in ("String", "Binary", "Tags", "IconID", "ForegroundColor", "BackgroundColor", "OverrideURL"):
                historia.addprevious(copy.deepcopy(hijo))
        self._tocar(e, "LastModificationTime", "LastAccessTime")
        self._cambio()

    # ── Entradas ─────────────────────────────────────────────────────────────
    def crear_entrada(self, grupo: str | None, campos: list[dict], etiquetas: list[str] | None = None,
                      expira: str | None = None) -> str:
        valores = {c["clave"]: c.get("valor", "") for c in campos}
        protegidos = tuple(c["clave"] for c in campos if c.get("protegido")) or ("Password",)
        e = self.base.nueva_entrada(self._grupo(grupo), valores, protegidos)
        self._fijar_extras(e, etiquetas, expira)
        self._cambio()
        return e.findtext("UUID")

    def editar_entrada(self, uuid: str, campos: list[dict], etiquetas: list[str] | None = None,
                       expira: str | None = None) -> None:
        """`campos`: la lista completa de campos de texto tras editar ({clave, valor, protegido})."""
        e = self._entrada(uuid)
        self._a_historial(e)
        for s in e.findall("String"):
            e.remove(s)
        ancla = e.find("Binary") if e.find("Binary") is not None else e.find("AutoType")
        orden = sorted(campos, key=lambda c: (ESTANDAR.index(c["clave"]) if c["clave"] in ESTANDAR else 99))
        for c in orden:
            s = etree.Element("String")
            etree.SubElement(s, "Key").text = c["clave"]
            v = etree.SubElement(s, "Value")
            v.text = c.get("valor", "")
            if c.get("protegido"):
                v.set("Protected", "True")
            if ancla is not None:
                ancla.addprevious(s)
            else:
                e.append(s)
        self._fijar_extras(e, etiquetas, expira)
        self._tocar(e, "LastModificationTime", "LastAccessTime")
        self._cambio()

    def _fijar_extras(self, e: etree._Element, etiquetas: list[str] | None, expira: str | None) -> None:
        if etiquetas is not None:
            t = e.find("Tags")
            if t is None:
                t = etree.Element("Tags")
                e.find("Times").addprevious(t)
            t.text = ";".join(x.strip() for x in etiquetas if x.strip())
        if expira is not None:
            tiempos = e.find("Times")
            if expira:
                tiempos.find("Expires").text = "True"
                tiempos.find("ExpiryTime").text = self._fecha(datetime.fromisoformat(expira.replace("Z", "+00:00")))
            else:
                tiempos.find("Expires").text = "False"

    def duplicar_entrada(self, uuid: str, sufijo: str = " (copia)") -> str:
        e = self._entrada(uuid)
        copia = copy.deepcopy(e)
        copia.find("UUID").text = nuevo_uuid()
        h = copia.find("History")
        if h is not None:
            for x in list(h):
                h.remove(x)
        for s in copia.findall("String"):
            if s.findtext("Key") == "Title":
                s.find("Value").text = (s.find("Value").text or "") + sufijo
        e.addnext(copia)
        self._tocar(copia, "CreationTime", "LastModificationTime", "LastAccessTime", "LocationChanged")
        self._cambio()
        return copia.findtext("UUID")

    def mover_entrada(self, uuid: str, grupo: str | None) -> None:
        e = self._entrada(uuid)
        destino = self._grupo(grupo)
        e.getparent().remove(e)
        insertar_entrada(destino, e)
        self._tocar(e, "LocationChanged")
        self._cambio()

    def eliminar_entrada(self, uuid: str, nombre_papelera: str = "Papelera") -> None:
        e = self._entrada(uuid)
        if not self._en_papelera(e):
            papelera = self._papelera(nombre_papelera)
            if papelera is not None:
                e.getparent().remove(e)
                insertar_entrada(papelera, e)
                self._tocar(e, "LocationChanged")
                self._cambio()
                return
        self._borrar(e)

    def _borrar(self, elem: etree._Element) -> None:
        eliminados = self.base.xml.getroot().find("Root/DeletedObjects")
        if eliminados is None:
            eliminados = etree.SubElement(self.base.xml.getroot().find("Root"), "DeletedObjects")
        for x in [elem, *[d for d in elem.iter("Group", "Entry") if d is not elem and d.getparent().tag != "History"]]:
            if x.getparent() is not None and x.getparent().tag == "History":
                continue
            d = etree.SubElement(eliminados, "DeletedObject")
            etree.SubElement(d, "UUID").text = x.findtext("UUID")
            etree.SubElement(d, "DeletionTime").text = self.base.ahora()
        elem.getparent().remove(elem)
        self._cambio()

    def vaciar_papelera(self) -> None:
        u = self.uuid_papelera
        if not u:
            return
        p = self._grupo(u)
        for hijo in list(p.findall("Entry")) + list(p.findall("Group")):
            self._borrar(hijo)

    # ── Adjuntos ─────────────────────────────────────────────────────────────
    def agregar_adjunto(self, uuid: str, nombre: str, datos: bytes) -> None:
        e = self._entrada(uuid)
        self._a_historial(e)
        for b in e.findall("Binary"):
            if b.findtext("Key") == nombre:
                e.remove(b)
        ref = self.base.agregar_adjunto(datos)
        b = etree.Element("Binary")
        etree.SubElement(b, "Key").text = nombre
        etree.SubElement(b, "Value", Ref=str(ref))
        if e.find("AutoType") is not None:
            e.find("AutoType").addprevious(b)
        else:
            e.append(b)
        self._tocar(e, "LastModificationTime", "LastAccessTime")
        self._cambio()

    def leer_adjunto(self, uuid: str, nombre: str) -> bytes:
        for b in self._entrada(uuid).findall("Binary"):
            if b.findtext("Key") == nombre:
                return self.base.adjunto(int(b.find("Value").get("Ref")))
        raise NoEncontrado(f"adjunto {nombre}")

    def quitar_adjunto(self, uuid: str, nombre: str) -> None:
        e = self._entrada(uuid)
        self._a_historial(e)
        for b in e.findall("Binary"):
            if b.findtext("Key") == nombre:
                e.remove(b)
        self._tocar(e, "LastModificationTime", "LastAccessTime")
        self._cambio()

    # ── Grupos ───────────────────────────────────────────────────────────────
    def crear_grupo(self, padre: str | None, nombre: str) -> str:
        g = elemento_grupo(nombre, self.base.ahora())
        p = self._grupo(padre)
        u = self.uuid_papelera
        papelera = next((x for x in p.findall("Group") if u and x.findtext("UUID") == u), None)
        if papelera is not None:
            papelera.addprevious(g)  # la papelera, siempre al final
        else:
            p.append(g)
        self._cambio()
        return g.findtext("UUID")

    def renombrar_grupo(self, uuid: str, nombre: str) -> None:
        g = self._grupo(uuid)
        g.find("Name").text = nombre
        self._tocar(g, "LastModificationTime")
        self._cambio()

    def mover_grupo(self, uuid: str, padre: str | None) -> None:
        g, destino = self._grupo(uuid), self._grupo(padre)
        if g is self.raiz or any(x is g for x in destino.iterancestors()) or destino is g:
            raise ErrorKdbx("no se puede mover un grupo dentro de sí mismo")
        g.getparent().remove(g)
        destino.append(g)
        self._tocar(g, "LocationChanged")
        self._cambio()

    def eliminar_grupo(self, uuid: str, nombre_papelera: str = "Papelera") -> None:
        g = self._grupo(uuid)
        if g is self.raiz or uuid == self.uuid_papelera:
            raise ErrorKdbx("no se puede eliminar el grupo raíz ni la papelera")
        if not self._en_papelera(g):
            papelera = self._papelera(nombre_papelera)
            if papelera is not None:
                g.getparent().remove(g)
                papelera.append(g)
                self._tocar(g, "LocationChanged")
                self._cambio()
                return
        self._borrar(g)

    # ── Ajustes de la base ───────────────────────────────────────────────────
    def ajustar_base(self, nombre: str | None = None, descripcion: str | None = None) -> None:
        meta = self.base.meta
        for etiqueta, valor in (("DatabaseName", nombre), ("DatabaseDescription", descripcion)):
            if valor is None:
                continue
            e = meta.find(etiqueta)
            if e is None:
                e = etree.SubElement(meta, etiqueta)
            e.text = valor
            cambio = meta.find(etiqueta + "Changed")
            if cambio is not None:
                cambio.text = self.base.ahora()
        self._cambio()

    def cambiar_clave(self, contrasena: str | None, ruta_clave: str | None = None) -> None:
        fichero = Path(ruta_clave).read_bytes() if ruta_clave else None
        self.base.cambiar_clave(contrasena, fichero)
        self._cambio()

    def ajustar_seguridad(self, cifrado: str | None = None, segundos_desbloqueo: float | None = None) -> None:
        """KDBX 4: cifrado (AES-256 o ChaCha20) y Argon2id calibrado al tiempo pedido.
        KDBX 3.1: solo rondas de AES-KDF calibradas al tiempo pedido (el formato no admite más)."""
        b = self.base
        if cifrado and not b.es_v3:
            b.cifrado = {"AES-256": _cifrado.UUID_AES256, "ChaCha20": _cifrado.UUID_CHACHA20}[cifrado]
        if segundos_desbloqueo:
            if b.es_v3 or b.kdf.get("$UUID") == _kdf.UUID_AES_KDF:
                import time
                t0 = time.perf_counter()
                p = copy.deepcopy(b.kdf)
                p.poner(0x05, "R", 200_000)
                _kdf.transformar(bytes(32), p)
                por_ronda = (time.perf_counter() - t0) / 200_000
                b.kdf.poner(0x05, "R", max(60_000, int(segundos_desbloqueo / max(por_ronda, 1e-9))))
            else:
                b.kdf = _kdf.argon2id_por_defecto(iteraciones=_kdf.calibrar_iteraciones(segundos_desbloqueo))
            _kdf.renovar_sal(b.kdf)
            b._transformada = None
        self._cambio()

    def convertir_a_kdbx4(self) -> None:
        self.base.convertir_a_kdbx4(_kdf.argon2id_por_defecto(iteraciones=_kdf.calibrar_iteraciones()))
        self._cambio()

    # ── Secciones (servicios internos, externos e identidades operativas) ─────
    def _custom(self, clave: str) -> str | None:
        for item in self.base.meta.iterfind("CustomData/Item"):
            if item.findtext("Key") == clave:
                return item.findtext("Value")
        return None

    def _poner_custom(self, clave: str, valor: str) -> None:
        meta = self.base.meta
        cd = meta.find("CustomData")
        if cd is None:
            cd = etree.SubElement(meta, "CustomData")
        for item in cd.findall("Item"):
            if item.findtext("Key") == clave:
                item.find("Value").text = valor
                break
        else:
            item = etree.SubElement(cd, "Item")
            etree.SubElement(item, "Key").text = clave
            etree.SubElement(item, "Value").text = valor
        self._cambio()

    def secciones(self) -> dict:
        try:
            datos = json.loads(self._custom(CD_SECCIONES) or "{}")
        except ValueError:
            datos = {}
        existentes = {g.findtext("UUID") for g in self.raiz.iter("Group")}
        return {s: (datos.get(s) if isinstance(datos, dict) and datos.get(s) in existentes
                    and not self._en_papelera(self._grupo(datos[s])) else None) for s in SECCIONES}

    def preparar_secciones(self, nombres: dict[str, str]) -> dict:
        """Crea bajo la raíz los grupos de las secciones que falten y guarda el mapa en la base."""
        actuales = self.secciones()
        for s in SECCIONES:
            if not actuales[s]:
                actuales[s] = self.crear_grupo(None, nombres.get(s) or s)
        self._poner_custom(CD_SECCIONES, json.dumps(actuales, sort_keys=True))
        return actuales

    def asignar_seccion(self, seccion: str, grupo: str | None) -> None:
        if seccion not in SECCIONES:
            raise ErrorKdbx(f"sección desconocida: {seccion}")
        actuales = self.secciones()
        if grupo:
            g = self._grupo(grupo)
            if g is self.raiz or grupo == self.uuid_papelera:
                raise ErrorKdbx("la raíz y la papelera no pueden ser una sección")
            actuales = {s: (u if u != grupo else None) for s, u in actuales.items()}
        actuales[seccion] = grupo or None
        self._poner_custom(CD_SECCIONES, json.dumps(actuales, sort_keys=True))

    def renovar_dias(self) -> int:
        valor = self._custom(CD_RENOVAR)
        try:
            return max(0, int(valor)) if valor is not None else RENOVAR_POR_DEFECTO
        except ValueError:
            return RENOVAR_POR_DEFECTO

    def fijar_renovar_dias(self, dias: int) -> None:
        self._poner_custom(CD_RENOVAR, str(max(0, min(int(dias), 3650))))

    # ── Salud de las contraseñas ─────────────────────────────────────────────
    def _fijada_el(self, e: etree._Element, clave: str) -> datetime | None:
        """Cuándo se puso el valor actual del campo: se recorre el historial hasta el último cambio."""
        versiones = [*e.findall("History/Entry"), e]
        actual = campos_entrada(e).get(clave, "")
        momento = None
        previo = object()
        for v in versiones:
            valor = campos_entrada(v).get(clave, "")
            t = v.find("Times")
            cuando = fecha_kdbx(t.findtext("LastModificationTime")) if t is not None else None
            if valor != previo:
                momento = cuando
            previo = valor
        if momento is None:
            t = e.find("Times")
            momento = fecha_kdbx(t.findtext("CreationTime")) if t is not None else None
        return momento if actual else None

    def salud(self) -> dict:
        """Contraseñas repetidas, débiles, caducadas o por caducar y pendientes de renovar.
        Nunca devuelve valores: solo qué entrada y qué campo."""
        # Se recalcula si cambia la base o cada 5 minutos: la caducidad depende de la hora, y el aviso
        # periódico de la interfaz tiene que ver lo que caduca con la aplicación abierta.
        clave_cache = (self._rev, int(time.time() // 300))
        if self._salud_cache and self._salud_cache[0] == clave_cache:
            return self._salud_cache[1]
        ahora = datetime.now(timezone.utc)
        dias = self.renovar_dias()
        por_huella: dict[str, list[tuple[tuple, dict]]] = {}
        debiles, renovar, caducadas, por_caducar = [], [], [], []
        for e in self.base.entradas():
            if self._en_papelera(e):
                continue
            c = campos_entrada(e)
            uuid, titulo, grupo = e.findtext("UUID"), c.get("Title", ""), e.getparent().findtext("UUID")
            tiempos = e.find("Times")
            if tiempos is not None and (tiempos.findtext("Expires") or "").lower() == "true":
                fin = fecha_kdbx(tiempos.findtext("ExpiryTime"))
                if fin and fin <= ahora:
                    caducadas.append({"uuid": uuid, "titulo": titulo, "grupo": grupo, "fecha": fin.isoformat()})
                elif fin and (fin - ahora).days < AVISO_CADUCIDAD_DIAS:
                    por_caducar.append({"uuid": uuid, "titulo": titulo, "grupo": grupo, "fecha": fin.isoformat()})
            for clave, valor in c.items():
                if not es_contrasena(clave) or not valor:
                    continue
                ref = {"uuid": uuid, "titulo": titulo, "grupo": grupo, "campo": clave,
                       "servicio": c.get(clave.rsplit(".", 1)[0] + ".nombre", "") if clave != "Password" else ""}
                por_huella.setdefault(hashlib.sha256(valor.encode("utf-8")).hexdigest(), []).append((self._cuenta(uuid, c, clave), ref))
                bits = round(_generador.entropia_estimada(valor))
                if bits < BITS_DEBIL:
                    debiles.append({**ref, "bits": bits})
                if dias:
                    fijada = self._fijada_el(e, clave)
                    if fijada and (ahora - fijada).days >= dias:
                        renovar.append({**ref, "fecha": fijada.isoformat(), "dias": (ahora - fijada).days})
        # Repetida = la misma contraseña en cuentas distintas. La misma cuenta anotada dos veces en una
        # identidad (la cuenta principal y su servicio de correo, con el mismo usuario) no es reutilización.
        repetidas = []
        for refs in por_huella.values():
            por_cuenta = {}
            for cuenta, ref in refs:
                por_cuenta.setdefault(cuenta, ref)
            if len(por_cuenta) > 1:
                repetidas.append(list(por_cuenta.values()))
        resultado = {"repetidas": repetidas, "debiles": debiles, "renovar": renovar, "caducadas": caducadas,
                     "por_caducar": por_caducar, "renovar_dias": dias,
                     "total": sum(len(x) for x in (repetidas, debiles, renovar, caducadas, por_caducar))}
        self._salud_cache = (clave_cache, resultado)
        self._indice_cache = None
        return resultado

    @staticmethod
    def _cuenta(uuid: str, c: dict, clave: str) -> tuple:
        """Quién se autentica con ese campo: (entrada, usuario). Sin usuario, el propio campo."""
        if clave == "Password":
            usuario = c.get("UserName", "")
        else:
            base = clave.rsplit(".", 1)[0]
            usuario = c.get(base + ".usuario") or c.get(base + ".correo") or c.get(base + ".id") or ""
        usuario = usuario.strip().casefold()
        return (uuid, usuario) if usuario else (uuid, clave)

    def _indice_salud(self) -> dict[str, set[str]]:
        s = self.salud()
        if self._indice_cache is not None and self._indice_cache[0] is s:
            return self._indice_cache[1]
        indice: dict[str, set[str]] = {}
        for refs in s["repetidas"]:
            for r in refs:
                indice.setdefault(r["uuid"], set()).add("repetida")
        for clave, alerta in (("debiles", "debil"), ("renovar", "renovar"), ("caducadas", "caducada"),
                              ("por_caducar", "por_caducar")):
            for r in s[clave]:
                indice.setdefault(r["uuid"], set()).add(alerta)
        self._indice_cache = (s, indice)
        return indice

    # ── Imágenes y adjuntos en bloque ────────────────────────────────────────
    def agregar_adjuntos(self, uuid: str, ficheros: list[tuple[str, bytes]]) -> list[str]:
        """Varios adjuntos con una sola versión en el historial. Si el nombre ya existe en la entrada,
        se numera («foto (2).jpg») en vez de sustituir. Devuelve los nombres finales."""
        e = self._entrada(uuid)
        self._a_historial(e)
        existentes = {b.findtext("Key") for b in e.findall("Binary")}
        nombres = []
        for nombre, datos in ficheros:
            nombre = os.path.basename(nombre.replace("\\", "/")).strip() or "adjunto"
            raiz, ext = os.path.splitext(nombre)
            n, final = 2, nombre
            while final in existentes:
                final, n = f"{raiz} ({n}){ext}", n + 1
            existentes.add(final)
            ref = self.base.agregar_adjunto(datos)
            b = etree.Element("Binary")
            etree.SubElement(b, "Key").text = final
            etree.SubElement(b, "Value", Ref=str(ref))
            if e.find("AutoType") is not None:
                e.find("AutoType").addprevious(b)
            elif e.find("History") is not None:
                e.find("History").addprevious(b)
            else:
                e.append(b)
            nombres.append(final)
        self._tocar(e, "LastModificationTime", "LastAccessTime")
        self._cambio()
        return nombres

    def imagen(self, uuid: str, nombre: str) -> str:
        """Adjunto de imagen como data: URL para previsualizarlo en la ventana (la CSP solo admite data:)."""
        mime = mime_imagen(nombre)
        if not mime:
            raise NoEncontrado(f"{nombre} no es una imagen")
        datos = self.leer_adjunto(uuid, nombre)
        if len(datos) > MAX_IMAGEN:
            raise NoEncontrado("imagen demasiado grande para previsualizar")
        return f"data:{mime};base64,{base64.b64encode(datos).decode()}"
