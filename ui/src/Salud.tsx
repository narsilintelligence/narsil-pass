// Salud de las contraseñas (repetidas, débiles, a renovar, caducidad) y ayuda de atajos de teclado.
import { useState } from 'react'
import type { RefSalud, Salud } from './api'
import { useApp } from './contexto'
import { Icono } from './iconos'
import { fecha } from './i18n'
import { Dialogo } from './Dialogos'
import type { Mutar } from './Piezas'

export type PestanaSalud = 'repetidas' | 'debiles' | 'renovar' | 'caducidad'
export const PLAZOS_RENOVACION = [0, 90, 180, 365]

export function PanelSalud({ salud, inicial = 'repetidas', alIr, alCerrar, mutar }: {
  salud: Salud; inicial?: PestanaSalud; alIr: (r: RefSalud) => void; alCerrar: () => void; mutar: Mutar
}) {
  const { t, idioma } = useApp()
  const [pestana, setPestana] = useState<PestanaSalud>(inicial)
  const cuenta: Record<PestanaSalud, number> = {
    repetidas: salud.repetidas.length, debiles: salud.debiles.length, renovar: salud.renovar.length,
    caducidad: salud.caducadas.length + salud.por_caducar.length,
  }
  const campo = (r: RefSalud) => (!r.campo || r.campo === 'Password' ? t('salud.campo_principal') : t('salud.campo_servicio', { s: r.servicio || r.campo }))
  const fila = (r: RefSalud, detalle: string, clave: string) => (
    <button key={clave} className="salud__fila" onClick={() => alIr(r)}>
      <Icono nombre="llave" tamano={14} />
      <span className="salud__texto"><span className="salud__titulo">{r.titulo || t('entrada.sin_titulo')}</span><span className="nota">{detalle}</span></span>
      <Icono nombre="derecha" tamano={14} />
    </button>
  )
  return (
    <Dialogo titulo={t('salud.titulo')} alCerrar={alCerrar} ancho pie={<button className="boton boton--primario" onClick={alCerrar}>{t('comun.cerrar')}</button>}>
      <div className="pestanas">
        {(['repetidas', 'debiles', 'renovar', 'caducidad'] as PestanaSalud[]).map((p) => (
          <button key={p} className={`pestana${pestana === p ? ' pestana--activa' : ''}`} onClick={() => setPestana(p)}>
            {t(`salud.${p}`)}{cuenta[p] > 0 && <span className="insignia insignia--linea">{cuenta[p]}</span>}</button>
        ))}
      </div>
      <div className="dialogo__cuerpo salud">
        <p className="nota" style={{ margin: 0 }}>{t(`salud.explica_${pestana}`)}</p>
        {pestana === 'renovar' && (
          <label className="grupo-control" style={{ gap: 10 }}><span>{t('salud.politica')}</span>
            <select className="control" style={{ width: 150, flex: 'none' }} value={salud.renovar_dias} onChange={(e) => void mutar('fijar_renovacion', Number(e.target.value))}>
              {PLAZOS_RENOVACION.map((d) => <option key={d} value={d}>{d ? t('salud.dias', { n: d }) : t('salud.nunca')}</option>)}
            </select></label>
        )}
        {cuenta[pestana] === 0 && <p className="nota" style={{ margin: 0 }}>{t('salud.nada')}</p>}
        {pestana === 'repetidas' && salud.repetidas.map((g, i) => (
          <div className="salud__grupo" key={i}><div className="bloque__titulo">{t('salud.grupo_repetida', { n: g.length })}</div>
            {g.map((r, j) => fila(r, campo(r), `${i}-${j}`))}</div>
        ))}
        {pestana === 'debiles' && salud.debiles.map((r, i) => fila(r, `${campo(r)} · ${t('salud.bits', { b: r.bits ?? 0 })}`, String(i)))}
        {pestana === 'renovar' && salud.renovar.map((r, i) => fila(r, `${campo(r)} · ${t('salud.hace_dias', { n: r.dias ?? 0 })}`, String(i)))}
        {pestana === 'caducidad' && (<>
          {salud.caducadas.map((r, i) => fila(r, t('salud.caduco', { f: fecha(r.fecha, idioma) }), `c${i}`))}
          {salud.por_caducar.map((r, i) => fila(r, t('salud.caduca', { f: fecha(r.fecha, idioma) }), `p${i}`))}
        </>)}
      </div>
    </Dialogo>
  )
}

export function Atajos({ alCerrar }: { alCerrar: () => void }) {
  const { t } = useApp()
  const teclas: [string, string][] = [
    ['Ctrl+F', t('atajos.buscar')], ['Ctrl+N', t('atajos.nueva')], ['Ctrl+S', t('atajos.guardar')], ['Ctrl+L', t('atajos.bloquear')],
    ['Ctrl+B', t('atajos.usuario')], ['Ctrl+C', t('atajos.contrasena')], ['Ctrl+U', t('atajos.url')], ['Ctrl+T', t('atajos.totp')],
    ['Ctrl+E · Intro', t('atajos.editar')], ['Ctrl+Intro · Ctrl+S', t('atajos.guardar_editor')], ['Esc', t('atajos.cancelar')],
    ['Supr', t('atajos.eliminar')], ['Ctrl+D', t('atajos.duplicar')], ['↑ ↓', t('atajos.navegar')], ['Ctrl+1 … Ctrl+4', t('atajos.secciones')],
    ['F1', t('atajos.ayuda')],
  ]
  return (
    <Dialogo titulo={t('atajos.titulo')} alCerrar={alCerrar} ancho pie={<button className="boton boton--primario" onClick={alCerrar}>{t('comun.cerrar')}</button>}>
      <div className="dialogo__cuerpo">
        <div className="atajos">{teclas.map(([k, d]) => <div className="atajo" key={k}><kbd>{k}</kbd><span>{d}</span></div>)}</div>
        <div className="campo"><span className="campo__rotulo">{t('atajos.raton')}</span>
          {(['atajos.doble_clic', 'atajos.menu', 'atajos.arrastrar', 'atajos.pegar'] as const).map((k) => <span key={k} className="nota">{t(k)}</span>)}</div>
      </div>
    </Dialogo>
  )
}
