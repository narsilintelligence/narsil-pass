// Identidad operativa: ficha del avatar, servicios en los que está registrada, fotos y biografía.
// Vista (lectura, copia y fotos) y editor (todo opcional). El modelo vive en ficha.ts.
import { useEffect, useMemo, useState } from 'react'
import { llamar, type Campo, type Detalle } from './api'
import { useApp } from './contexto'
import { Icono } from './iconos'
import { fecha } from './i18n'
import { Confirmar } from './Dialogos'
import { Generador } from './Generador'
import { Dato, EditorCampos, FilaTotp, Galeria, Historial, teclasEditor, type Mutar } from './Piezas'
import {
  CAMPOS_SERVICIO, ESTADOS, FICHA, claveReservada, claveServicio, edad, escribirIdentidad, esImagen, leerIdentidad,
  normalizarOtp, rotuloFicha, rotuloSeccion, servicioVacio, type CampoFicha, type Identidad,
} from './ficha'

type PestanaVista = 'ficha' | 'servicios' | 'fotos' | 'biografia' | 'historial'

const host = (url: string) => url.trim().toLowerCase().replace(/^[a-z][a-z0-9+.-]*:\/\//, '').split(/[/?#:]/)[0].replace(/^www\./, '')

export function ChipEstado({ estado }: { estado: string }) {
  const { t } = useApp()
  if (!estado) return null
  const conocido = (ESTADOS as readonly string[]).includes(estado)
  return <span className={`chip chip--estado chip--${conocido ? estado : 'otro'}`}>{conocido ? t(`estado.${estado}` as never) : estado}</span>
}

export function VistaIdentidad({ d, mutar, alEditar, alMover, alEliminado }: {
  d: Detalle; mutar: Mutar; alEditar: () => void; alMover: () => void; alEliminado: () => void
}) {
  const { t, idioma, copiar } = useApp()
  const [pestana, setPestana] = useState<PestanaVista>('ficha')
  const [avatar, setAvatar] = useState<string | null>(null)
  const [confirmar, setConfirmar] = useState(false)
  const id = useMemo(() => leerIdentidad(d.campos), [d.campos])
  const campo = (clave: string) => d.campos.find((c) => c.clave === clave)
  const primeraFoto = d.adjuntos_lista.find((a) => esImagen(a.nombre))?.nombre
  const editable = !d.en_papelera

  useEffect(() => {
    setAvatar(null)
    if (!primeraFoto) return
    let vigente = true
    void llamar<{ url: string }>('imagen', d.uuid, primeraFoto).then((r) => { if (vigente && r.ok) setAvatar(r.url) })
    return () => { vigente = false }
  }, [d.uuid, primeraFoto])

  const datoFicha = (c: CampoFicha) => {
    const v = id.ficha[c.id]
    if (!v) return null
    let mostrar = v
    if (c.control === 'estado' && (ESTADOS as readonly string[]).includes(v)) mostrar = t(`estado.${v}` as never)
    if (c.control === 'fecha') {
      mostrar = fecha(v, idioma)
      const e = c.id === 'fecha_nacimiento' ? edad(v) : null
      if (e !== null) mostrar += ` · ${t('identidad.anos', { n: e })}`
    }
    return <Dato key={c.id} uuid={d.uuid} clave={`Ficha.${c.id}`} rotulo={t(rotuloFicha(c.id))} valor={v} mostrar={mostrar} />
  }
  const cuenta = ['UserName', 'Password', 'URL'].map((k) => campo(k)).filter((c): c is Campo => !!c && !c.vacio)
  const notas = campo('Notes')
  const otros = id.otros.filter((c) => !['otp', 'TOTP Seed', 'TOTP Settings'].includes(c.clave))
  const secciones = FICHA.filter((s) => s.campos.some((c) => id.ficha[c.id]))
  const fotos = d.adjuntos_lista.filter((a) => esImagen(a.nombre)).length
  const nombreVisible = d.titulo || [id.ficha.nombre, id.ficha.apellidos].filter(Boolean).join(' ') || t('entrada.sin_titulo')

  return (
    <div className="detalle">
      <div className="detalle__cabeza">
        <div className="avatar">{avatar ? <img src={avatar} alt="" draggable={false} /> : <Icono nombre="identidad" tamano={26} />}</div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <h1 className="detalle__titulo seleccionable">{nombreVisible}</h1>
          <div className="etiquetas" style={{ marginTop: 6 }}>
            <ChipEstado estado={id.ficha.estado ?? ''} />
            {id.ficha.operacion && <span className="chip">{id.ficha.operacion}</span>}
            {d.en_papelera && <span className="chip chip--aviso">{t('entrada.en_papelera')}</span>}
            {d.alertas.map((a) => <span key={a} className={`chip ${a === 'renovar' || a === 'por_caducar' ? 'chip--aviso' : 'chip--peligro'}`}>{t(`alerta.${a}` as never)}</span>)}
            {d.etiquetas.map((e) => <span key={e} className="chip">{e}</span>)}
          </div>
        </div>
        <div className="detalle__acciones">
          {editable && <button className="boton boton--sm" onClick={alEditar}><Icono nombre="lapiz" tamano={14} />{t('comun.editar')}</button>}
          {editable && <button className="boton boton--sm boton--icono" onClick={() => void mutar('duplicar_entrada', d.uuid)} title={t('entrada.duplicar')} aria-label={t('entrada.duplicar')}><Icono nombre="duplicar" tamano={14} /></button>}
          <button className="boton boton--sm boton--icono" onClick={alMover} title={t('entrada.mover')} aria-label={t('entrada.mover')}><Icono nombre="mover" tamano={14} /></button>
          <button className="boton boton--sm boton--icono boton--peligro" title={t('comun.eliminar')} aria-label={t('comun.eliminar')}
                  onClick={() => (d.en_papelera ? setConfirmar(true) : void mutar('eliminar_entrada', d.uuid).then(alEliminado))}><Icono nombre="papelera" tamano={14} /></button>
        </div>
      </div>

      <div className="pestanas pestanas--detalle">
        {([['ficha', t('identidad.pestana_ficha')], ['servicios', `${t('identidad.pestana_servicios')} · ${id.servicios.length}`],
          ['fotos', `${t('identidad.pestana_fotos')} · ${fotos}`], ['biografia', t('identidad.pestana_biografia')],
          ['historial', t('identidad.pestana_historial')]] as [PestanaVista, string][]).map(([p, r]) => (
          <button key={p} className={`pestana${pestana === p ? ' pestana--activa' : ''}`} onClick={() => setPestana(p)}>{r}</button>
        ))}
      </div>

      {pestana === 'ficha' && (<>
        {(cuenta.length > 0 || d.totp) && (
          <div className="bloque"><div className="bloque__titulo">{t('identidad.cuenta_principal')}</div>
            {cuenta.map((c) => <Dato key={c.clave} uuid={d.uuid} clave={c.clave} rotulo={t(`campo.${c.clave}` as never)} valor={c.valor} protegido={c.protegido} vacio={c.vacio} />)}
            <FilaTotp uuid={d.uuid} activo={d.totp} />
          </div>
        )}
        {secciones.map((s) => (
          <div className="bloque" key={s.id}><div className="bloque__titulo">{t(rotuloSeccion(s.id))}</div>{s.campos.map(datoFicha)}</div>
        ))}
        {notas && !notas.vacio && <div className="bloque"><div className="bloque__titulo">{t('campo.Notes')}</div>
          <Dato uuid={d.uuid} clave="Notes" rotulo={t('campo.Notes')} valor={notas.valor} protegido={notas.protegido} /></div>}
        {otros.length > 0 && <div className="bloque"><div className="bloque__titulo">{t('identidad.otros_campos')}</div>
          {otros.map((c) => <Dato key={c.clave} uuid={d.uuid} clave={c.clave} rotulo={c.clave} valor={c.valor} protegido={c.protegido} vacio={c.vacio} />)}</div>}
        {secciones.length === 0 && cuenta.length === 0 && otros.length === 0 && <p className="nota">{t('identidad.ficha_vacia')}</p>}
      </>)}

      {pestana === 'servicios' && (
        id.servicios.length === 0 ? <p className="nota">{t('servicio.ninguno')}</p> : (
          <div className="servicios">
            {id.servicios.map((s, i) => {
              const n = id.numeros[i]
              return (
                <div className="servicio" key={n}>
                  <div className="servicio__cabeza"><Icono nombre="globo" tamano={15} /><strong>{s.nombre || t('servicio.sin_nombre')}</strong>
                    {s.url && <span className="tenue mono">{host(s.url)}</span>}</div>
                  {CAMPOS_SERVICIO.filter((c) => c !== 'nombre').map((c) => {
                    const k = campo(claveServicio(n, c))
                    return k ? <Dato key={c} uuid={d.uuid} clave={k.clave} rotulo={t(`servicio.${c}` as never)} valor={k.valor} protegido={k.protegido} vacio={k.vacio} /> : null
                  })}
                </div>
              )
            })}
          </div>
        )
      )}

      {pestana === 'fotos' && <Galeria uuid={d.uuid} adjuntos={d.adjuntos_lista} editable={editable} fotos mutar={mutar} />}

      {pestana === 'biografia' && (
        id.biografia ? (
          <div className="texto-largo">
            <div className="texto-largo__acciones"><button className="boton boton--fantasma boton--sm" onClick={() => void copiar(d.uuid, 'Ficha.biografia')}><Icono nombre="copiar" tamano={14} />{t('comun.copiar')}</button></div>
            <div className="seleccionable" draggable onDragStart={(e) => e.dataTransfer.setData('text/plain', id.biografia)}>{id.biografia}</div>
          </div>
        ) : <p className="nota">{t('identidad.biografia_vacia')}</p>
      )}

      {pestana === 'historial' && <div className="bloque"><Historial uuid={d.uuid} historial={d.historial} editable={editable} mutar={mutar} /></div>}

      <p className="nota" style={{ margin: 0 }}>{t('entrada.creada')}: {fecha(d.fechas.CreationTime, idioma, true)} · {t('entrada.modificada')}: {fecha(d.fechas.LastModificationTime, idioma, true)}</p>
      {confirmar && <Confirmar titulo={t('comun.eliminar')} texto={t('principal.confirmar_eliminar_def', { t: nombreVisible })} accion={t('comun.eliminar')} peligro
                               alAceptar={() => void mutar('eliminar_entrada', d.uuid).then(alEliminado)} alCerrar={() => setConfirmar(false)} />}
    </div>
  )
}

type PestanaEditor = 'ficha' | 'servicios' | 'biografia' | 'cuenta'

export function EditorIdentidad({ uuid, alCerrar, alGuardar }: {
  uuid?: string; alCerrar: () => void; alGuardar: (campos: Campo[], etiquetas: string[], expira: string) => Promise<void>
}) {
  const { t, error } = useApp()
  const [id, setId] = useState<Identidad | null>(null)
  const [etiquetas, setEtiquetas] = useState('')
  const [caduca, setCaduca] = useState(false)
  const [fechaCaduca, setFechaCaduca] = useState('')
  const [pestana, setPestana] = useState<PestanaEditor>('ficha')
  const [ver, setVer] = useState(false)
  const [generador, setGenerador] = useState<null | 'principal' | number>(null)
  const [aviso, setAviso] = useState('')
  const [inicial, setInicial] = useState('')
  const [descartar, setDescartar] = useState(false)

  useEffect(() => {
    if (!uuid) {
      const nueva: Identidad = { estandar: { Title: '' }, ficha: { estado: 'activa' }, biografia: '', servicios: [servicioVacio()], numeros: [0], leidos: [], otros: [] }
      setId(nueva); setEtiquetas(''); setInicial(JSON.stringify([nueva, '', false, '']))
      return
    }
    void llamar<{ entrada: Detalle }>('para_editar', uuid).then((r) => {
      if (!r.ok) { error(r.error); return }
      const leida = leerIdentidad(r.entrada.campos)
      const tags = r.entrada.etiquetas.join(', ')
      const f = r.entrada.expira ? r.entrada.expira.slice(0, 10) : ''
      setId(leida); setEtiquetas(tags); setCaduca(!!r.entrada.expira); setFechaCaduca(f)
      setInicial(JSON.stringify([leida, tags, !!r.entrada.expira, f]))
    })
  }, [uuid, error])

  if (!id) return null
  const sucio = JSON.stringify([id, etiquetas, caduca, fechaCaduca]) !== inicial
  const cancelar = () => (sucio ? setDescartar(true) : alCerrar())
  const ponerEstandar = (k: string, v: string) => setId({ ...id, estandar: { ...id.estandar, [k]: v } })
  const ponerFicha = (k: string, v: string) => setId({ ...id, ficha: { ...id.ficha, [k]: v } })
  const ponerServicio = (i: number, k: string, v: string) => setId({ ...id, servicios: id.servicios.map((s, j) => (j === i ? { ...s, [k]: v } : s)) })
  const guardar = async () => {
    const claves = id.otros.map((c) => c.clave.trim())
    if (new Set(claves).size !== claves.length || claves.some((c) => !c || claveReservada(c))) { setPestana('cuenta'); setAviso(t('entrada.campo_existe')); return }
    const campos = normalizarOtp(escribirIdentidad({ ...id, otros: id.otros.map((c) => ({ ...c, clave: c.clave.trim() })) }))
    await alGuardar(campos, etiquetas.split(',').map((x) => x.trim()).filter(Boolean), caduca && fechaCaduca ? `${fechaCaduca}T00:00:00+00:00` : '')
  }

  const control = (c: CampoFicha) => {
    const v = id.ficha[c.id] ?? ''
    const rotulo = <span className="campo__rotulo">{t(rotuloFicha(c.id))}</span>
    if (c.control === 'largo') return <label key={c.id} className="campo campo--ancho">{rotulo}<textarea className="control" value={v} onChange={(e) => ponerFicha(c.id, e.target.value)} /></label>
    if (c.control === 'fecha') return <label key={c.id} className="campo">{rotulo}<input className="control" type="date" value={v} onChange={(e) => ponerFicha(c.id, e.target.value)} /></label>
    if (c.control === 'estado') return (
      <label key={c.id} className="campo">{rotulo}<select className="control" value={v} onChange={(e) => ponerFicha(c.id, e.target.value)}>
        <option value="">{t('identidad.sin_estado')}</option>
        {ESTADOS.map((s) => <option key={s} value={s}>{t(`estado.${s}` as never)}</option>)}
        {v && !(ESTADOS as readonly string[]).includes(v) && <option value={v}>{v}</option>}
      </select></label>)
    const e = c.id === 'edad' && !v && id.ficha.fecha_nacimiento ? edad(id.ficha.fecha_nacimiento) : null
    return <label key={c.id} className="campo">{rotulo}<input className="control" value={v} placeholder={e !== null ? String(e) : ''} spellCheck={false} onChange={(ev) => ponerFicha(c.id, ev.target.value)} /></label>
  }

  return (
    <div className="editor" onKeyDown={(e) => teclasEditor(e, () => void guardar(), cancelar)}>
      <h1 className="detalle__titulo">{uuid ? id.estandar.Title || t('entrada.sin_titulo') : t('principal.nueva_identidad')}</h1>
      <label className="campo"><span className="campo__rotulo">{t('identidad.nombre')}</span>
        <input className="control" autoFocus value={id.estandar.Title ?? ''} onChange={(e) => ponerEstandar('Title', e.target.value)} /></label>
      <div className="pestanas pestanas--detalle">
        {([['ficha', t('identidad.pestana_ficha')], ['servicios', `${t('identidad.pestana_servicios')} · ${id.servicios.length}`],
          ['biografia', t('identidad.pestana_biografia')], ['cuenta', t('identidad.pestana_cuenta')]] as [PestanaEditor, string][]).map(([p, r]) => (
          <button key={p} className={`pestana${pestana === p ? ' pestana--activa' : ''}`} onClick={() => setPestana(p)}>{r}</button>
        ))}
      </div>

      {pestana === 'ficha' && (<>
        <p className="nota" style={{ margin: 0 }}>{t('identidad.opcional')}</p>
        {FICHA.map((s) => (
          <fieldset className="ficha-seccion" key={s.id}><legend>{t(rotuloSeccion(s.id))}</legend>
            <div className="ficha-rejilla">{s.campos.map(control)}</div></fieldset>
        ))}
      </>)}

      {pestana === 'servicios' && (<>
        {id.servicios.map((s, i) => (
          <fieldset className="ficha-seccion" key={i}>
            <legend>{s.nombre || t('servicio.sin_nombre')}</legend>
            <div className="ficha-rejilla">
              {CAMPOS_SERVICIO.map((c) => c === 'contrasena' ? (
                <label key={c} className="campo"><span className="campo__rotulo">{t('servicio.contrasena')}</span>
                  <div className="grupo-control">
                    <input className="control mono" type={ver ? 'text' : 'password'} value={s.contrasena} spellCheck={false} autoComplete="new-password" onChange={(e) => ponerServicio(i, c, e.target.value)} />
                    <button type="button" className="boton boton--icono" onClick={() => setVer(!ver)} title={t('tip.mostrar')} aria-label={t('tip.mostrar')}><Icono nombre={ver ? 'ojo_cerrado' : 'ojo'} /></button>
                    <button type="button" className="boton boton--icono" onClick={() => setGenerador(i)} title={t('principal.generador')} aria-label={t('principal.generador')}><Icono nombre="dado" /></button>
                  </div></label>
              ) : c === 'notas' ? (
                <label key={c} className="campo campo--ancho"><span className="campo__rotulo">{t('servicio.notas')}</span>
                  <textarea className="control" value={s.notas} onChange={(e) => ponerServicio(i, c, e.target.value)} /></label>
              ) : (
                <label key={c} className="campo"><span className="campo__rotulo">{t(`servicio.${c}` as never)}</span>
                  <input className="control" value={s[c]} spellCheck={false} onChange={(e) => ponerServicio(i, c, e.target.value)} /></label>
              ))}
            </div>
            <div><button className="boton boton--sm boton--peligro" onClick={() => setId({ ...id, servicios: id.servicios.filter((_, j) => j !== i), numeros: id.numeros.filter((_, j) => j !== i) })}>
              <Icono nombre="papelera" tamano={14} />{t('servicio.quitar')}</button></div>
          </fieldset>
        ))}
        <div><button className="boton boton--sm" onClick={() => setId({ ...id, servicios: [...id.servicios, servicioVacio()], numeros: [...id.numeros, 0] })}><Icono nombre="mas" tamano={14} />{t('servicio.anadir')}</button></div>
      </>)}

      {pestana === 'biografia' && (
        <label className="campo"><span className="nota">{t('identidad.biografia_ayuda')}</span>
          <textarea className="control" style={{ minHeight: 340 }} value={id.biografia} onChange={(e) => setId({ ...id, biografia: e.target.value })} /></label>
      )}

      {pestana === 'cuenta' && (<>
        <div className="campo"><span className="campo__rotulo">{t('identidad.cuenta_principal')}</span><span className="nota">{t('identidad.cuenta_ayuda')}</span></div>
        <div className="editor__fila">
          <label className="campo"><span className="campo__rotulo">{t('campo.UserName')}</span>
            <input className="control" value={id.estandar.UserName ?? ''} spellCheck={false} onChange={(e) => ponerEstandar('UserName', e.target.value)} /></label>
          <label className="campo"><span className="campo__rotulo">{t('campo.URL')}</span>
            <input className="control" value={id.estandar.URL ?? ''} spellCheck={false} onChange={(e) => ponerEstandar('URL', e.target.value)} /></label>
        </div>
        <label className="campo"><span className="campo__rotulo">{t('campo.Password')}</span>
          <div className="grupo-control">
            <input className="control mono" type={ver ? 'text' : 'password'} value={id.estandar.Password ?? ''} spellCheck={false} autoComplete="new-password" onChange={(e) => ponerEstandar('Password', e.target.value)} />
            <button type="button" className="boton boton--icono" onClick={() => setVer(!ver)} title={t('tip.mostrar')} aria-label={t('tip.mostrar')}><Icono nombre={ver ? 'ojo_cerrado' : 'ojo'} /></button>
            <button type="button" className="boton boton--icono" onClick={() => setGenerador('principal')} title={t('principal.generador')} aria-label={t('principal.generador')}><Icono nombre="dado" /></button>
          </div></label>
        <label className="campo"><span className="campo__rotulo">{t('campo.Notes')}</span>
          <textarea className="control" value={id.estandar.Notes ?? ''} onChange={(e) => ponerEstandar('Notes', e.target.value)} /></label>
        <EditorCampos campos={id.otros} ver={ver} alCambiar={(otros) => setId({ ...id, otros: otros.map((c) => ({ ...c, valor: c.valor ?? '' })) })} />
        <div className="editor__fila">
          <label className="campo"><span className="campo__rotulo">{t('entrada.etiquetas')}</span>
            <input className="control" value={etiquetas} placeholder={t('entrada.etiquetas_ayuda')} onChange={(e) => setEtiquetas(e.target.value)} /></label>
          <div className="campo"><span className="campo__rotulo">{t('entrada.fecha_caducidad')}</span>
            <div className="grupo-control"><label className="casilla"><input type="checkbox" checked={caduca} onChange={(e) => setCaduca(e.target.checked)} />{t('entrada.caduca')}</label>
              <input className="control" type="date" disabled={!caduca} value={fechaCaduca} onChange={(e) => setFechaCaduca(e.target.value)} /></div></div>
        </div>
      </>)}

      {aviso && <p className="error" style={{ margin: 0 }}>{aviso}</p>}
      <div className="editor__pie">
        <button className="boton" onClick={cancelar}>{t('comun.cancelar')}</button>
        <button className="boton boton--primario" onClick={() => void guardar()}><Icono nombre="ok" tamano={14} />{t('comun.guardar')}</button>
      </div>
      {generador !== null && <Generador alCerrar={() => setGenerador(null)} alUsar={(v) => {
        if (generador === 'principal') ponerEstandar('Password', v); else ponerServicio(generador, 'contrasena', v)
        setVer(true); setGenerador(null)
      }} />}
      {descartar && <Confirmar titulo={t('editor.descartar_titulo')} texto={t('editor.descartar_texto')} accion={t('editor.descartar')} peligro
                               alAceptar={alCerrar} alCerrar={() => setDescartar(false)} />}
    </div>
  )
}
