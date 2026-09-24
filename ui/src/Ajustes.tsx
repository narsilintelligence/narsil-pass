import { useState } from 'react'
import { llamar, type Info, type Preferencias } from './api'
import { useApp } from './contexto'
import { IDIOMAS, type Idioma } from './i18n'
import { Dialogo } from './Dialogos'
import { PLAZOS_RENOVACION } from './Salud'

export function Ajustes({ info, alCerrar, mutar }: { info: Info; alCerrar: () => void; mutar: (m: string, ...a: unknown[]) => Promise<unknown> }) {
  const { t, idioma, setIdioma, avisar } = useApp()
  const [pestana, setPestana] = useState<'aplicacion' | 'base' | 'acerca'>('aplicacion')
  const [pref, setPref] = useState<Preferencias | null>(null)
  const [version, setVersion] = useState('')
  const [nombre, setNombre] = useState(info.nombre)
  const [descripcion, setDescripcion] = useState(info.descripcion)
  const [cifrado, setCifrado] = useState(info.cifrado)
  const [segundos, setSegundos] = useState(1)
  const [clave, setClave] = useState('')
  const [repetir, setRepetir] = useState('')
  const [aviso, setAviso] = useState('')

  if (pref === null) {
    void llamar<{ preferencias: Preferencias; version: string }>('estado').then((r) => { if (r.ok) { setPref(r.preferencias); setVersion(r.version) } })
    return null
  }
  const cambiarPref = (cambio: Partial<Preferencias>) => {
    const nuevas = { ...pref, ...cambio }
    setPref(nuevas)
    void llamar('guardar_preferencias', cambio)
  }
  const aplicarBase = async () => {
    await mutar('ajustar_base', nombre, descripcion)
    if (!info.es_v3 && cifrado !== info.cifrado) await mutar('ajustar_seguridad', cifrado, null)
    avisar(t('ajustes.aplicado'))
  }
  const aplicarTiempo = async () => { await mutar('ajustar_seguridad', null, segundos); avisar(t('ajustes.aplicado')) }
  const cambiarClave = async () => {
    if (!clave || clave !== repetir) { setAviso(t('crear.no_coinciden')); return }
    await mutar('cambiar_clave', clave, null); setClave(''); setRepetir(''); setAviso(''); avisar(t('ajustes.aplicado'))
  }
  const fila = (rotulo: string, control: React.ReactNode) => (
    <div style={{ display: 'grid', gridTemplateColumns: '1fr auto', alignItems: 'center', gap: 12 }}><span>{rotulo}</span>{control}</div>
  )
  return (
    <Dialogo titulo={t('ajustes.titulo')} alCerrar={alCerrar} ancho pie={<button className="boton boton--primario" onClick={alCerrar}>{t('comun.cerrar')}</button>}>
      <div className="pestanas">
        {(['aplicacion', 'base', 'acerca'] as const).map((p) => (
          <button key={p} className={`pestana${pestana === p ? ' pestana--activa' : ''}`} onClick={() => setPestana(p)}>{t(`ajustes.${p}`)}</button>
        ))}
      </div>
      {pestana === 'aplicacion' && (
        <div className="dialogo__cuerpo">
          {fila(t('comun.idioma'), <select className="control" style={{ width: 180 }} value={idioma} onChange={(e) => setIdioma(e.target.value as Idioma)}>
            {IDIOMAS.map((i) => <option key={i.id} value={i.id}>{i.nativo}</option>)}</select>)}
          {fila(t('ajustes.bloqueo'), <select className="control" style={{ width: 180 }} value={pref.bloqueo_minutos} onChange={(e) => cambiarPref({ bloqueo_minutos: Number(e.target.value) })}>
            {[0, 1, 2, 5, 10, 15, 30, 60].map((m) => <option key={m} value={m}>{m ? t('ajustes.minutos', { n: m }) : t('ajustes.nunca')}</option>)}</select>)}
          {fila(t('ajustes.portapapeles'), <select className="control" style={{ width: 180 }} value={pref.portapapeles_segundos} onChange={(e) => cambiarPref({ portapapeles_segundos: Number(e.target.value) })}>
            {[5, 10, 12, 20, 30, 60, 120].map((s) => <option key={s} value={s}>{t('ajustes.segundos', { n: s })}</option>)}</select>)}
          <label className="casilla"><input type="checkbox" checked={pref.autoguardado} onChange={(e) => cambiarPref({ autoguardado: e.target.checked })} />{t('ajustes.autoguardado')}</label>
          <label className="casilla"><input type="checkbox" checked={pref.copia_previa} onChange={(e) => cambiarPref({ copia_previa: e.target.checked })} />{t('ajustes.copia_previa')}</label>
          <label className="casilla"><input type="checkbox" checked={pref.recordar_recientes} onChange={(e) => cambiarPref({ recordar_recientes: e.target.checked })} />{t('ajustes.recientes')}</label>
        </div>
      )}
      {pestana === 'base' && (
        <div className="dialogo__cuerpo">
          <div className="editor__fila">
            <label className="campo"><span className="campo__rotulo">{t('ajustes.nombre_base')}</span><input className="control" value={nombre} onChange={(e) => setNombre(e.target.value)} /></label>
            <label className="campo"><span className="campo__rotulo">{t('ajustes.descripcion')}</span><input className="control" value={descripcion} onChange={(e) => setDescripcion(e.target.value)} /></label>
          </div>
          <div className="editor__fila">
            <div className="campo"><span className="campo__rotulo">{t('ajustes.formato')}</span><span><span className="chip chip--formato">{info.formato}</span> · {info.kdf}</span></div>
            <label className="campo"><span className="campo__rotulo">{t('ajustes.cifrado')}</span>
              <select className="control" value={cifrado} disabled={info.es_v3} onChange={(e) => setCifrado(e.target.value)}>
                <option value="ChaCha20">ChaCha20</option><option value="AES-256">AES-256</option></select></label>
          </div>
          <div><button className="boton" onClick={() => void aplicarBase()}>{t('ajustes.aplicar')}</button></div>
          <label className="campo"><span className="campo__rotulo">{t('ajustes.tiempo')}</span>
            <div className="grupo-control"><input className="control" type="number" min={0.2} max={10} step={0.1} value={segundos} onChange={(e) => setSegundos(Number(e.target.value))} style={{ width: 110, flex: 'none' }} />
              <button className="boton" onClick={() => void aplicarTiempo()}>{t('ajustes.aplicar')}</button></div>
            <span className="nota">{t('ajustes.tiempo_ayuda')}</span></label>
          <div className="campo"><span className="campo__rotulo">{t('ajustes.cambiar_clave')}</span>
            <div className="editor__fila">
              <input className="control mono" type="password" placeholder={t('ajustes.nueva_clave')} value={clave} onChange={(e) => setClave(e.target.value)} autoComplete="new-password" />
              <input className="control mono" type="password" placeholder={t('crear.repetir')} value={repetir} onChange={(e) => setRepetir(e.target.value)} autoComplete="new-password" />
            </div>
            <div><button className="boton" onClick={() => void cambiarClave()}>{t('ajustes.cambiar_clave')}</button></div>
            {aviso && <span className="error">{aviso}</span>}</div>
          {info.es_v3 && (
            <div className="campo"><span className="campo__rotulo">{t('ajustes.convertir')}</span>
              <span className="nota">{t('ajustes.convertir_texto')}</span>
              <div><button className="boton" onClick={async () => { await mutar('convertir_a_kdbx4'); avisar(t('ajustes.aplicado')) }}>{t('ajustes.convertir')}</button></div></div>
          )}
          <label className="campo"><span className="campo__rotulo">{t('salud.politica')}</span>
            <select className="control" style={{ width: 180 }} value={info.renovar_dias} onChange={async (e) => { await mutar('fijar_renovacion', Number(e.target.value)); avisar(t('ajustes.aplicado')) }}>
              {PLAZOS_RENOVACION.map((d) => <option key={d} value={d}>{d ? t('salud.dias', { n: d }) : t('salud.nunca')}</option>)}</select>
            <span className="nota">{t('ajustes.renovar_ayuda')}</span></label>
          <div className="campo"><span className="campo__rotulo">{t('ajustes.ruta')}</span><span className="mono nota seleccionable">{info.ruta}</span></div>
        </div>
      )}
      {pestana === 'acerca' && (
        <div className="dialogo__cuerpo">
          <div style={{ fontFamily: 'var(--n-titular)', letterSpacing: '.2em', fontSize: 18 }}>NARSIL PASS</div>
          <span>{t('ajustes.version', { v: version })}</span>
          <span className="nota">{t('ajustes.local')}</span>
          <span className="nota">{t('ajustes.licencia')}</span>
          <div className="campo"><span className="campo__rotulo">{t('ajustes.terceros')}</span>
            <span className="nota">Python (PSF) · cryptography (Apache-2.0/BSD) · argon2-cffi (MIT) · pycryptodomex (BSD) · lxml (BSD) · pywebview (BSD) · React (MIT) · Archivo, JetBrains Mono (SIL OFL) · EFF Large Wordlist (CC BY 3.0 US)</span></div>
        </div>
      )}
    </Dialogo>
  )
}
