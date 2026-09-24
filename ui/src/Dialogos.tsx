import { useEffect, useRef, useState, type ReactNode } from 'react'
import { Icono } from './iconos'
import { useApp } from './contexto'

export function Dialogo({ titulo, alCerrar, children, pie, ancho = false }: {
  titulo: string; alCerrar: () => void; children: ReactNode; pie?: ReactNode; ancho?: boolean
}) {
  const { t } = useApp()
  useEffect(() => {
    const tecla = (e: KeyboardEvent) => { if (e.key === 'Escape') alCerrar() }
    window.addEventListener('keydown', tecla)
    return () => window.removeEventListener('keydown', tecla)
  }, [alCerrar])
  return (
    <div className="velo" onMouseDown={(e) => { if (e.target === e.currentTarget) alCerrar() }}>
      <div className={`dialogo${ancho ? ' dialogo--ancho' : ''}`} role="dialog" aria-modal="true" aria-label={titulo}>
        <div className="dialogo__cabeza">
          <h2>{titulo}</h2>
          <button className="boton boton--fantasma boton--icono" onClick={alCerrar} aria-label={t('comun.cerrar')}><Icono nombre="cerrar" /></button>
        </div>
        {children}
        {pie && <div className="dialogo__pie">{pie}</div>}
      </div>
    </div>
  )
}

export function Confirmar({ titulo, texto, accion, peligro = false, alAceptar, alCerrar }: {
  titulo: string; texto: string; accion: string; peligro?: boolean; alAceptar: () => void; alCerrar: () => void
}) {
  const { t } = useApp()
  return (
    <Dialogo titulo={titulo} alCerrar={alCerrar} pie={<>
      <button className="boton" onClick={alCerrar}>{t('comun.cancelar')}</button>
      <button className={`boton ${peligro ? 'boton--peligro' : 'boton--primario'}`} autoFocus onClick={() => { alAceptar(); alCerrar() }}>{accion}</button>
    </>}>
      <div className="dialogo__cuerpo"><p className="nota" style={{ margin: 0, fontSize: 'var(--n-t-base)' }}>{texto}</p></div>
    </Dialogo>
  )
}

export function PedirTexto({ titulo, rotulo, inicial = '', alAceptar, alCerrar }: {
  titulo: string; rotulo: string; inicial?: string; alAceptar: (v: string) => void; alCerrar: () => void
}) {
  const { t } = useApp()
  const [valor, setValor] = useState(inicial)
  const ref = useRef<HTMLInputElement>(null)
  useEffect(() => { ref.current?.select() }, [])
  const enviar = () => { if (valor.trim()) { alAceptar(valor.trim()); alCerrar() } }
  return (
    <Dialogo titulo={titulo} alCerrar={alCerrar} pie={<>
      <button className="boton" onClick={alCerrar}>{t('comun.cancelar')}</button>
      <button className="boton boton--primario" onClick={enviar}>{t('comun.aceptar')}</button>
    </>}>
      <div className="dialogo__cuerpo">
        <label className="campo"><span className="campo__rotulo">{rotulo}</span>
          <input ref={ref} className="control" value={valor} autoFocus onChange={(e) => setValor(e.target.value)}
                 onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); enviar() } }} /></label>
      </div>
    </Dialogo>
  )
}
