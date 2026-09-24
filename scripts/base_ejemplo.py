"""Base de ejemplo sintética para pruebas y comparación: todos los tipos de campo que maneja NARSIL Pass.

    .venv/bin/python scripts/base_ejemplo.py <carpeta_salida>

Genera NARSIL-ejemplo-KDBX4.kdbx y NARSIL-ejemplo-KDBX31.kdbx (la 3.1 la crea keepassxc-cli y la rellena
NARSIL Pass, como le pasaría a una base migrada) y LEEME.md con el inventario. Todos los
datos son inventados: nombres, cuentas, teléfonos y claves no corresponden a nadie.
"""
from __future__ import annotations

import shutil
import struct
import subprocess
import sys
import zlib
from datetime import datetime, timedelta, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from nucleo import kdf  # noqa: E402
from nucleo.base import Base, texto_fecha_iso, texto_fecha_kdbx  # noqa: E402
from nucleo.boveda import Boveda  # noqa: E402

CLAVE = "NarsilEjemplo-2026"
SECCIONES = {"interno": "Servicios internos", "externo": "Servicios externos", "identidades": "Identidades operativas"}
AHORA = datetime.now(timezone.utc)


LEEME = """# Base de ejemplo de NARSIL Pass

Base **sintética y completa** para ver cómo queda una base bien alimentada. Todos los datos son
inventados: nombres, cuentas, teléfonos, direcciones y claves no corresponden a nadie, y las fotos son
siluetas generadas.

**Contraseña maestra de las dos bases: `NarsilEjemplo-2026`**

| Fichero | Formato |
|---|---|
| `NARSIL-ejemplo-KDBX4.kdbx` | KDBX 4.0 · ChaCha20 · Argon2id. Creada y rellenada por NARSIL Pass. |
| `NARSIL-ejemplo-KDBX31.kdbx` | KDBX 3.1 · AES-256 · AES-KDF. Creada por KeePassXC y rellenada por NARSIL Pass, como una base migrada; sigue en 3.1 al guardar. |

Las dos tienen el mismo contenido y sirven para comparar los dos formatos. Trabaje sobre una copia si
quiere modificarlas.

## Cómo compararla con una base propia

1. Cree su base en NARSIL Pass y reproduzca a mano las entradas de abajo.
2. Abra las dos en NARSIL Pass y compare pestaña a pestaña: Ficha, Servicios, Fotos, Biografía, Historial.
3. Ábralas también en KeePassXC: cada identidad se ve con sus campos `Ficha.*` y `Servicio.N.*` como
   atributos adicionales, las fotos como adjuntos y las secciones como grupos normales.
4. Para una comparación exhaustiva, exporte las dos a XML desde KeePassXC (*Base de datos → Exportar a
   XML*) y compare los ficheros: las fechas y los identificadores internos serán distintos; el resto
   debe coincidir.

## Estructura

12 grupos contando la raíz y la papelera, 15 entradas más 1 en la papelera y 7 versiones de historial.
Añadir adjuntos o fotos guarda una versión anterior de la entrada, como en KeePassXC; por eso la VPN, el
servidor de copias y las identidades con fotos tienen una versión en su historial.

**Servicios internos**

| Entrada | Qué muestra |
|---|---|
| Intranet de la unidad | Campos estándar y etiquetas; contraseña **repetida** con un servicio de Marta Ribas |
| Infraestructura / VPN corporativa | Adjunto de texto; contraseña de hace 400 días: **pendiente de renovar** |
| Infraestructura / Servidor de análisis | Campo propio «Puerto» y campo **protegido** «Clave API»; **caduca en 6 días** |
| Infraestructura / Servidor de copias | Código **TOTP**, adjunto de texto y etiquetas |
| Aplicaciones de la unidad / Gestor documental | **Historial**: tres versiones de la contraseña, dos restaurables |

**Servicios externos**

| Entrada | Qué muestra |
|---|---|
| Registros oficiales / Registro mercantil | **Caducada** hace 3 días |
| Registros oficiales / Catastro | Caduca dentro de un año (sin aviso) |
| Correo y mensajería / Correo de la operación | TOTP, notas de varias líneas y dos etiquetas |
| Fuentes abiertas / Foro de seguridad | Contraseña **débil** («1234») |
| Fuentes abiertas / Plataforma de monitorización | Campos propios «Plan» y «Límite de consultas», y **protegido** «Clave API privada» |

**Identidades operativas**

| Identidad | Qué muestra |
|---|---|
| Operación Norte / Marta Ribas | **Activa.** Ficha completa (los siete bloques), cuenta principal, biografía, 3 servicios (Instagram, Correo, Telegram), 3 fotos y un documento de leyenda. La cuenta principal y el servicio «Correo» son la misma cuenta: no cuenta como repetida. |
| Operación Norte / Iker Solano | **En reposo.** Ficha a medio completar, 2 servicios (LinkedIn, GitHub), 1 foto y notas |
| Reserva / Lucía Ferrer | **Comprometida.** Pautas de actuación, 1 servicio, 1 foto y la etiqueta «revisar» |
| Reserva / Daniel Ortega | **Retirada.** Ficha mínima, sin servicios ni fotos |

**Fuera de las secciones:** «Entrada sin clasificar», en la raíz (se ve en *Toda la base*, bloque «Sin
sección»). **Papelera:** «Cuenta antigua de pruebas».

## Lo que debe mostrar Salud

Repetidas 1 · Débiles 1 · A renovar 1 · Caducidad 2 (una caducada y una que caduca pronto), con la
renovación configurada cada 180 días. Las fechas son relativas al momento en que se generó la base:
con el paso del tiempo, lo que «caduca pronto» pasará a caducado.

La base se regenera con `.venv/bin/python scripts/base_ejemplo.py ejemplos` (necesita `keepassxc-cli`).
"""


