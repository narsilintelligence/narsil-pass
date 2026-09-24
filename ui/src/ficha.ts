// Modelo de la identidad operativa. Todo se guarda como campos KeePass normales de la entrada, así
// que KeePassXC la abre y la muestra completa:
//   NARSIL.Tipo = identidad            marca de tipo (oculta en la interfaz)
//   Ficha.<campo>                      datos del avatar, todos opcionales; solo se guardan los rellenos
//   Servicio.<n>.<campo>               cada servicio en el que está registrada; contraseña protegida
// Las fotos son adjuntos de imagen de la propia entrada.
import type { Campo } from './api'
import type { Clave } from './i18n'

export const CAMPO_TIPO = 'NARSIL.Tipo'
export const ESTANDAR = ['Title', 'UserName', 'Password', 'URL', 'Notes']
export const OCULTOS = ['otp', 'TOTP Seed', 'TOTP Settings', CAMPO_TIPO]

export type Control = 'texto' | 'largo' | 'fecha' | 'estado'
export interface CampoFicha { id: string; control: Control }
export interface SeccionFicha { id: string; campos: CampoFicha[] }

const tx = (id: string, control: Control = 'texto'): CampoFicha => ({ id, control })

export const FICHA: SeccionFicha[] = [
  { id: 'personal', campos: [tx('nombre'), tx('apellidos'), tx('alias'), tx('genero'), tx('fecha_nacimiento', 'fecha'), tx('edad'),
    tx('lugar_nacimiento'), tx('nacionalidad'), tx('origen'), tx('idiomas')] },
  { id: 'residencia', campos: [tx('pais_residencia'), tx('ciudad_residencia'), tx('direccion'), tx('codigo_postal'), tx('telefono'),
    tx('correo'), tx('correo_recuperacion')] },
  { id: 'formacion', campos: [tx('estudios'), tx('centro_estudios'), tx('profesion'), tx('lugar_trabajo'), tx('cargo'),
    tx('trayectoria', 'largo')] },
  { id: 'fisico', campos: [tx('estatura'), tx('complexion'), tx('ojos'), tx('pelo'), tx('rasgos', 'largo')] },
  { id: 'vida', campos: [tx('estado_civil'), tx('familia', 'largo'), tx('intereses', 'largo'), tx('cultura', 'largo'), tx('deportes'),
    tx('mascotas'), tx('vehiculo')] },
  { id: 'digital', campos: [tx('dispositivo'), tx('sistema'), tx('navegador'), tx('huso_horario'), tx('ubicacion_conexion'), tx('sim'),
    tx('red_contactos', 'largo')] },
  { id: 'cobertura', campos: [tx('estado', 'estado'), tx('operacion'), tx('responsable'), tx('creada_el', 'fecha'),
    tx('cobertura', 'largo'), tx('pautas', 'largo')] },
]
export const ESTADOS = ['activa', 'reposo', 'comprometida', 'retirada'] as const
export const CAMPOS_SERVICIO = ['nombre', 'url', 'id', 'usuario', 'alias', 'correo', 'telefono', 'contrasena', 'notas'] as const
export type CampoServicio = typeof CAMPOS_SERVICIO[number]
export type Servicio = Record<CampoServicio, string>

export const servicioVacio = (): Servicio => Object.fromEntries(CAMPOS_SERVICIO.map((c) => [c, ''])) as Servicio
export const rotuloFicha = (id: string) => `ficha.${id}` as Clave
export const rotuloSeccion = (id: string) => `ficha.s.${id}` as Clave

export interface Identidad {
  estandar: Record<string, string>
  ficha: Record<string, string>
  biografia: string
  servicios: Servicio[]
  numeros: number[]   // número real de cada servicio en la base (Servicio.<n>.*), para revelar y copiar; 0 si es nuevo
  leidos: number[]    // números de servicio que había al leer la entrada (no cambia al editar)
  otros: Campo[]   // campos que no son de la ficha: se conservan tal cual (otp, campos antiguos, de otras apps)
}

const RE_SERVICIO = /^Servicio\.(\d+)\.(\w+)$/
const IDS_FICHA = new Set(FICHA.flatMap((s) => s.campos.map((c) => c.id)))

