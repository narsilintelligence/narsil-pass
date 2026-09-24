# Base de ejemplo de NARSIL Pass

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
