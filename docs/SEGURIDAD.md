# Seguridad de NARSIL Pass

Qué protege NARSIL Pass, cómo lo hace y qué queda fuera de su alcance. Está escrito para quien tenga
que evaluar la herramienta antes de confiarle secretos reales.

## Modelo

- La base es **un fichero `.kdbx` que controla el usuario**. No hay cuenta, servidor, sincronización
  ni copia en la nube: si el fichero no sale del equipo, los secretos tampoco.
- La confidencialidad descansa en el **formato KeePass** (KDBX 3.1 y 4) y en la **clave maestra**
  (contraseña, fichero de clave o ambos). NARSIL Pass implementa ese formato sobre primitivas de
  bibliotecas auditadas; no define cifrado propio.

## Criptografía y formato

| Pieza | Implementación |
|---|---|
| Cifrado de la base | AES-256-CBC o ChaCha20 (`cryptography`) |
| Derivación de la clave | Argon2d / Argon2id (`argon2-cffi`) o AES-KDF (KDBX 3.1) |
| Integridad KDBX 4 | SHA-256 de la cabecera, HMAC-SHA-256 de la cabecera y de cada bloque, comprobados **antes** de descifrar, con comparación en tiempo constante |
| Integridad KDBX 3.1 | Bytes de inicio cifrados y bloques con SHA-256 |
| Valores protegidos en el fichero | ChaCha20 (KDBX 4) o Salsa20 (KDBX 3.1) como flujo interior |
| Aleatoriedad | `os.urandom`: semilla maestra, IV y clave del flujo interior nuevos en cada guardado; sal de la derivación nueva al cambiar la clave |
| XML interior | `lxml` sin entidades, sin DTD (se rechaza), sin red |

Las bases nuevas se crean en KDBX 4 con ChaCha20 y Argon2id (64 MiB, iteraciones calibradas a un
segundo de desbloqueo en el equipo). El tiempo de desbloqueo se ajusta en *Ajustes → Base de datos*.

La compatibilidad se prueba en cada cambio contra **KeePassXC** como oráculo: bases escritas por
NARSIL Pass que KeePassXC abre sin perder un campo, y bases de KeePassXC (con historial, adjuntos,
AutoType y datos de complementos) que pasan por NARSIL Pass y quedan idénticas salvo lo editado, en
KDBX 4 y en 3.1.

## Sin red

- La interfaz se carga desde el propio ejecutable (`file://`); pywebview **no abre ningún puerto**.
- La política de contenido de la ventana es `default-src 'none'`, `connect-src 'none'` e imágenes
  y tipografías solo embebidas (`data:`): la interfaz no puede cargar ni enviar nada a ninguna
  dirección aunque tuviera un fallo. Incluye `'unsafe-eval'` porque el puente de pywebview entre la
  interfaz y Python lo necesita (crea sus funciones con `new Function` y devuelve cada respuesta con
  `eval`); no abre ninguna vía de red y una prueba lo vigila.
- La prueba de la ventana real comprueba que el proceso no tiene sockets de red abiertos.
- No hay actualizador automático, telemetría ni comprobación de contraseñas filtradas en línea.

## Guardado

1. La base se serializa a un **fichero temporal** en la misma carpeta, creado en exclusiva
   (`O_EXCL`) y sin seguir enlaces simbólicos.
2. Se **vuelve a abrir y a descifrar** y se compara con lo que había en memoria.
3. Solo entonces se vuelca a disco y **sustituye** al original de forma atómica. Si algo falla, el
   original no se toca.
4. Con la copia previa activada, la versión anterior queda en `<base>.kdbx.bak` (cifrada con la
   clave que tuviera en ese momento).

En Linux, las bases nuevas y los ficheros de clave se crean con permisos `0600`, y una base
existente conserva los suyos. Si otro programa ha modificado la base desde que se abrió, NARSIL Pass
no la sobrescribe sin preguntar.

## En uso

- Los listados y el detalle **nunca llevan contraseñas** a la interfaz: cada valor protegido se pide
  uno a uno al revelarlo o copiarlo.
- **Portapapeles:** lo copiado se borra a los N segundos (12 por defecto) si no ha cambiado entretanto.
  En Windows se marca para que no entre en el historial del portapapeles (Win+V) ni en el
  portapapeles en la nube.
- **Bloqueo** manual y por inactividad: descarta la base descifrada y vacía el portapapeles. Si hay
  cambios que no se pueden guardar, avisa y no finge el bloqueo.
- El **registro técnico** no contiene valores de la base, contraseñas ni rutas de ficheros de clave.
  Las preferencias guardan idioma, tiempos y rutas de bases recientes (desactivable), nunca secretos.

## Ficheros hostiles

Una base recibida de terceros se trata como no fiable: cabeceras, longitudes y parámetros
malformados se rechazan como «base dañada»; un XML con DTD se rechaza; un código TOTP con
parámetros absurdos se ignora en lugar de bloquear la aplicación.

**Límite conocido:** los parámetros de la derivación de clave van en la cabecera y solo se pueden
autenticar después de derivar. Un fichero manipulado con parámetros desorbitados (memoria o
iteraciones) puede dejar la aplicación ocupada al pulsar Desbloquear. KeePassXC tiene el mismo
comportamiento. No abra bases de origen desconocido fuera de un entorno de pruebas.

## Lo que NARSIL Pass no puede proteger

- **Un equipo comprometido.** Un programa malicioso con acceso a su sesión puede leer la memoria, el
  teclado o la pantalla. Ningún gestor de contraseñas lo evita.
- **La memoria mientras la base está abierta.** Python no permite borrar con garantías las cadenas
  de la memoria; bloquee la base cuando no la use.
- **Una clave maestra débil.** La derivación hace caro cada intento, no imposible. Use una frase de
  paso larga (el generador de NARSIL Pass las crea) o combine contraseña y fichero de clave.
- **El ejecutable no está firmado.** Compruebe la suma SHA-256 de la descarga con `SHA256SUMS`.

## Revisiones

El código ha pasado una revisión de calidad y una auditoría de seguridad internas antes de su
primera entrega. Los hallazgos (todos de severidad media o baja) están corregidos y cada uno tiene
su prueba en `tests/test_seguridad.py`.