/** De la lista de campos de la entrada al modelo; con `para_editar` los protegidos llegan en claro. */
export function leerIdentidad(campos: Campo[]): Identidad {
  const id: Identidad = { estandar: {}, ficha: {}, biografia: '', servicios: [], numeros: [], leidos: [], otros: [] }
  const porNumero = new Map<number, Servicio>()
  for (const c of campos) {
    const v = c.valor ?? ''
    if (ESTANDAR.includes(c.clave)) id.estandar[c.clave] = v
    else if (c.clave === CAMPO_TIPO) continue
    else if (c.clave === 'Ficha.biografia') id.biografia = v
    else if (c.clave.startsWith('Ficha.') && IDS_FICHA.has(c.clave.slice(6))) id.ficha[c.clave.slice(6)] = v
    else {
      const m = RE_SERVICIO.exec(c.clave)
      if (m && (CAMPOS_SERVICIO as readonly string[]).includes(m[2])) {
        const n = Number(m[1])
        if (!porNumero.has(n)) porNumero.set(n, servicioVacio())
        porNumero.get(n)![m[2] as CampoServicio] = v
      } else id.otros.push(c)
    }
  }
  const orden = [...porNumero.entries()].sort((a, b) => a[0] - b[0])
  id.servicios = orden.map(([, s]) => s)
  id.numeros = orden.map(([n]) => n)
  id.leidos = [...id.numeros]
  return id
}

/** Del modelo a campos KeePass. Solo se escriben los valores rellenos; los servicios se renumeran. */
export function escribirIdentidad(id: Identidad): Campo[] {
  const salida: Campo[] = ESTANDAR.map((c) => ({ clave: c, valor: id.estandar[c] ?? '', protegido: c === 'Password' }))
  salida.push({ clave: CAMPO_TIPO, valor: 'identidad', protegido: false })
  for (const s of FICHA) for (const c of s.campos) {
    const v = (id.ficha[c.id] ?? '').trim()
    if (v) salida.push({ clave: `Ficha.${c.id}`, valor: v, protegido: false })
  }
  if (id.biografia.trim()) salida.push({ clave: 'Ficha.biografia', valor: id.biografia, protegido: false })
  // Los servicios se renumeran desde 1. Un campo Servicio.<n>.<x> que la ficha no conoce acompaña a su
  // servicio (se renumera con él) y desaparece si el servicio se quita; si no pertenece a ningún servicio
  // de la ficha, se deja como está.
  let n = 0
  const renumero = new Map<number, number>()
  const conocidos = new Set(id.leidos)
  id.servicios.forEach((s, i) => {
    if (!CAMPOS_SERVICIO.some((c) => s[c].trim())) return
    n += 1
    if (id.numeros[i] > 0) renumero.set(id.numeros[i], n)
    for (const c of CAMPOS_SERVICIO) {
      if (s[c].trim()) salida.push({ clave: `Servicio.${n}.${c}`, valor: c === 'contrasena' ? s[c] : s[c].trim(), protegido: c === 'contrasena' })
    }
  })
  const otros: Campo[] = []
  for (const c of id.otros) {
    if (!c.clave.trim()) continue
    const m = RE_SERVICIO.exec(c.clave)
    if (m && conocidos.has(Number(m[1]))) {
      const nuevo = renumero.get(Number(m[1]))
      if (nuevo !== undefined) otros.push({ ...c, clave: `Servicio.${nuevo}.${m[2]}` })
    } else otros.push(c)
  }
  return [...salida, ...otros]
}

/** Clave KeePass del campo de un servicio ya guardado (para revelar o copiar). */
export const claveServicio = (numero: number, campo: CampoServicio) => `Servicio.${numero}.${campo}`

export function edad(fechaIso: string): number | null {
  const d = new Date(fechaIso)
  if (Number.isNaN(d.getTime())) return null
  const hoy = new Date()
  let e = hoy.getFullYear() - d.getFullYear()
  if (hoy.getMonth() < d.getMonth() || (hoy.getMonth() === d.getMonth() && hoy.getDate() < d.getDate())) e -= 1
  return e >= 0 && e < 130 ? e : null
}

export const esImagen = (nombre: string) => /\.(jpe?g|png|webp|gif|bmp)$/i.test(nombre)

/** Un secreto TOTP escrito a mano (base32) se guarda como otpauth://, que es lo que lee KeePassXC. */
export const normalizarOtp = (campos: Campo[]): Campo[] => campos.map((c) => (c.clave === 'otp' && c.valor && !c.valor.startsWith('otpauth://')
  ? { ...c, valor: `otpauth://totp/NARSIL?secret=${c.valor.replace(/\s+/g, '').toUpperCase()}&period=30&digits=6`, protegido: true } : c))

/** Nombres que el usuario no puede dar a un campo propio porque los escribe la ficha. Los Ficha.* o
 *  Servicio.* que la ficha no conoce (de otra herramienta o versión) se conservan como campos propios. */
export const claveReservada = (clave: string) => {
  if (ESTANDAR.includes(clave) || clave === CAMPO_TIPO || clave === 'Ficha.biografia') return true
  if (clave.startsWith('Ficha.') && IDS_FICHA.has(clave.slice(6))) return true
  const m = RE_SERVICIO.exec(clave)
  return !!m && (CAMPOS_SERVICIO as readonly string[]).includes(m[2])
}
