import { es, type Clave } from './es'
import { en } from './en'
import { fr } from './fr'
import { de } from './de'
import { it } from './it'
import { pt } from './pt'

export type { Clave }
export type Idioma = 'es' | 'en' | 'fr' | 'de' | 'it' | 'pt'

export const IDIOMAS: { id: Idioma; nativo: string }[] = [
  { id: 'es', nativo: 'Español' }, { id: 'en', nativo: 'English' }, { id: 'fr', nativo: 'Français' },
  { id: 'de', nativo: 'Deutsch' }, { id: 'it', nativo: 'Italiano' }, { id: 'pt', nativo: 'Português' },
]

export const LOCALES: Record<Idioma, string> = { es: 'es-ES', en: 'en-GB', fr: 'fr-FR', de: 'de-DE', it: 'it-IT', pt: 'pt-PT' }

const TABLAS: Record<Idioma, Record<Clave, string>> = { es, en, fr, de, it, pt }

export function traductor(idioma: Idioma) {
  const tabla = TABLAS[idioma] ?? es
  return (clave: Clave, vars?: Record<string, string | number>): string => {
    let texto = tabla[clave] ?? es[clave] ?? clave
    if (vars) for (const [k, v] of Object.entries(vars)) texto = texto.split(`{${k}}`).join(String(v))
    return texto
  }
}

export function fecha(iso: string | null | undefined, idioma: Idioma, conHora = false): string {
  if (!iso) return '—'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return '—'
  return d.toLocaleString(LOCALES[idioma], conHora
    ? { day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' }
    : { day: '2-digit', month: 'short', year: 'numeric' })
}

export function tamano(bytes: number, idioma: Idioma): string {
  const f = new Intl.NumberFormat(LOCALES[idioma], { maximumFractionDigits: 1 })
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${f.format(bytes / 1024)} KB`
  return `${f.format(bytes / 1024 / 1024)} MB`
}
