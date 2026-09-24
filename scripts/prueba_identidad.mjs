// Prueba del modelo de identidad (ui/src/ficha.ts): leer y escribir no pierde ni inventa campos.
//   node scripts/prueba_identidad.mjs      (lo compila con el esbuild que trae Vite)
import { build } from '../ui/node_modules/esbuild/lib/main.js'
import { mkdtempSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import path from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'
import assertEstricto from 'node:assert/strict'

let comprobaciones = 0   // se cuentan solas: el mensaje final nunca miente sobre cuántas hay
const assert = new Proxy(assertEstricto, {
  get: (t, p) => (typeof t[p] === 'function' ? (...a) => { comprobaciones += 1; return t[p](...a) } : t[p]),
})

const raiz = path.dirname(path.dirname(fileURLToPath(import.meta.url)))
const salida = path.join(mkdtempSync(path.join(tmpdir(), 'identidad-')), 'identidad.mjs')
await build({ entryPoints: [path.join(raiz, 'ui/src/ficha.ts')], bundle: true, format: 'esm', outfile: salida, logLevel: 'error' })
const m = await import(pathToFileURL(salida).href)

const c = (clave, valor, protegido = false) => ({ clave, valor, protegido })
const origen = [
  c('Title', 'Marta'), c('UserName', 'marta@x'), c('Password', ' clave con espacios ', true), c('URL', ''), c('Notes', 'n'),
  c('NARSIL.Tipo', 'identidad'), c('Ficha.nombre', 'Marta'), c('Ficha.biografia', 'Línea 1\nLínea 2'),
  c('Ficha.campo_futuro', 'de otra versión'),                         // desconocido: se conserva
  c('Servicio.3.nombre', 'Instagram'), c('Servicio.3.contrasena', ' s3 ', true), c('Servicio.3.campo_raro', 'x'),
  c('Servicio.7.usuario', 'solo-usuario'), c('otp', 'otpauth://totp/x?secret=ABC', true), c('Propio', 'valor'),
]
const id = m.leerIdentidad(origen)
assert.equal(id.ficha.nombre, 'Marta')
assert.equal(id.biografia, 'Línea 1\nLínea 2')
assert.deepEqual(id.numeros, [3, 7])
assert.deepEqual(id.otros.map((x) => x.clave), ['Ficha.campo_futuro', 'Servicio.3.campo_raro', 'otp', 'Propio'])

const campos = m.escribirIdentidad(id)
const mapa = Object.fromEntries(campos.map((x) => [x.clave, x]))
assert.equal(mapa['NARSIL.Tipo'].valor, 'identidad')
assert.equal(mapa['Password'].valor, ' clave con espacios ', 'la contraseña no se recorta')
assert.equal(mapa['Password'].protegido, true)
assert.equal(mapa['Servicio.1.nombre'].valor, 'Instagram', 'los servicios se renumeran desde 1')
assert.equal(mapa['Servicio.1.contrasena'].valor, ' s3 ')
assert.equal(mapa['Servicio.1.contrasena'].protegido, true)
assert.equal(mapa['Servicio.2.usuario'].valor, 'solo-usuario')
assert.equal(mapa['Ficha.campo_futuro'].valor, 'de otra versión', 'un Ficha.* desconocido no se pierde')
assert.equal(mapa['Servicio.1.campo_raro'].valor, 'x', 'el campo desconocido de un servicio se renumera con él')
assert.ok(!('Servicio.3.campo_raro' in mapa))
assert.equal(mapa['Propio'].valor, 'valor')
assert.equal(mapa['otp'].protegido, true)
assert.equal(new Set(campos.map((x) => x.clave)).size, campos.length, 'sin claves duplicadas')
assert.ok(!('Ficha.apellidos' in mapa), 'los campos vacíos no se escriben')

// Ida y vuelta estable: leer lo escrito y volver a escribir da lo mismo.
assert.deepEqual(m.escribirIdentidad(m.leerIdentidad(campos)), campos)
// Un servicio vacío no deja rastro; quitar un servicio se lleva sus campos desconocidos; los que no
// pertenecen a ningún servicio de la ficha se quedan como están.
assert.deepEqual(m.escribirIdentidad({ ...id, servicios: [...id.servicios, m.servicioVacio()], numeros: [...id.numeros, 0] }), campos)
const sinInstagram = m.escribirIdentidad({ ...id, servicios: id.servicios.slice(1), numeros: id.numeros.slice(1) })
assert.ok(!sinInstagram.some((x) => x.clave.endsWith('campo_raro')), 'quitar el servicio se lleva su campo desconocido')
assert.equal(sinInstagram.find((x) => x.clave === 'Servicio.1.usuario').valor, 'solo-usuario')
const huerfano = m.leerIdentidad([...origen, c('Servicio.9.suelto', 'y')])
assert.ok(m.escribirIdentidad(huerfano).some((x) => x.clave === 'Servicio.9.suelto'), 'un Servicio.* sin servicio en la ficha se conserva')
assert.equal(m.claveReservada('Ficha.nombre'), true)
assert.equal(m.claveReservada('Servicio.4.contrasena'), true)
assert.equal(m.claveReservada('Ficha.campo_futuro'), false)
assert.equal(m.claveReservada('Servicio.3.campo_raro'), false)
assert.equal(m.edad('2000-01-01') >= 26, true)
assert.equal(m.normalizarOtp([c('otp', 'jbsw y3dp', false)])[0].valor, 'otpauth://totp/NARSIL?secret=JBSWY3DP&period=30&digits=6')
writeFileSync(salida, '')
console.log(`ficha.ts: lectura y escritura sin pérdidas (${comprobaciones} comprobaciones)`)