# ── Fotos sintéticas (PNG sin dependencias) ──────────────────────────────────
def _png(ancho: int, alto: int, pixel) -> bytes:
    filas = b"".join(b"\x00" + b"".join(bytes(pixel(x, y)) for x in range(ancho)) for y in range(alto))
    def trozo(tipo: bytes, datos: bytes) -> bytes:
        return struct.pack(">I", len(datos)) + tipo + datos + struct.pack(">I", zlib.crc32(tipo + datos) & 0xFFFFFFFF)
    return (b"\x89PNG\r\n\x1a\n" + trozo(b"IHDR", struct.pack(">IIBBBBB", ancho, alto, 8, 2, 0, 0, 0))
            + trozo(b"IDAT", zlib.compress(filas, 9)) + trozo(b"IEND", b""))


def retrato(fondo: tuple, piel: tuple, pelo: tuple, ropa: tuple, n: int = 240) -> bytes:
    """Silueta de avatar: fondo en degradado, cabeza, pelo y hombros. Claramente sintética."""
    def pixel(x, y):
        cx, cy, r = n / 2, n * 0.42, n * 0.19
        if (x - cx) ** 2 + (y - cy) ** 2 < r * r:
            return pelo if y < cy - r * 0.25 else piel
        if y > n * 0.72 and abs(x - cx) < (y - n * 0.62) * 1.25:
            return ropa
        k = (x + y) / (2 * n)
        return tuple(int(a * (1 - k) + b * k) for a, b in zip(fondo, (20, 27, 46)))
    return _png(n, n, pixel)


# ── Utilidades de datos ──────────────────────────────────────────────────────
def c(**campos) -> list[dict]:
    return [{"clave": k, "valor": v, "protegido": k in ("Password", "otp")} for k, v in campos.items()]


def campos(d: dict, protegidos: tuple = ()) -> list[dict]:
    return [{"clave": k, "valor": v, "protegido": k == "Password" or k.endswith(".contrasena") or k in protegidos}
            for k, v in d.items()]


