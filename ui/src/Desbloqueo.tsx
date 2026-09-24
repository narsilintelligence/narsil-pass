import { useEffect, useRef, useState } from 'react'
import escudo from './marca/escudo.png'
import { llamar, type Estado, type Info } from './api'
import { useApp } from './contexto'
import { Icono } from './iconos'
import { IDIOMAS, type Idioma } from './i18n'
import { Dialogo } from './Dialogos'

const nombreFichero = (ruta: string | null) => (ruta ? ruta.split(/[\\/]/).pop() ?? ruta : '')

export function MarcaBloque() {
  const { t } = useApp()
  return (
    <>
      <img className="arranque__logo" src={escudo} alt="" />
      <div className="marca-bloque">
        <span className="marca-bloque__narsil">NARSIL</span>
        <span className="marca-bloque__plataforma">{t('marca.plataforma')}</span>
        <span className="marca-bloque__producto">{t('marca.producto')}</span>
      </div>
      <div className="horizonte" aria-hidden="true" />
    </>
  )
}

export function Desbloqueo({ estado, aviso, alAbrir }: { estado: Estado; aviso?: string; alAbrir: (i: Info) => void }) {
  const { t, idioma, setIdioma } = useApp()
  const [ruta, setRuta] = useState<string | null>(estado.inicial ?? estado.recientes[0] ?? null)
  const [recientes, setRecientes] = useState(estado.recientes)
  const [clave, setClave] = useState('')
  const [ver, setVer] = useState(false)
  const [fichero, setFichero] = useState<string | null>(null)
  const [error, setError] = useState(aviso ?? '')
  const [ocupado, setOcupado] = useState(false)
  const [creando, setCreando] = useState(false)
  const campoClave = useRef<HTMLInputElement>(null)
  const formulario = useRef<HTMLFormElement>(null)

  useEffect(() => { campoClave.current?.focus() }, [ruta])

  const elegir = async () => {
    const r = await llamar<{ ruta: string | null }>('elegir_base')
    if (r.ok && r.ruta) { setRuta(r.ruta); setError('') }
  }
  const elegirFichero = async () => {
    const r = await llamar<{ ruta: string | null }>('elegir_fichero_clave')
    if (r.ok && r.ruta) setFichero(r.ruta)
  }
  const olvidar = async (r: string) => {
    await llamar('olvidar_reciente', r)
    const resto = recientes.filter((x) => x !== r)
    setRecientes(resto)
    if (ruta === r) setRuta(resto[0] ?? null)
  }
  // Se lee el campo real y no solo el estado: el autorrelleno del navegador no siempre avisa
  // Enter envía siempre; el botón no se deshabilita por vacío.
  const acceder = async (e?: React.FormEvent) => {
    e?.preventDefault()
    if (ocupado) return
    if (!ruta) { setError(t('desbloqueo.falta_base')); return }
    setOcupado(true); setError('')
    const r = await llamar<{ info: Info }>('desbloquear', ruta, campoClave.current?.value ?? clave, fichero)
    setOcupado(false)
    if (r.ok) { setClave(''); alAbrir(r.info) } else { setError(t(`error.${r.error}` as never) || t('error.interno')); campoClave.current?.select() }
  }

  return (
    <div className="arranque">
      <div className="arranque__caja">
        <MarcaBloque />
        <form ref={formulario} className="arranque__formulario" onSubmit={acceder}>
          <label className="campo"><span className="campo__rotulo">{t('desbloqueo.base')}</span>
            <div className="selector-base">
              {recientes.length > 0 ? (
                <select className="control" value={ruta ?? ''} onChange={(e) => setRuta(e.target.value || null)} aria-label={t('desbloqueo.recientes')}>
                  {ruta && !recientes.includes(ruta) && <option value={ruta}>{nombreFichero(ruta)}</option>}
                  {recientes.map((r) => <option key={r} value={r}>{nombreFichero(r)}</option>)}
                </select>
              ) : (
                <input className="control" readOnly value={ruta ? nombreFichero(ruta) : t('desbloqueo.ninguna')} title={ruta ?? ''} />
              )}
              <button type="button" className="boton" onClick={elegir}>{t('desbloqueo.elegir_base')}</button>
              {ruta && recientes.includes(ruta) && (
                <button type="button" className="boton boton--fantasma boton--icono" data-tip={t('desbloqueo.olvidar')} data-tip-lado="izquierda"
                        onClick={() => olvidar(ruta)} aria-label={t('desbloqueo.olvidar')}><Icono nombre="cerrar" /></button>
              )}
            </div>
          </label>
          <label className="campo"><span className="campo__rotulo">{t('desbloqueo.contrasena')}</span>
            <div className="grupo-control">
              <input ref={campoClave} className="control mono" type={ver ? 'text' : 'password'} value={clave} autoComplete="current-password"
                     onChange={(e) => setClave(e.target.value)} spellCheck={false}
                     onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); formulario.current?.requestSubmit() } }} />
              <button type="button" className="boton boton--icono" onClick={() => setVer(!ver)} data-tip={t('tip.mostrar')} data-tip-lado="izquierda"
                      aria-label={t('tip.mostrar')}><Icono nombre={ver ? 'ojo_cerrado' : 'ojo'} /></button>
            </div>
          </label>
          <label className="campo"><span className="campo__rotulo">{t('desbloqueo.fichero_clave')}</span>
            <div className="grupo-control">
              <input className="control" readOnly value={fichero ? nombreFichero(fichero) : t('desbloqueo.sin_fichero')} title={fichero ?? ''} />
              <button type="button" className="boton" onClick={elegirFichero}>{t('comun.elegir')}</button>
              {fichero && <button type="button" className="boton boton--fantasma" onClick={() => setFichero(null)}>{t('comun.quitar')}</button>}
            </div>
          </label>
          <button type="submit" className="boton boton--primario" style={{ marginTop: 4, height: 36 }}>
            <Icono nombre="candado" />{ocupado ? t('desbloqueo.desbloqueando') : t('desbloqueo.desbloquear')}
          </button>
          {error && <p className="error" role="alert" style={{ margin: 0 }}>{error}</p>}
        </form>
        <button className="enlace" onClick={() => setCreando(true)}>{t('desbloqueo.crear_nueva')}</button>
        <div className="arranque__pie">
          <span>{t('marca.pie')}</span><span>·</span><span className="mono">v{estado.version}</span>
        </div>
        <label className="casilla" style={{ gap: 8 }}>
          <span className="campo__rotulo">{t('comun.idioma')}</span>
          <select className="control" style={{ width: 'auto', height: 28 }} value={idioma} onChange={(e) => setIdioma(e.target.value as Idioma)}>
            {IDIOMAS.map((i) => <option key={i.id} value={i.id}>{i.nativo}</option>)}
          </select>
        </label>
      </div>
      {creando && <CrearBase alCerrar={() => setCreando(false)} alCrear={alAbrir} />}
    </div>
  )
}

