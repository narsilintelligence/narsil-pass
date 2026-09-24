"""Base KeePass (KDBX 3.1 y KDBX 4.x) abierta en memoria: lectura, creación y guardado.

Principios de compatibilidad:
- El árbol XML descifrado es la fuente de verdad. Lo que el gestor no entiende (AutoType,
  CustomData de complementos, iconos, campos nuevos) se conserva tal cual.
- Cada base se guarda en su formato y versión (3.1 sigue en 3.1, 4.x en 4.x) salvo que el usuario
  pida convertirla a KDBX 4.
- Los valores protegidos se recorren siempre en orden de documento.
"""
from __future__ import annotations

import base64
import binascii
import copy
import gzip
import hashlib
import hmac
import os
import struct
import uuid as _uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from lxml import etree

from . import cifrado, formato, kdf
from .claves import clave_compuesta
from .errores import CredencialesIncorrectas, FicheroDanado, FormatoNoSoportado
from .kdf import argon2id_por_defecto, calibrar_iteraciones

ORIGEN = datetime(1, 1, 1, tzinfo=timezone.utc)
UUID_CERO = base64.b64encode(bytes(16)).decode("ascii")

# Elementos que contienen fechas (para convertir de ISO a binario al pasar a KDBX 4).
ETIQUETAS_FECHA = ("CreationTime", "LastModificationTime", "LastAccessTime", "ExpiryTime", "LocationChanged",
                   "DeletionTime", "DatabaseNameChanged", "DatabaseDescriptionChanged", "DefaultUserNameChanged",
                   "MasterKeyChanged", "RecycleBinChanged", "EntryTemplatesGroupChanged", "SettingsChanged")


def _parser() -> etree.XMLParser:
    # Sin entidades, sin DTD y sin red: el XML viene de un fichero que puede ser hostil.
    # huge_tree: en KDBX 3.1 los adjuntos van en base64 dentro del XML y un solo nodo pasa del
    # límite de 10 MB de libxml2. Es seguro porque cualquier DTD se rechaza (_parsear) y el XML
    # solo llega aquí tras autenticar el fichero con la clave.
    return etree.XMLParser(resolve_entities=False, no_network=True, load_dtd=False,
                           huge_tree=True, remove_blank_text=False)


def fecha_kdbx(texto: str | None) -> datetime | None:
    """KDBX 4 guarda las fechas como segundos desde 0001-01-01 en int64, en base64; KDBX 3.1, en ISO."""
    if not texto:
        return None
    texto = texto.strip()
    try:
        bruto = base64.b64decode(texto, validate=True)
        if len(bruto) == 8:
            return ORIGEN + timedelta(seconds=struct.unpack("<q", bruto)[0])
    except (ValueError, OverflowError):
        pass
    try:
        d = datetime.fromisoformat(texto.replace("Z", "+00:00"))
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def texto_fecha_kdbx(momento: datetime) -> str:
    segundos = int((momento.astimezone(timezone.utc) - ORIGEN).total_seconds())
    return base64.b64encode(struct.pack("<q", segundos)).decode("ascii")


def texto_fecha_iso(momento: datetime) -> str:
    return momento.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass
class Adjunto:
    datos: bytes
    protegido: bool