def envejecer(b: Boveda, uuid: str, dias: int) -> None:
    """Fecha la entrada (y su historial, escalonado) hacia atrás, para que la salud tenga qué medir."""
    e = b._entrada(uuid)
    fecha = texto_fecha_iso if b.base.es_v3 else texto_fecha_kdbx
    versiones = e.findall("History/Entry")
    for i, v in enumerate(versiones):
        momento = AHORA - timedelta(days=dias + (len(versiones) - i) * 30)
        for etiqueta in ("CreationTime", "LastModificationTime", "LastAccessTime"):
            t = v.find("Times/" + etiqueta)
            if t is not None:
                t.text = fecha(momento)
    for etiqueta in ("CreationTime", "LastModificationTime", "LastAccessTime"):
        e.find("Times/" + etiqueta).text = fecha(AHORA - timedelta(days=dias))
    b._cambio()


def rellenar(b: Boveda) -> dict:
    s = b.preparar_secciones(SECCIONES)
    g = {"infra": b.crear_grupo(s["interno"], "Infraestructura"), "apps": b.crear_grupo(s["interno"], "Aplicaciones de la unidad"),
         "fuentes": b.crear_grupo(s["externo"], "Fuentes abiertas"), "registros": b.crear_grupo(s["externo"], "Registros oficiales"),
         "correo": b.crear_grupo(s["externo"], "Correo y mensajería"),
         "norte": b.crear_grupo(s["identidades"], "Operación Norte"), "reserva": b.crear_grupo(s["identidades"], "Reserva")}
    fecha = lambda d: (AHORA + timedelta(days=d)).isoformat()  # noqa: E731
    compartida = "Rb8#tLq2!Vn4-Compartida"

    # Servicios internos
    b.crear_entrada(s["interno"], c(Title="Intranet de la unidad", UserName="analista.07", Password=compartida,
                                    URL="https://intranet.unidad.local", Notes="Acceso con la cuenta de dominio."), ["interno", "dominio"])
    vpn = b.crear_entrada(g["infra"], c(Title="VPN corporativa", UserName="analista.07", Password="correcto-caballo-bateria-grapa",
                                        URL="vpn.unidad.local", Notes="Perfil WireGuard en el portátil de la unidad."), ["vpn"])
    b.agregar_adjuntos(vpn, [("perfil-wg-EJEMPLO.conf", b"[Interface]\n# PERFIL SINTETICO DE EJEMPLO\nAddress = 10.99.0.7/32\n")])
    envejecer(b, vpn, 400)
    b.crear_entrada(g["infra"], campos({"Title": "Servidor de análisis", "UserName": "admin", "Password": "kQ9!mZ4#pX7@-analisis",
                                        "URL": "https://analisis.unidad.local:8443", "Notes": "", "Puerto": "8443",
                                        "Clave API": "ejemplo-0000-1111-2222-3333"}, ("Clave API",)), ["servidor"], expira=fecha(6))
    copias = b.crear_entrada(g["infra"], c(Title="Servidor de copias", UserName="backup", Password="Tq3$zN8!wL5@-copias",
                                           URL="ssh://copias.unidad.local", Notes="Acceso SSH con clave.",
                                           otp="otpauth://totp/NARSIL:copias?secret=JBSWY3DPEHPK3PXP&period=30&digits=6"), ["ssh", "2fa"])
    b.agregar_adjuntos(copias, [("clave-ssh-EJEMPLO.txt", b"-----BEGIN CLAVE DE EJEMPLO-----\nNO ES UNA CLAVE REAL\n-----END CLAVE DE EJEMPLO-----\n")])
    gestor = b.crear_entrada(g["apps"], c(Title="Gestor documental", UserName="a.ruiz", Password="Version-1!aaaa", URL="https://docs.unidad.local"))
    b.editar_entrada(gestor, c(Title="Gestor documental", UserName="a.ruiz", Password="Version-2!bbbb", URL="https://docs.unidad.local"))
    b.editar_entrada(gestor, c(Title="Gestor documental", UserName="a.ruiz", Password="Version-3!cccc-actual", URL="https://docs.unidad.local",
                               Notes="Tres versiones: el historial guarda las dos anteriores."), ["historial"])
    envejecer(b, gestor, 20)

    # Servicios externos
    b.crear_entrada(g["registros"], c(Title="Registro mercantil", UserName="unidad.analisis", Password="Hy7@pL3!xC6&-registro",
                                      URL="https://www.registradores.org"), ["registro"], expira=fecha(-3))
    b.crear_entrada(g["registros"], c(Title="Catastro", UserName="unidad.analisis", Password="Pz4!kW9#rM2$-catastro",
                                      URL="https://www.sedecatastro.gob.es"), ["registro"], expira=fecha(365))
    b.crear_entrada(g["correo"], c(Title="Correo de la operación", UserName="norte.analisis@proton.example", Password="V7#qz!Lr9@kTm2$w",
                                   URL="https://mail.proton.me", Notes="Buzón compartido del equipo.\nRevisar a diario.",
                                   otp="otpauth://totp/NARSIL:norte?secret=GEZDGNBVGY3TQOJQ&period=30&digits=6"), ["correo", "equipo"])
    b.crear_entrada(g["fuentes"], c(Title="Foro de seguridad", UserName="n0rte", Password="1234", URL="https://foro.example",
                                    Notes="Contraseña débil a propósito: la detecta Salud."))
    b.crear_entrada(g["fuentes"], campos({"Title": "Plataforma de monitorización", "UserName": "unidad@monitor.example",
                                          "Password": "Mn6$vB1!qX8@-monitor", "URL": "https://monitor.example", "Notes": "",
                                          "Plan": "Profesional", "Límite de consultas": "10.000 al mes",
                                          "Clave API privada": "ejemplo-api-9999"}, ("Clave API privada",)),
                    ["osint", "suscripción"], expira=fecha(200))

    # Identidades operativas
    marta = b.crear_entrada(g["norte"], campos({
        "Title": "Marta Ribas", "UserName": "marta.ribas.viajes@correo.example", "Password": "kH3!pQ9z#Lm2-x8Vr", "URL": "https://correo.example",
        "Notes": "", "NARSIL.Tipo": "identidad",
        "Ficha.nombre": "Marta", "Ficha.apellidos": "Ribas Soler", "Ficha.alias": "martaviaja_ejemplo", "Ficha.genero": "Mujer",
        "Ficha.fecha_nacimiento": "1991-04-17", "Ficha.edad": "35", "Ficha.lugar_nacimiento": "Valencia", "Ficha.nacionalidad": "Española",
        "Ficha.origen": "Comunidad Valenciana", "Ficha.idiomas": "Español, valenciano, inglés (B2), portugués básico",
        "Ficha.pais_residencia": "Portugal", "Ficha.ciudad_residencia": "Lisboa", "Ficha.direccion": "Rua de Exemplo 12, 3.º (ficticia)",
        "Ficha.codigo_postal": "1100-000", "Ficha.telefono": "+351 900 000 000", "Ficha.correo": "marta.ribas.viajes@correo.example",
        "Ficha.correo_recuperacion": "m.ribas.recupera@correo.example",
        "Ficha.estudios": "Grado en Bellas Artes", "Ficha.centro_estudios": "Universidad de ejemplo", "Ficha.profesion": "Fotógrafa de viajes",
        "Ficha.lugar_trabajo": "Autónoma", "Ficha.cargo": "Fotógrafa freelance",
        "Ficha.trayectoria": "2014-2018: prácticas en un estudio.\n2019-2022: agencia de viajes.\nDesde 2022: autónoma en Lisboa.",
        "Ficha.estatura": "1,68 m", "Ficha.complexion": "Delgada", "Ficha.ojos": "Marrones", "Ficha.pelo": "Castaño, media melena",
        "Ficha.rasgos": "Lunar en la mejilla izquierda. Gafas de pasta en las fotos de estudio.",
        "Ficha.estado_civil": "Soltera", "Ficha.familia": "Padres en Valencia; un hermano menor en Madrid.",
        "Ficha.intereses": "Fotografía analógica, senderismo, cocina asiática.", "Ficha.cultura": "Indie español, cine de autor, novela negra.",
        "Ficha.deportes": "Senderismo, yoga", "Ficha.mascotas": "Una gata (Nori)", "Ficha.vehiculo": "No tiene",
        "Ficha.dispositivo": "Android dedicado", "Ficha.sistema": "Android 15", "Ficha.navegador": "Navegador del sistema",
        "Ficha.huso_horario": "Europe/Lisbon", "Ficha.ubicacion_conexion": "Salida por Lisboa", "Ficha.sim": "Prepago portuguesa (ficticia)",
        "Ficha.red_contactos": "Tres fotógrafos de Lisboa y una revista de viajes.",
        "Ficha.estado": "activa", "Ficha.operacion": "Operación Norte", "Ficha.responsable": "Analista 07", "Ficha.creada_el": "2026-05-27",
        "Ficha.cobertura": "Fotógrafa freelance que vende reportajes de viaje a revistas pequeñas.",
        "Ficha.pautas": "No interactuar con perfiles de la investigación durante el primer mes.",
        "Ficha.biografia": "Nació en Valencia en 1991. Estudió Bellas Artes y se especializó en fotografía documental.\n\n"
                           "Desde 2022 vive en Lisboa, trabaja por encargo y publica sus viajes en Instagram. Escribe en español "
                           "informal, sin emojis, y suele responder por la tarde.",
        "Servicio.1.nombre": "Instagram", "Servicio.1.url": "https://www.instagram.com/martaviaja_ejemplo", "Servicio.1.id": "5800000001",
        "Servicio.1.usuario": "martaviaja_ejemplo", "Servicio.1.alias": "Marta · viajes", "Servicio.1.correo": "marta.ribas.viajes@correo.example",
        "Servicio.1.contrasena": compartida, "Servicio.1.notas": "Contraseña repetida a propósito con la intranet: la detecta Salud.",
        "Servicio.2.nombre": "Correo", "Servicio.2.url": "https://correo.example", "Servicio.2.usuario": "marta.ribas.viajes@correo.example",
        "Servicio.2.telefono": "+351 900 000 000", "Servicio.2.contrasena": "kH3!pQ9z#Lm2-x8Vr",
        "Servicio.3.nombre": "Telegram", "Servicio.3.id": "6000000001", "Servicio.3.usuario": "@martaviaja_ejemplo",
        "Servicio.3.telefono": "+351 900 000 000", "Servicio.3.notas": "Sesión solo en el Android dedicado.",
    }), ["virtual-humint"])
    b.agregar_adjuntos(marta, [
        ("retrato-perfil.png", retrato((58, 74, 110), (217, 179, 154), (75, 46, 34), (42, 54, 86))),
        ("viaje-lisboa.png", retrato((159, 106, 87), (224, 192, 168), (42, 26, 20), (60, 70, 100))),
        ("estudio.png", retrato((95, 127, 158), (202, 160, 137), (107, 70, 48), (30, 40, 70))),
        ("leyenda-EJEMPLO.txt", "Leyenda de ejemplo de la identidad Marta Ribas (datos inventados).\n".encode()),
    ])
    iker = b.crear_entrada(g["norte"], campos({
        "Title": "Iker Solano", "UserName": "", "Password": "", "URL": "", "Notes": "Ficha a medio completar a propósito.",
        "NARSIL.Tipo": "identidad", "Ficha.nombre": "Iker", "Ficha.apellidos": "Solano", "Ficha.profesion": "Técnico de sistemas",
        "Ficha.ciudad_residencia": "Bilbao", "Ficha.estado": "reposo", "Ficha.operacion": "Operación Norte",
        "Servicio.1.nombre": "LinkedIn", "Servicio.1.url": "https://www.linkedin.com", "Servicio.1.usuario": "iker.solano.ejemplo",
        "Servicio.1.contrasena": "Mw5#tR8!yU2@oP7s",
        "Servicio.2.nombre": "GitHub", "Servicio.2.usuario": "isolano-ejemplo", "Servicio.2.contrasena": "Gh2!nB7#sQ4$-dev",
    }))
    b.agregar_adjuntos(iker, [("perfil.png", retrato((70, 90, 70), (210, 170, 140), (40, 30, 25), (50, 50, 60)))])
    lucia = b.crear_entrada(g["reserva"], campos({
        "Title": "Lucía Ferrer", "UserName": "lucia.ferrer@correo.example", "Password": "Lf9!xR2#mK7$-lucia", "URL": "", "Notes": "",
        "NARSIL.Tipo": "identidad", "Ficha.nombre": "Lucía", "Ficha.apellidos": "Ferrer", "Ficha.estado": "comprometida",
        "Ficha.pautas": "No reutilizar: posible exposición detectada en el último servicio.",
        "Servicio.1.nombre": "X", "Servicio.1.usuario": "@luciaferrer_ejemplo", "Servicio.1.contrasena": "Xq8!vL3#pN6$-x",
    }), ["revisar"])
    b.agregar_adjuntos(lucia, [("perfil.png", retrato((110, 60, 60), (230, 196, 170), (120, 60, 30), (40, 40, 40)))])
    b.crear_entrada(g["reserva"], campos({
        "Title": "Daniel Ortega", "UserName": "", "Password": "", "URL": "", "Notes": "", "NARSIL.Tipo": "identidad",
        "Ficha.nombre": "Daniel", "Ficha.apellidos": "Ortega", "Ficha.estado": "retirada", "Ficha.creada_el": "2024-02-01",
    }))

    # Sin sección, y papelera
    b.crear_entrada(None, c(Title="Entrada sin clasificar", UserName="usuario", Password="Sc5!tZ1#yH8@-suelta",
                            Notes="Está en la raíz, fuera de las secciones: solo se ve en «Toda la base»."))
    vieja = b.crear_entrada(s["externo"], c(Title="Cuenta antigua de pruebas", UserName="prueba", Password="Old1!pass-2024"))
    b.eliminar_entrada(vieja)
    b.fijar_renovar_dias(180)
    return s