function CrearBase({ alCerrar, alCrear }: { alCerrar: () => void; alCrear: (i: Info) => void }) {
  const { t } = useApp()
  const [nombre, setNombre] = useState('')
  const [ruta, setRuta] = useState<string | null>(null)
  const [clave, setClave] = useState('')
  const [repetir, setRepetir] = useState('')
  const [fichero, setFichero] = useState<string | null>(null)
  const [bits, setBits] = useState(0)
  const [error, setError] = useState('')
  const [ocupado, setOcupado] = useState(false)

  useEffect(() => {
    let vigente = true
    void llamar<{ bits: number }>('calidad', clave).then((r) => { if (vigente && r.ok) setBits(r.bits) })
    return () => { vigente = false }
  }, [clave])

  const elegirRuta = async () => {
    const r = await llamar<{ ruta: string | null }>('elegir_destino', `${nombre || 'NARSIL'}.kdbx`)
    if (r.ok && r.ruta) setRuta(r.ruta)
  }
  const generarFichero = async () => {
    const r = await llamar<{ ruta: string | null }>('crear_fichero_clave')
    if (r.ok && r.ruta) setFichero(r.ruta); else if (!r.ok) setError(t(`error.${r.error}` as never))
  }
  const crear = async () => {
    if (!nombre.trim() || !ruta || (!clave && !fichero)) { setError(t('crear.falta')); return }
    if (clave !== repetir) { setError(t('crear.no_coinciden')); return }
    setOcupado(true)
    const r = await llamar<{ info: Info }>('crear_base', ruta, nombre.trim(), clave || null, fichero)
    setOcupado(false)
    if (r.ok) { alCerrar(); alCrear(r.info) } else setError(t(`error.${r.error}` as never))
  }
  const color = bits < 50 ? 'var(--n-peligro)' : bits < 80 ? 'var(--n-aviso)' : 'var(--n-exito)'
  return (
    <Dialogo titulo={t('crear.titulo')} alCerrar={alCerrar} pie={<>
      <button className="boton" onClick={alCerrar}>{t('comun.cancelar')}</button>
      <button className="boton boton--primario" onClick={crear} disabled={ocupado}>{ocupado ? t('crear.creando') : t('crear.crear')}</button>
    </>}>
      <div className="dialogo__cuerpo">
        <label className="campo"><span className="campo__rotulo">{t('crear.nombre')}</span>
          <input className="control" value={nombre} autoFocus onChange={(e) => setNombre(e.target.value)} /></label>
        <label className="campo"><span className="campo__rotulo">{t('crear.ubicacion')}</span>
          <div className="grupo-control"><input className="control" readOnly value={ruta ?? ''} title={ruta ?? ''} />
            <button className="boton" onClick={elegirRuta}>{t('crear.elegir_ubicacion')}</button></div></label>
        <label className="campo"><span className="campo__rotulo">{t('desbloqueo.contrasena')}</span>
          <input className="control mono" type="password" value={clave} onChange={(e) => setClave(e.target.value)} autoComplete="new-password" />
          <div className="calidad"><i style={{ width: `${Math.min(100, bits / 1.28)}%`, background: color }} /></div>
          <span className="nota">{t('entrada.calidad', { b: bits })}</span></label>
        <label className="campo"><span className="campo__rotulo">{t('crear.repetir')}</span>
          <input className="control mono" type="password" value={repetir} onChange={(e) => setRepetir(e.target.value)} autoComplete="new-password"
                 onKeyDown={(e) => { if (e.key === 'Enter') void crear() }} /></label>
        <label className="campo"><span className="campo__rotulo">{t('crear.fichero_opcional')}</span>
          <div className="grupo-control"><input className="control" readOnly value={fichero ? nombreFichero(fichero) : ''} title={fichero ?? ''} />
            <button className="boton" onClick={generarFichero}>{t('crear.generar_fichero')}</button>
            {fichero && <button className="boton boton--fantasma" onClick={() => setFichero(null)}>{t('comun.quitar')}</button>}</div>
          {fichero && <span className="nota">{t('crear.aviso_fichero')}</span>}</label>
        <p className="nota" style={{ margin: 0 }}>{t('crear.formato')}</p>
        {error && <p className="error" role="alert" style={{ margin: 0 }}>{error}</p>}
      </div>
    </Dialogo>
  )
}