@dataclass
class Base:
    """Base abierta. Guarda lo necesario para reescribirla idéntica en lo que no se toque."""

    version: int
    cifrado: bytes
    compresion: int
    kdf: formato.Variante          # en 3.1 se representa como AES-KDF {S: semilla, R: rondas}
    datos_publicos: bytes | None
    flujo_id: int
    adjuntos: list[Adjunto]        # solo KDBX 4 (en 3.1 los adjuntos viven en Meta/Binaries)
    xml: etree._ElementTree
    compuesta: bytes = field(repr=False)
    campos_desconocidos: list[tuple[int, bytes]] = field(default_factory=list)
    _transformada: tuple[bytes, bytes] | None = field(default=None, repr=False)  # (huella KDF, clave)

    # ── Utilidades de formato ────────────────────────────────────────────────
    @property
    def es_v3(self) -> bool:
        return self.version >> 16 == 3

    @property
    def version_texto(self) -> str:
        return f"KDBX {self.version >> 16}.{self.version & 0xFFFF}"

    def ahora(self) -> str:
        momento = datetime.now(timezone.utc)
        return texto_fecha_iso(momento) if self.es_v3 else texto_fecha_kdbx(momento)

    def _clave_transformada(self) -> bytes:
        huella = self.kdf.escribir()
        if self._transformada is None or self._transformada[0] != huella:
            self._transformada = (huella, kdf.transformar(self.compuesta, self.kdf))
        return self._transformada[1]

    def cambiar_clave(self, contrasena: str | None = None, fichero_clave: bytes | None = None) -> None:
        """Nueva clave maestra: sal nueva para la KDF, como KeePassXC."""
        self.compuesta = clave_compuesta(contrasena, fichero_clave)
        kdf.renovar_sal(self.kdf)
        self._transformada = None
        cambio = self.xml.getroot().find("Meta/MasterKeyChanged")
        if cambio is not None:
            cambio.text = self.ahora()

    # ── Lectura ──────────────────────────────────────────────────────────────
    @classmethod
    def abrir(cls, datos: bytes, contrasena: str | None = None, fichero_clave: bytes | None = None,
              *, compuesta: bytes | None = None, _transformada: tuple[bytes, bytes] | None = None) -> "Base":
        cab, pos = formato.leer_cabecera(datos)
        if compuesta is None:
            compuesta = clave_compuesta(contrasena, fichero_clave)
        try:
            if cab.version >> 16 == 3:
                return cls._abrir_v3(datos, cab, pos, compuesta, _transformada)
            return cls._abrir_v4(datos, cab, pos, compuesta, _transformada)
        except (struct.error, UnicodeDecodeError, binascii.Error) as e:
            # Campos de longitud incorrecta o texto ilegible en un fichero hostil o corrupto.
            raise FicheroDanado("estructura interna mal formada") from e

    @staticmethod
    def _derivar(compuesta: bytes, parametros: formato.Variante, conocida: tuple[bytes, bytes] | None):
        huella = parametros.escribir()
        if conocida is not None and conocida[0] == huella:
            return conocida
        return huella, kdf.transformar(compuesta, parametros)

    @classmethod
    def _abrir_v4(cls, datos, cab, pos, compuesta, conocida) -> "Base":
        suma, firma = datos[pos:pos + 32], datos[pos + 32:pos + 64]
        if len(firma) != 32:
            raise FicheroDanado("falta el hash o la HMAC de la cabecera")
        if not hmac.compare_digest(hashlib.sha256(cab.bruta).digest(), suma):
            raise FicheroDanado("el hash de la cabecera no coincide")

        ident, semilla, iv = cab.campo(formato.CAB_CIFRADO), cab.campo(formato.CAB_SEMILLA), cab.campo(formato.CAB_IV)
        bruto_kdf = cab.campo(formato.CAB_KDF)
        compresion = struct.unpack("<I", cab.campo(formato.CAB_COMPRESION) or bytes(4))[0]
        if not (ident and semilla and iv and bruto_kdf):
            raise FicheroDanado("faltan campos obligatorios en la cabecera")
        cls._comprobar_cifrado(ident, semilla, iv)
        parametros = formato.Variante.leer(bruto_kdf)

        transformada = cls._derivar(compuesta, parametros, conocida)
        base_hmac = formato.clave_hmac_base(semilla, transformada[1])
        if not hmac.compare_digest(formato.hmac_cabecera(base_hmac, cab.bruta), firma):
            raise CredencialesIncorrectas("la clave no abre la base")

        cifrada = formato.leer_bloques(datos, pos + 64, base_hmac)
        carga = cifrado.descifrar(ident, formato.clave_cifrado(semilla, transformada[1]), iv, cifrada)
        carga = cls._descomprimir(carga, compresion)

        interior, inicio_xml = formato.leer_tlv(carga, 0, fin=formato.INT_FIN)
        flujo_id, flujo_clave, adjuntos = None, None, []
        for i, v in interior:
            if i == formato.INT_FLUJO_ID:
                flujo_id = struct.unpack("<I", v)[0]
            elif i == formato.INT_FLUJO_CLAVE:
                flujo_clave = v
            elif i == formato.INT_ADJUNTO:
                adjuntos.append(Adjunto(datos=v[1:], protegido=bool(v[:1] and v[0] & 1)))
        if flujo_id is None or flujo_clave is None:
            raise FicheroDanado("cabecera interior sin flujo de protección")

        arbol = cls._parsear(carga[inicio_xml:])
        _desproteger(arbol.getroot(), cifrado.FlujoInterior(flujo_id, flujo_clave))
        conocidos = (formato.CAB_FIN, formato.CAB_CIFRADO, formato.CAB_COMPRESION, formato.CAB_SEMILLA,
                     formato.CAB_IV, formato.CAB_KDF, formato.CAB_DATOS_PUBLICOS)
        return cls(version=cab.version, cifrado=ident, compresion=compresion, kdf=parametros,
                   datos_publicos=cab.campo(formato.CAB_DATOS_PUBLICOS), flujo_id=flujo_id,
                   adjuntos=adjuntos, xml=arbol, compuesta=compuesta,
                   campos_desconocidos=[(i, v) for i, v in cab.campos if i not in conocidos],
                   _transformada=transformada)

    @classmethod
    def _abrir_v3(cls, datos, cab, pos, compuesta, conocida) -> "Base":
        ident, semilla, iv = cab.campo(formato.CAB_CIFRADO), cab.campo(formato.CAB_SEMILLA), cab.campo(formato.CAB_IV)
        semilla_t, rondas = cab.campo(formato.CAB_SEMILLA_TRANSFORMACION), cab.campo(formato.CAB_RONDAS)
        clave_flujo, inicio = cab.campo(formato.CAB_CLAVE_FLUJO), cab.campo(formato.CAB_BYTES_INICIO)
        flujo = cab.campo(formato.CAB_FLUJO_ID)
        if not all((ident, semilla, iv, semilla_t, rondas, clave_flujo, inicio, flujo)):
            raise FicheroDanado("faltan campos obligatorios en la cabecera KDBX 3.1")
        cls._comprobar_cifrado(ident, semilla, iv)
        compresion = struct.unpack("<I", cab.campo(formato.CAB_COMPRESION) or bytes(4))[0]
        parametros = formato.Variante()
        parametros.poner(formato.VD_BYTES, "$UUID", kdf.UUID_AES_KDF)
        parametros.poner(formato.VD_BYTES, "S", semilla_t)
        parametros.poner(formato.VD_UINT64, "R", struct.unpack("<Q", rondas)[0])

        transformada = cls._derivar(compuesta, parametros, conocida)
        try:
            claro = cifrado.descifrar(ident, formato.clave_cifrado(semilla, transformada[1]), iv, datos[pos:])
        except FicheroDanado as e:  # en 3.1 no hay HMAC: una clave errónea se ve como relleno roto
            raise CredencialesIncorrectas("la clave no abre la base") from e
        if not hmac.compare_digest(claro[:32], inicio):
            raise CredencialesIncorrectas("la clave no abre la base")
        carga = cls._descomprimir(formato.leer_bloques_sha(claro[32:]), compresion)

        arbol = cls._parsear(carga)
        flujo_id = struct.unpack("<I", flujo)[0]
        _desproteger(arbol.getroot(), cifrado.FlujoInterior(flujo_id, clave_flujo))
        suma = arbol.getroot().findtext("Meta/HeaderHash")
        if suma and base64.b64decode(suma) != hashlib.sha256(cab.bruta).digest():
            raise FicheroDanado("el hash de la cabecera guardado en la base no coincide")
        conocidos = (formato.CAB_FIN, formato.CAB_CIFRADO, formato.CAB_COMPRESION, formato.CAB_SEMILLA,
                     formato.CAB_SEMILLA_TRANSFORMACION, formato.CAB_RONDAS, formato.CAB_IV,
                     formato.CAB_CLAVE_FLUJO, formato.CAB_BYTES_INICIO, formato.CAB_FLUJO_ID)
        return cls(version=cab.version, cifrado=ident, compresion=compresion, kdf=parametros,
                   datos_publicos=None, flujo_id=flujo_id, adjuntos=[], xml=arbol, compuesta=compuesta,
                   campos_desconocidos=[(i, v) for i, v in cab.campos if i not in conocidos],
                   _transformada=transformada)

    @staticmethod
    def _comprobar_cifrado(ident: bytes, semilla: bytes, iv: bytes) -> None:
        if ident not in cifrado.TAM_IV:
            raise FormatoNoSoportado(f"cifrado {cifrado.NOMBRES.get(ident, ident.hex())}")
        if len(semilla) != 32 or len(iv) != cifrado.TAM_IV[ident]:
            raise FicheroDanado("semilla o IV con longitud incorrecta")

    @staticmethod
    def _descomprimir(carga: bytes, compresion: int) -> bytes:
        if compresion == 0:
            return carga
        if compresion == 1:
            try:
                return gzip.decompress(carga)
            except (OSError, EOFError) as e:
                raise FicheroDanado("carga comprimida ilegible") from e
        raise FormatoNoSoportado(f"compresión {compresion}")

    @staticmethod
    def _parsear(xml: bytes) -> etree._ElementTree:
        try:
            arbol = etree.ElementTree(etree.fromstring(xml, _parser()))
        except etree.XMLSyntaxError as e:
            raise FicheroDanado("XML interior ilegible") from e
        if arbol.docinfo.doctype or arbol.docinfo.internalDTD is not None:
            raise FicheroDanado("XML interior con DTD")
        return arbol

    # ── Creación ─────────────────────────────────────────────────────────────
    @classmethod
    def nueva(cls, nombre: str, contrasena: str | None = None, fichero_clave: bytes | None = None,
              *, cifrado_id: bytes = cifrado.UUID_CHACHA20, parametros_kdf: formato.Variante | None = None) -> "Base":
        """Base vacía KDBX 4.0: ChaCha20 + Argon2id calibrado a ~1 s, como decidimos en el diseño."""
        base = cls(version=formato.VERSION_4_0, cifrado=cifrado_id, compresion=1,
                   kdf=parametros_kdf or argon2id_por_defecto(iteraciones=calibrar_iteraciones()),
                   datos_publicos=None, flujo_id=cifrado.FLUJO_CHACHA20, adjuntos=[],
                   xml=etree.ElementTree(etree.Element("KeePassFile")),
                   compuesta=clave_compuesta(contrasena, fichero_clave))
        ahora = base.ahora()
        raiz = base.xml.getroot()
        meta = etree.SubElement(raiz, "Meta")
        for etiqueta, valor in (("Generator", "NARSIL Pass"), ("DatabaseName", nombre),
                                ("DatabaseNameChanged", ahora), ("DatabaseDescription", ""),
                                ("DatabaseDescriptionChanged", ahora), ("DefaultUserName", ""),
                                ("DefaultUserNameChanged", ahora), ("MaintenanceHistoryDays", "365"),
                                ("Color", ""), ("MasterKeyChanged", ahora), ("MasterKeyChangeRec", "-1"),
                                ("MasterKeyChangeForce", "-1")):
            etree.SubElement(meta, etiqueta).text = valor
        proteccion = etree.SubElement(meta, "MemoryProtection")
        for campo, activo in (("ProtectTitle", "False"), ("ProtectUserName", "False"), ("ProtectPassword", "True"),
                              ("ProtectURL", "False"), ("ProtectNotes", "False")):
            etree.SubElement(proteccion, campo).text = activo
        etree.SubElement(meta, "CustomIcons")
        for etiqueta, valor in (("RecycleBinEnabled", "True"), ("RecycleBinUUID", UUID_CERO),
                                ("RecycleBinChanged", ahora), ("EntryTemplatesGroup", UUID_CERO),
                                ("EntryTemplatesGroupChanged", ahora), ("LastSelectedGroup", UUID_CERO),
                                ("LastTopVisibleGroup", UUID_CERO), ("HistoryMaxItems", "10"),
                                ("HistoryMaxSize", "6291456")):
            etree.SubElement(meta, etiqueta).text = valor
        raiz_grupos = etree.SubElement(raiz, "Root")
        raiz_grupos.append(elemento_grupo(nombre or "Root", ahora))
        etree.SubElement(raiz_grupos, "DeletedObjects")
        return base

    def nueva_entrada(self, grupo: etree._Element, campos: dict[str, str],
                      protegidos: tuple[str, ...] = ("Password",)) -> etree._Element:
        entrada = etree.Element("Entry")
        etree.SubElement(entrada, "UUID").text = nuevo_uuid()
        etree.SubElement(entrada, "IconID").text = "0"
        for etiqueta in ("ForegroundColor", "BackgroundColor", "OverrideURL", "Tags"):
            etree.SubElement(entrada, etiqueta)
        entrada.append(elemento_tiempos(self.ahora()))
        estandar = ("Title", "UserName", "Password", "URL", "Notes")
        for clave in (*estandar, *[k for k in campos if k not in estandar]):
            s = etree.SubElement(entrada, "String")
            etree.SubElement(s, "Key").text = clave
            v = etree.SubElement(s, "Value")
            v.text = campos.get(clave, "")
            if clave in protegidos:
                v.set("Protected", "True")
        auto = etree.SubElement(entrada, "AutoType")
        etree.SubElement(auto, "Enabled").text = "True"
        etree.SubElement(auto, "DataTransferObfuscation").text = "0"
        etree.SubElement(entrada, "History")
        insertar_entrada(grupo, entrada)
        return entrada

    # ── Adjuntos (unifica KDBX 4 y 3.1) ──────────────────────────────────────
    def _binarios_v3(self) -> etree._Element:
        meta = self.xml.getroot().find("Meta")
        binarios = meta.find("Binaries")
        if binarios is None:
            binarios = etree.SubElement(meta, "Binaries")
        return binarios

    def adjunto(self, ref: int) -> bytes:
        if not self.es_v3:
            return self.adjuntos[ref].datos
        for b in self._binarios_v3().findall("Binary"):
            if b.get("ID") == str(ref):
                datos = base64.b64decode(b.text or "")
                return gzip.decompress(datos) if (b.get("Compressed") or "").lower() == "true" else datos
        raise KeyError(ref)

    def agregar_adjunto(self, datos: bytes, protegido: bool = False) -> int:
        """Añade un binario al almacén de la base y devuelve su referencia."""
        if not self.es_v3:
            for i, a in enumerate(self.adjuntos):  # sin duplicados, como KeePass
                if a.datos == datos:
                    return i
            self.adjuntos.append(Adjunto(datos, protegido))
            return len(self.adjuntos) - 1
        binarios = self._binarios_v3()
        ids = [int(b.get("ID")) for b in binarios.findall("Binary") if (b.get("ID") or "").isdigit()]
        nuevo = max(ids, default=-1) + 1
        b = etree.SubElement(binarios, "Binary", ID=str(nuevo), Compressed="True")
        b.text = base64.b64encode(gzip.compress(datos, mtime=0)).decode("ascii")
        return nuevo

    def limpiar_adjuntos(self) -> None:
        """Quita del almacén los binarios que ya no referencia ninguna entrada (ni su historial)."""
        usados = {int(v.get("Ref")) for v in self.xml.getroot().iter("Value")
                  if (v.get("Ref") or "").isdigit()}
        if self.es_v3:
            for b in list(self._binarios_v3().findall("Binary")):
                if (b.get("ID") or "").isdigit() and int(b.get("ID")) not in usados:
                    b.getparent().remove(b)
            return
        nuevos, mapa = [], {}
        for i, a in enumerate(self.adjuntos):
            if i in usados:
                mapa[i] = len(nuevos)
                nuevos.append(a)
        for v in self.xml.getroot().iter("Value"):
            r = v.get("Ref")
            if r is not None and r.isdigit() and int(r) in mapa:
                v.set("Ref", str(mapa[int(r)]))
        self.adjuntos = nuevos

    # ── Conversión ───────────────────────────────────────────────────────────
    def convertir_a_kdbx4(self, parametros_kdf: formato.Variante | None = None) -> None:
        """Pasa una base 3.1 a KDBX 4.0 conservando todo su contenido (a petición del usuario)."""
        if not self.es_v3:
            return
        raiz = self.xml.getroot()
        for elem in raiz.iter(*ETIQUETAS_FECHA):
            d = fecha_kdbx(elem.text)
            if d is not None:
                elem.text = texto_fecha_kdbx(d)
        binarios = raiz.find("Meta/Binaries")
        mapa = {}
        if binarios is not None:
            for b in binarios.findall("Binary"):
                datos = base64.b64decode(b.text or "")
                if (b.get("Compressed") or "").lower() == "true":
                    datos = gzip.decompress(datos)
                mapa[b.get("ID")] = len(self.adjuntos)
                self.adjuntos.append(Adjunto(datos, (b.get("Protected") or "").lower() == "true"))
            binarios.getparent().remove(binarios)
        for v in raiz.iter("Value"):
            if v.get("Ref") is not None and v.get("Ref") in mapa:
                v.set("Ref", str(mapa[v.get("Ref")]))
        suma = raiz.find("Meta/HeaderHash")
        if suma is not None:
            suma.getparent().remove(suma)
        self.version = formato.VERSION_4_0
        self.flujo_id = cifrado.FLUJO_CHACHA20
        if parametros_kdf is not None:
            self.kdf = parametros_kdf
        kdf.renovar_sal(self.kdf)
        self._transformada = None
        self.campos_desconocidos = [(i, v) for i, v in self.campos_desconocidos if i != formato.CAB_COMENTARIO]

    # ── Escritura ────────────────────────────────────────────────────────────
    def serializar(self) -> bytes:
        """Fichero completo en el formato de la base. Semilla maestra, IV y clave interior nuevas en
        cada guardado; la sal de la KDF solo cambia con la clave maestra (como KeePassXC)."""
        return self._serializar_v3() if self.es_v3 else self._serializar_v4()

    def _serializar_v4(self) -> bytes:
        semilla, iv = os.urandom(32), os.urandom(cifrado.TAM_IV[self.cifrado])
        transformada = self._clave_transformada()
        base_hmac = formato.clave_hmac_base(semilla, transformada)
        campos = [(formato.CAB_CIFRADO, self.cifrado),
                  (formato.CAB_COMPRESION, struct.pack("<I", self.compresion)),
                  (formato.CAB_SEMILLA, semilla), (formato.CAB_IV, iv),
                  (formato.CAB_KDF, self.kdf.escribir())]
        if self.datos_publicos is not None:
            campos.append((formato.CAB_DATOS_PUBLICOS, self.datos_publicos))
        campos += self.campos_desconocidos
        campos.append((formato.CAB_FIN, b"\r\n\r\n"))
        cabecera = struct.pack("<III", formato.FIRMA_1, formato.FIRMA_2, self.version) + formato.escribir_tlv(campos)

        clave_flujo = os.urandom(64)
        interior = [(formato.INT_FLUJO_ID, struct.pack("<I", cifrado.FLUJO_CHACHA20)),
                    (formato.INT_FLUJO_CLAVE, clave_flujo)]
        interior += [(formato.INT_ADJUNTO, bytes([1 if a.protegido else 0]) + a.datos) for a in self.adjuntos]
        interior.append((formato.INT_FIN, b""))
        self.flujo_id = cifrado.FLUJO_CHACHA20
        copia = copy.deepcopy(self.xml.getroot())
        _proteger(copia, cifrado.FlujoInterior(cifrado.FLUJO_CHACHA20, clave_flujo))
        carga = formato.escribir_tlv(interior) + etree.tostring(copia, xml_declaration=True, encoding="UTF-8",
                                                                  standalone=True)
        if self.compresion == 1:
            carga = gzip.compress(carga, mtime=0)
        cifrada = cifrado.cifrar(self.cifrado, formato.clave_cifrado(semilla, transformada), iv, carga)
        return (cabecera + hashlib.sha256(cabecera).digest() + formato.hmac_cabecera(base_hmac, cabecera)
                + formato.escribir_bloques(cifrada, base_hmac))

    def _serializar_v3(self) -> bytes:
        semilla, iv = os.urandom(32), os.urandom(cifrado.TAM_IV[self.cifrado])
        clave_flujo, inicio = os.urandom(32), os.urandom(32)
        transformada = self._clave_transformada()
        campos = [(formato.CAB_CIFRADO, self.cifrado),
                  (formato.CAB_COMPRESION, struct.pack("<I", self.compresion)),
                  (formato.CAB_SEMILLA, semilla),
                  (formato.CAB_SEMILLA_TRANSFORMACION, self.kdf.get("S")),
                  (formato.CAB_RONDAS, struct.pack("<Q", int(self.kdf.get("R")))),
                  (formato.CAB_IV, iv), (formato.CAB_CLAVE_FLUJO, clave_flujo),
                  (formato.CAB_BYTES_INICIO, inicio),
                  (formato.CAB_FLUJO_ID, struct.pack("<I", self.flujo_id))]
        campos += self.campos_desconocidos
        campos.append((formato.CAB_FIN, b"\r\n\r\n"))
        cabecera = (struct.pack("<III", formato.FIRMA_1, formato.FIRMA_2, self.version)
                    + formato.escribir_tlv(campos, ancho=2))

        # El hash de la cabecera va dentro del XML (Meta/HeaderHash), detrás de Generator.
        meta = self.xml.getroot().find("Meta")
        suma = meta.find("HeaderHash")
        if suma is None:
            suma = etree.Element("HeaderHash")
            generador = meta.find("Generator")
            if generador is not None:
                generador.addnext(suma)
            else:
                meta.insert(0, suma)
        suma.text = base64.b64encode(hashlib.sha256(cabecera).digest()).decode("ascii")

        copia = copy.deepcopy(self.xml.getroot())
        _proteger(copia, cifrado.FlujoInterior(self.flujo_id, clave_flujo))
        carga = etree.tostring(copia, xml_declaration=True, encoding="UTF-8", standalone=True)
        if self.compresion == 1:
            carga = gzip.compress(carga, mtime=0)
        claro = inicio + formato.escribir_bloques_sha(carga)
        return cabecera + cifrado.cifrar(self.cifrado, formato.clave_cifrado(semilla, transformada), iv, claro)

    def guardar(self, ruta: str | os.PathLike, *, copia_previa: bool = False) -> None:
        """Guardado seguro: temporal en la misma carpeta, se relee y descifra, y solo entonces
        sustituye al original. Nunca se pisa una base buena con una que no se pueda abrir."""
        ruta = os.fspath(ruta)
        datos = self.serializar()
        verificada = Base.abrir(datos, compuesta=self.compuesta, _transformada=self._transformada)
        # Forma canónica (C14N): <X/> y <X></X> son el mismo dato.
        if (etree.tostring(verificada.xml.getroot(), method="c14n")
                != etree.tostring(self.xml.getroot(), method="c14n")
                or [a.datos for a in verificada.adjuntos] != [a.datos for a in self.adjuntos]):
            raise FicheroDanado("la verificación del guardado no reproduce la base")
        carpeta = os.path.dirname(os.path.abspath(ruta)) or "."
        temporal = os.path.join(carpeta, f".{os.path.basename(ruta)}.{os.getpid()}.tmp")
        try:
            modo = os.stat(ruta).st_mode & 0o777
        except OSError:
            modo = 0o600
        try:
            escribir_privado(temporal, datos, modo)
            if copia_previa and os.path.exists(ruta):
                with open(ruta, "rb") as original:
                    previo = original.read()
                bak = ruta + ".bak"
                if os.path.lexists(bak):
                    os.remove(bak)  # nunca escribir a través de un enlace ya existente
                escribir_privado(bak, previo, modo)
            os.replace(temporal, ruta)
        finally:
            if os.path.exists(temporal):
                os.remove(temporal)

    # ── Consulta ─────────────────────────────────────────────────────────────
    @property
    def raiz(self) -> etree._Element:
        grupo = self.xml.getroot().find("Root/Group")
        if grupo is None:
            raise FicheroDanado("la base no tiene grupo raíz")
        return grupo

    @property
    def meta(self) -> etree._Element:
        return self.xml.getroot().find("Meta")

    @property
    def nombre(self) -> str:
        return self.xml.getroot().findtext("Meta/DatabaseName") or ""

    def entradas(self, incluir_historial: bool = False):
        """Entradas vivas (sin las del historial salvo que se pida), en orden de documento."""
        for e in self.raiz.iter("Entry"):
            if incluir_historial or e.getparent().tag != "History":
                yield e


