// Dónde vive cada entrada (sección y carpeta) y agrupación de listados por sección. Lógica pura, sin
// interfaz, para probarla aparte (scripts/prueba_listado.mjs).
import type { Grupo, Info, Resumen, Seccion } from './api'

export type Bloque = Seccion | 'sin_seccion'
export const ORDEN_BLOQUES: Bloque[] = ['interno', 'externo', 'identidades', 'sin_seccion']

export interface Ubicacion { seccion: Bloque; nombre: string; raizSeccion: boolean; papelera: boolean }

/** Para cada grupo: la sección a la que pertenece (la del antepasado más cercano que sea sección), su
 *  nombre y si es la raíz de una sección. La raíz de la base y lo que cuelga fuera de las secciones
 *  quedan «sin sección»; la papelera y su contenido se marcan como tales. */
export function mapaUbicacion(arbol: Grupo | null, secciones: Info['secciones']): Map<string, Ubicacion> {
  const mapa = new Map<string, Ubicacion>()
  const porUuid = new Map<string, Seccion>()
  for (const s of ['interno', 'externo', 'identidades'] as Seccion[]) {
    const u = secciones?.[s]
    if (u) porUuid.set(u, s)
  }
  const recorrer = (n: Grupo, seccion: Bloque, papelera: boolean) => {
    const propia = porUuid.get(n.uuid)
    const actual = propia ?? seccion
    const enPapelera = papelera || n.papelera
    mapa.set(n.uuid, { seccion: actual, nombre: n.nombre, raizSeccion: !!propia, papelera: enPapelera })
    for (const h of n.hijos) recorrer(h, actual, enPapelera)
  }
  if (arbol) recorrer(arbol, 'sin_seccion', false)
  return mapa
}

export interface GrupoLista { id: Bloque; filas: Resumen[] }

/** Agrupa por sección en el orden fijo de ORDEN_BLOQUES, conservando el orden original dentro de cada
 *  bloque. Una entrada cuyo grupo no se conoce (árbol aún sin cargar) va a «sin sección». */
export function agruparPorSeccion(lista: Resumen[], mapa: Map<string, Ubicacion>): GrupoLista[] {
  const por = new Map<Bloque, Resumen[]>()
  for (const e of lista) {
    const b = mapa.get(e.grupo)?.seccion ?? 'sin_seccion'
    if (!por.has(b)) por.set(b, [])
    por.get(b)!.push(e)
  }
  return ORDEN_BLOQUES.filter((b) => por.has(b)).map((b) => ({ id: b, filas: por.get(b)! }))
}

/** Carpeta que merece la pena mostrar junto a una entrada: ni la raíz de la base ni la raíz de su sección. */
export function carpetaVisible(e: Resumen, mapa: Map<string, Ubicacion>, raiz: string): string {
  const u = mapa.get(e.grupo)
  return u && e.grupo !== raiz && !u.raizSeccion ? u.nombre : ''
}