def generar(destino: Path) -> None:
    destino.mkdir(parents=True, exist_ok=True)
    k4 = destino / "NARSIL-ejemplo-KDBX4.kdbx"
    k31 = destino / "NARSIL-ejemplo-KDBX31.kdbx"
    for r in (k4, k31):
        r.unlink(missing_ok=True)

    b = Boveda(base=Base.nueva("NARSIL · base de ejemplo", CLAVE, parametros_kdf=kdf.argon2id_por_defecto(iteraciones=kdf.calibrar_iteraciones(1.0))),
               ruta=str(k4))
    b._papelera("Papelera")
    rellenar(b)
    b.guardar(forzar=True)

    cli = shutil.which("keepassxc-cli")
    if not cli:
        raise SystemExit("hace falta keepassxc-cli para crear la variante 3.1")
    subprocess.run([cli, "db-create", "-q", "-p", "-t", "1000", str(k31)], input=f"{CLAVE}\n{CLAVE}\n", text=True, check=True)
    b31 = Boveda.abrir(str(k31), CLAVE)
    b31.ajustar_base("NARSIL · base de ejemplo (KDBX 3.1)")
    b31._papelera("Papelera")
    rellenar(b31)
    b31.guardar()
    (destino / "LEEME.md").write_text(LEEME, encoding="utf-8")
    print(k4, k31, sep="\n")


if __name__ == "__main__":
    generar(Path(sys.argv[1]) if len(sys.argv) > 1 else RAIZ / "ejemplos")