def escribir_privado(ruta: str, datos: bytes, modo: int = 0o600) -> None:
    """Crea `ruta` (debe no existir) sin seguir enlaces simbólicos, con permisos `modo` (0600 por
    defecto) y en binario también en Windows; vuelca a disco antes de cerrar."""
    if os.name == "nt":
        modo = 0o600  # en Windows el modo solo decide «solo lectura»; los permisos son ACL heredadas
    banderas = (os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0)
                | getattr(os, "O_NOFOLLOW", 0))
    fd = os.open(ruta, banderas, modo & 0o666)
    with os.fdopen(fd, "wb") as f:
        f.write(datos)
        f.flush()
        os.fsync(f.fileno())
    if os.name != "nt":
        os.chmod(ruta, modo & 0o666)  # por encima de la umask: hereda los del original


# ── Elementos XML ────────────────────────────────────────────────────────────

def nuevo_uuid() -> str:
    return base64.b64encode(_uuid.uuid4().bytes).decode("ascii")


def elemento_tiempos(ahora: str) -> etree._Element:
    t = etree.Element("Times")
    for etiqueta, valor in (("LastModificationTime", ahora), ("CreationTime", ahora), ("LastAccessTime", ahora),
                            ("ExpiryTime", ahora), ("Expires", "False"), ("UsageCount", "0"),
                            ("LocationChanged", ahora)):
        etree.SubElement(t, etiqueta).text = valor
    return t


