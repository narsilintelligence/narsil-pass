// Cliente del puente con Python (window.pywebview.api). Sin red: la única vía es la ventana.
// En la compilación de demostración (`--mode demo`) se usa un doble en memoria para las capturas
// y las pruebas de interfaz; ese código no entra en el ejecutable.
import type { Idioma } from './i18n'

export type Respuesta<T = Record<string, unknown>> = ({ ok: true } & T) | { ok: false; error: string }

export interface Info {
  nombre: string; descripcion: string; formato: string; es_v3: boolean; cifrado: string; kdf: string
  kdf_iteraciones: number | null; kdf_memoria_mib: number | null; ruta: string | null; cambios: boolean
  papelera: string | null; raiz: string; entradas: number
  secciones: Record<Seccion, string | null>; renovar_dias: number
}
export type Seccion = 'interno' | 'externo' | 'identidades'
export type Alerta = 'repetida' | 'debil' | 'renovar' | 'caducada' | 'por_caducar'

export interface Preferencias {
  recordar_recientes: boolean; bloqueo_minutos: number; portapapeles_segundos: number
  autoguardado: boolean; copia_previa: boolean
}
export interface Estado {
  version: string; idioma: Idioma; recientes: string[]; inicial: string | null; abierta: boolean
  info: Info | null; preferencias: Preferencias; portapapeles_nativo: boolean
}
export interface Grupo { uuid: string; nombre: string; entradas: number; papelera: boolean; hijos: Grupo[] }
export interface Resumen {
  uuid: string; titulo: string; usuario: string; url: string; grupo: string; etiquetas: string[]
  modificada: string | null; expira: string | null; caducada: boolean; totp: boolean; adjuntos: number
  tipo: 'identidad' | 'entrada'; estado: string; servicios: number; fotos: number; alertas: Alerta[]
}
export interface RefSalud { uuid: string; titulo: string; grupo: string; campo?: string; servicio?: string; bits?: number; fecha?: string; dias?: number }
export interface Salud {
  repetidas: RefSalud[][]; debiles: RefSalud[]; renovar: RefSalud[]; caducadas: RefSalud[]; por_caducar: RefSalud[]
  renovar_dias: number; total: number
}
export interface Filtros { ambito?: string | null; servicio?: string; usuario?: string; tipo?: string; estado?: string; alerta?: string }
export interface Campo { clave: string; valor: string | null; protegido: boolean; vacio?: boolean }
export interface Detalle extends Resumen {
  campos: Campo[]; fechas: Record<string, string | null>
  historial: { indice: number; titulo: string; modificada: string | null }[]
  adjuntos_lista: { nombre: string; tamano: number }[]; en_papelera: boolean
}
export interface Totp { codigo: string; restante: number; periodo: number }

type Puente = Record<string, (...args: unknown[]) => Promise<unknown>>

declare global {
  interface Window { pywebview?: { api: Puente } }
}

let puenteDemo: Puente | null = null

async function puente(): Promise<Puente> {
  if (import.meta.env.MODE === 'demo') {
    if (!puenteDemo) puenteDemo = (await import('./demo')).crearDemo()
    return puenteDemo
  }
  // pywebview crea primero `window.pywebview.api` vacío y lo rellena después: no basta con que exista
  // el objeto (con muchos métodos, la primera llamada llegaría antes y la ventana quedaría en blanco).
  // Se espera a que esté la función y, por si el evento ya pasó, se sondea.
  const listo = () => typeof window.pywebview?.api?.estado === 'function'
  if (!listo()) {
    await new Promise<void>((resolver) => {
      const comprobar = () => { if (listo()) { window.removeEventListener('pywebviewready', comprobar); window.clearInterval(reloj); resolver() } }
      const reloj = window.setInterval(comprobar, 25)
      window.addEventListener('pywebviewready', comprobar)
    })
  }
  return window.pywebview!.api
}

export async function llamar<T = Record<string, unknown>>(metodo: string, ...args: unknown[]): Promise<Respuesta<T>> {
  const p = await puente()
  if (typeof p[metodo] !== 'function') return { ok: false, error: 'interno' }
  try {
    return (await p[metodo](...args)) as Respuesta<T>
  } catch {
    return { ok: false, error: 'interno' }
  }
}

/** Copia sin portapapeles nativo (respaldo): el propio documento. */
export function copiarEnNavegador(texto: string): boolean {
  const area = document.createElement('textarea')
  area.value = texto
  area.setAttribute('readonly', '')
  area.style.position = 'fixed'
  area.style.opacity = '0'
  document.body.appendChild(area)
  area.select()
  let ok = false
  try { ok = document.execCommand('copy') } catch { ok = false }
  document.body.removeChild(area)
  return ok
}
