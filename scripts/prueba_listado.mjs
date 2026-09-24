// Prueba de ui/src/listado.ts: cada entrada cae en su sección y los bloques salen en orden fijo.
//   node scripts/prueba_listado.mjs
import { build } from '../ui/node_modules/esbuild/lib/main.js'
import { mkdtempSync } from 'node:fs'
import { tmpdir } from 'node:os'
import path from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'
import assertEstricto from 'node:assert/strict'

let comprobaciones = 0   // se cuentan solas: el mensaje final nunca miente sobre cuántas hay
const assert = new Proxy(assertEstricto, {
  get: (t, p) => (typeof t[p] === 'function' ? (...a) => { comprobaciones += 1; return t[p](...a) } : t[p]),
})

const raiz = path.dirname(path.dirname(fileURLToPath(import.meta.url)))
const salida = path.join(mkdtempSync(path.join(tmpdir(), 'listado-')), 'listado.mjs')
await build({ entryPoints: [path.join(raiz, 'ui/src/listado.ts')], bundle: true, format: 'esm', outfile: salida, logLevel: 'error' })
const m = await import(pathToFileURL(salida).href)

const g = (uuid, nombre, hijos = [], papelera = false) => ({ uuid, nombre, entradas: 0, papelera, hijos })
const arbol = g('raiz', 'Base', [
  g('int', 'Servicios internos', [g('infra', 'Infraestructura', [g('hondo', 'Muy dentro')])]),
  g('ext', 'Servicios externos', [g('fuentes', 'Fuentes abiertas')]),
  g('id', 'Identidades operativas', [g('norte', 'Operación Norte')]),
  g('suelto', 'Grupo sin sección'),
  g('pap', 'Papelera', [g('borrado', 'Grupo borrado')], true)])
const secciones = { interno: 'int', externo: 'ext', identidades: 'id' }
const mapa = m.mapaUbicacion(arbol, secciones)
assert.equal(mapa.get('hondo').seccion, 'interno', 'un subgrupo profundo hereda la sección')
assert.equal(mapa.get('norte').seccion, 'identidades')
assert.equal(mapa.get('raiz').seccion, 'sin_seccion')
assert.equal(mapa.get('suelto').seccion, 'sin_seccion')
assert.equal(mapa.get('int').raizSeccion, true)
assert.equal(mapa.get('borrado').papelera, true, 'lo que cuelga de la papelera se marca')

const e = (uuid, grupo) => ({ uuid, grupo, titulo: uuid })
const lista = [e('a', 'norte'), e('b', 'raiz'), e('c', 'infra'), e('d', 'fuentes'), e('f', 'int'), e('x', 'desconocido'), e('h', 'hondo')]
const bloques = m.agruparPorSeccion(lista, mapa)
assert.deepEqual(bloques.map((b) => b.id), ['interno', 'externo', 'identidades', 'sin_seccion'], 'orden fijo de bloques')
assert.deepEqual(bloques[0].filas.map((x) => x.uuid), ['c', 'f', 'h'], 'dentro del bloque se conserva el orden')
assert.deepEqual(bloques[3].filas.map((x) => x.uuid), ['b', 'x'], 'raíz y grupo desconocido van a «sin sección»')
assert.equal(bloques.flatMap((b) => b.filas).length, lista.length, 'no se pierde ni se duplica ninguna entrada')
assert.deepEqual(m.agruparPorSeccion([e('d', 'fuentes')], mapa).map((b) => b.id), ['externo'], 'sin bloques vacíos')
assert.deepEqual(m.agruparPorSeccion([], mapa), [])

assert.equal(m.carpetaVisible(e('c', 'infra'), mapa, 'raiz'), 'Infraestructura')
assert.equal(m.carpetaVisible(e('f', 'int'), mapa, 'raiz'), '', 'la raíz de la sección no se repite')
assert.equal(m.carpetaVisible(e('b', 'raiz'), mapa, 'raiz'), '', 'la raíz de la base tampoco')
assert.equal(m.carpetaVisible(e('s', 'suelto'), mapa, 'raiz'), 'Grupo sin sección')

// Base sin secciones: todo a «sin sección», con su carpeta.
const sin = m.mapaUbicacion(arbol, { interno: null, externo: null, identidades: null })
assert.deepEqual(m.agruparPorSeccion(lista, sin).map((b) => b.id), ['sin_seccion'])
assert.equal(m.carpetaVisible(e('f', 'int'), sin, 'raiz'), 'Servicios internos')
// Árbol aún sin cargar: no revienta.
assert.deepEqual(m.agruparPorSeccion(lista, m.mapaUbicacion(null, secciones)).map((b) => b.id), ['sin_seccion'])
console.log(`listado.ts: ubicación y agrupación por sección correctas (${comprobaciones} comprobaciones)`)