def elemento_grupo(nombre: str, ahora: str) -> etree._Element:
    g = etree.Element("Group")
    etree.SubElement(g, "UUID").text = nuevo_uuid()
    etree.SubElement(g, "Name").text = nombre
    etree.SubElement(g, "Notes")
    etree.SubElement(g, "IconID").text = "48"
    g.append(elemento_tiempos(ahora))
    etree.SubElement(g, "IsExpanded").text = "True"
    etree.SubElement(g, "DefaultAutoTypeSequence")
    etree.SubElement(g, "EnableAutoType").text = "null"
    etree.SubElement(g, "EnableSearching").text = "null"
    etree.SubElement(g, "LastTopVisibleEntry").text = UUID_CERO
    return g


def insertar_entrada(grupo: etree._Element, entrada: etree._Element) -> None:
    """Las entradas van delante de los subgrupos, como las escriben KeePass y KeePassXC."""
    subgrupos = grupo.findall("Group")
    if subgrupos:
        subgrupos[0].addprevious(entrada)
    else:
        grupo.append(entrada)


def campos_entrada(entrada: etree._Element) -> dict[str, str]:
    """Campos de texto de una entrada (Title, UserName, Password, URL, Notes y personalizados)."""
    salida = {}
    for s in entrada.findall("String"):
        clave = s.findtext("Key")
        valor = s.find("Value")
        if clave is not None:
            salida[clave] = (valor.text or "") if valor is not None else ""
    return salida


