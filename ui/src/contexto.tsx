import { createContext, useCallback, useContext, useMemo, useRef, useState, type ReactNode } from 'react'
import { traductor, type Clave, type Idioma } from './i18n'
import { copiarEnNavegador, llamar } from './api'

interface Aviso { texto: string; error?: boolean }
interface Ctx {
  idioma: Idioma
  setIdioma: (i: Idioma) => void
  t: (c: Clave, v?: Record<string, string | number>) => string
  avisar: (texto: string, error?: boolean) => void
  error: (codigo: string) => void
  copiar: (uuid: string, clave: string) => Promise<void>
  copiarTexto: (texto: string) => Promise<void>
}

const Contexto = createContext<Ctx | null>(null)

export function useApp(): Ctx {
  const c = useContext(Contexto)
  if (!c) throw new Error('useApp fuera del proveedor')
  return c
}

export function Proveedor({ idiomaInicial, children }: { idiomaInicial: Idioma; children: ReactNode }) {
  const [idioma, setIdiomaEstado] = useState<Idioma>(idiomaInicial)
  const [aviso, setAviso] = useState<Aviso | null>(null)
  const temporizador = useRef<number | undefined>(undefined)
  const t = useMemo(() => traductor(idioma), [idioma])

  const avisar = useCallback((texto: string, error = false) => {
    setAviso({ texto, error })
    window.clearTimeout(temporizador.current)
    temporizador.current = window.setTimeout(() => setAviso(null), error ? 5000 : 2600)
  }, [])

  const error = useCallback((codigo: string) => avisar(t(`error.${codigo}` as Clave) || t('error.interno'), true), [avisar, t])

  const trasCopiar = useCallback((r: { ok: boolean; nativo?: boolean; texto?: string; segundos?: number; error?: string }) => {
    if (!r.ok) { error(r.error ?? 'interno'); return }
    if (r.nativo === false && r.texto !== undefined) {
      copiarEnNavegador(r.texto)
      avisar(t('comun.copiado_sin_borrado'))
      return
    }
    avisar(t('comun.copiado', { s: r.segundos ?? 12 }))
  }, [avisar, error, t])

  const copiar = useCallback(async (uuid: string, clave: string) => {
    trasCopiar(await llamar('copiar', uuid, clave) as never)
  }, [trasCopiar])

  const copiarTexto = useCallback(async (texto: string) => {
    trasCopiar(await llamar('copiar_texto', texto) as never)
  }, [trasCopiar])

  const setIdioma = useCallback((i: Idioma) => {
    setIdiomaEstado(i)
    document.documentElement.lang = i
    void llamar('guardar_preferencias', { idioma: i })
  }, [])

  const valor = useMemo(() => ({ idioma, setIdioma, t, avisar, error, copiar, copiarTexto }),
    [idioma, setIdioma, t, avisar, error, copiar, copiarTexto])

  return (
    <Contexto.Provider value={valor}>
      {children}
      {aviso && <div className={`aviso-flotante${aviso.error ? ' aviso-flotante--error' : ''}`} role="status">{aviso.texto}</div>}
    </Contexto.Provider>
  )
}