# ── Protección de valores ────────────────────────────────────────────────────

def _es_protegido(elem: etree._Element) -> bool:
    return (elem.get("Protected") or "").strip().lower() == "true"


def _es_binario(elem: etree._Element) -> bool:
    """Los adjuntos protegidos (KDBX 3.1) son bytes, no texto: se guardan en base64 en el árbol."""
    padre = elem.getparent()
    return elem.tag == "Binary" or (elem.tag == "Value" and padre is not None and padre.tag == "Binary")


def _proteger(raiz: etree._Element, flujo: cifrado.FlujoInterior) -> None:
    """Inverso de `_desproteger`: cifra en su sitio, en el mismo orden de documento."""
    for elem in raiz.iter():
        if isinstance(elem.tag, str) and _es_protegido(elem):
            claro = base64.b64decode(elem.text or "") if _es_binario(elem) else (elem.text or "").encode("utf-8")
            elem.text = base64.b64encode(flujo.aplicar(claro)).decode("ascii")


def _desproteger(raiz: etree._Element, flujo: cifrado.FlujoInterior) -> None:
    """Descifra en su sitio todos los valores con Protected="True", en orden de documento."""
    for elem in raiz.iter():
        if not isinstance(elem.tag, str) or not _es_protegido(elem):
            continue
        try:
            claro = flujo.aplicar(base64.b64decode(elem.text or "", validate=True))
        except ValueError as e:
            raise FicheroDanado("valor protegido que no es base64") from e
        if _es_binario(elem):
            elem.text = base64.b64encode(claro).decode("ascii")
            continue
        try:
            elem.text = claro.decode("utf-8")
        except UnicodeDecodeError as e:
            raise FicheroDanado("valor protegido ilegible tras descifrar") from e
