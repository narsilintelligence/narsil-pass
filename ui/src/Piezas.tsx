// Piezas compartidas por las vistas de entrada e identidad: el dato copiable y la galería de adjuntos.
import { useCallback, useEffect, useRef, useState, type DragEvent } from 'react'
import { llamar } from './api'
import { useApp } from './contexto'
import { Icono } from './iconos'
import { fecha, tamano } from './i18n'
import { esImagen } from './ficha'

export type Mutar = (metodo: string, ...args: unknown[]) => Promise<Record<string, unknown> | null>

/** Un campo de la entrada: se copia con su botón o con doble clic, y si está a la vista se puede
 *  arrastrar a otra aplicación. Los protegidos se revelan bajo demanda, nunca vienen en el detalle. */
export function Dato({ uuid, clave, rotulo, valor, protegido = false, vacio = false, mono = false, mostrar }: {
  uuid: string; clave: string; rotulo: string; valor: string | null; protegido?: boolean; vacio?: boolean; mono?: boolean
  mostrar?: string
}) {
  const { t, copiar } = useApp()
  const [visible, setVisible] = useState<string | null>(null)
  useEffect(() => setVisible(null), [uuid, clave])
  if (vacio && !valor) return null
  const alternar = async () => {
    if (visible !== null) { setVisible(null); return }
    const r = await llamar<{ valor: string }>('revelar', uuid, clave)
    if (r.ok) setVisible(r.valor)
  }
  const texto = protegido ? (visible ?? '••••••••••••') : (mostrar ?? valor ?? '')
  const arrastrable = !protegido || visible !== null
  const alArrastrar = (e: DragEvent) => {
    const v = protegido ? visible : valor
    if (v) { e.dataTransfer.setData('text/plain', v); e.dataTransfer.effectAllowed = 'copy' }
  }
  return (
    <div className="dato">
      <span className="dato__clave" title={rotulo}>{rotulo}</span>
      <span className={`dato__valor seleccionable${protegido && visible === null ? ' dato__valor--oculto' : ''}${mono || protegido ? ' mono' : ''}`}
            draggable={arrastrable} onDragStart={alArrastrar} onDoubleClick={() => void copiar(uuid, clave)}>{texto}</span>
      <span className="dato__acciones">
        {protegido && <button className="boton boton--fantasma boton--sm boton--icono" onClick={() => void alternar()} title={t('tip.mostrar')} aria-label={t('tip.mostrar')}>
          <Icono nombre={visible !== null ? 'ojo_cerrado' : 'ojo'} tamano={14} /></button>}
        <button className="boton boton--fantasma boton--sm boton--icono" onClick={() => void copiar(uuid, clave)} title={t('tip.copiar')} aria-label={t('tip.copiar')}>
          <Icono nombre="copiar" tamano={14} /></button>
      </span>
    </div>
  )
}

const MAX = 64 * 1024 * 1024

function base64De(f: File): Promise<string> {
  return new Promise((resolver, rechazar) => {
    const lector = new FileReader()
    lector.onload = () => resolver(String(lector.result).replace(/^data:[^,]*,/, ''))
    lector.onerror = () => rechazar(lector.error)
    lector.readAsDataURL(f)
  })
}

/** Adjuntos de la entrada: las imágenes en miniatura con visor, el resto en filas. Admite añadir
 *  con diálogo, soltar ficheros encima y pegar con Ctrl+V (fuera de un campo de texto). */
export function Galeria({ uuid, adjuntos, editable, fotos = false, mutar }: {
  uuid: string; adjuntos: { nombre: string; tamano: number }[]; editable: boolean; fotos?: boolean; mutar: Mutar
}) {
  const { t, idioma, avisar } = useApp()
  const [urls, setUrls] = useState<Record<string, string>>({})
  const [visor, setVisor] = useState<number | null>(null)
  const [encima, setEncima] = useState(false)
  const imagenes = adjuntos.filter((a) => esImagen(a.nombre))
  const otros = adjuntos.filter((a) => !esImagen(a.nombre))
  const claveImagenes = imagenes.map((a) => a.nombre).join('|')
  const cache = useRef<{ uuid: string; urls: Record<string, string> }>({ uuid, urls: {} })

  useEffect(() => {
    if (cache.current.uuid !== uuid) cache.current = { uuid, urls: {} }
    // Lo que ya no está en la entrada sale de la caché: si se quita una foto y se añade otra con el
    // mismo nombre, no debe verse la antigua.
    for (const n of Object.keys(cache.current.urls)) if (!imagenes.some((a) => a.nombre === n)) delete cache.current.urls[n]
    let vigente = true
    setUrls({ ...cache.current.urls })
    void (async () => {
      for (const a of imagenes) {
        if (cache.current.urls[a.nombre]) continue
        const r = await llamar<{ url: string }>('imagen', uuid, a.nombre)
        if (!vigente) return
        if (r.ok) { cache.current.urls[a.nombre] = r.url; setUrls({ ...cache.current.urls }) }
      }
    })()
    return () => { vigente = false }
  }, [uuid, claveImagenes]) // eslint-disable-line react-hooks/exhaustive-deps

  const subir = useCallback(async (ficheros: File[]) => {
    let n = 0
    for (const f of ficheros) {
      if (f.size > MAX) { avisar(t('fotos.grande'), true); continue }
      if (fotos && !esImagen(f.name) && !f.type.startsWith('image/')) { avisar(t('fotos.no_imagen'), true); continue }
      const nombre = f.name && f.name !== 'image.png' ? f.name : `captura-${new Date().toISOString().slice(0, 19).replace(/[:T]/g, '-')}.png`
      const r = await mutar('agregar_adjunto_datos', uuid, nombre, await base64De(f))
      if (r) n += 1
    }
    if (n) avisar(t('fotos.anadidas', { n }))
  }, [uuid, fotos, mutar, avisar, t])

  useEffect(() => {
    if (!editable) return
    const pegar = (e: ClipboardEvent) => {
      const activo = document.activeElement?.tagName ?? ''
      if (['INPUT', 'TEXTAREA', 'SELECT'].includes(activo)) return
      const ficheros = [...(e.clipboardData?.files ?? [])]
      if (ficheros.length) { e.preventDefault(); void subir(ficheros) }
    }
    window.addEventListener('paste', pegar)
    return () => window.removeEventListener('paste', pegar)
  }, [editable, subir])

  useEffect(() => {
    if (visor === null) return
    const tecla = (e: KeyboardEvent) => {
      if (e.key === 'Escape') { e.stopPropagation(); setVisor(null) }
      else if (e.key === 'ArrowRight') setVisor((v) => (v === null ? v : (v + 1) % imagenes.length))
      else if (e.key === 'ArrowLeft') setVisor((v) => (v === null ? v : (v - 1 + imagenes.length) % imagenes.length))
    }
    window.addEventListener('keydown', tecla, true)
    return () => window.removeEventListener('keydown', tecla, true)
  }, [visor, imagenes.length])

  const soltar = (e: DragEvent) => {
    e.preventDefault(); setEncima(false)
    if (editable && e.dataTransfer.files.length) void subir([...e.dataTransfer.files])
  }
  const anadir = () => void mutar(fotos ? 'agregar_imagenes' : 'agregar_adjunto', uuid)
  const actual = visor !== null ? imagenes[visor] : null

  return (
    <div className={`galeria${encima ? ' galeria--encima' : ''}`}
         onDragOver={(e) => { if (editable) { e.preventDefault(); setEncima(true) } }} onDragLeave={() => setEncima(false)} onDrop={soltar}>
      {imagenes.length > 0 && (
        <div className="galeria__rejilla">
          {imagenes.map((a, i) => (
            <button key={a.nombre} className="miniatura" onClick={() => setVisor(i)} title={a.nombre}>
              {urls[a.nombre] ? <img src={urls[a.nombre]} alt={a.nombre} draggable={false} /> : <Icono nombre="imagen" tamano={22} />}
            </button>
          ))}
        </div>
      )}
      {fotos && imagenes.length === 0 && <p className="nota" style={{ margin: 0 }}>{t('fotos.ninguna')}</p>}
      {otros.map((a) => (
        <div className="adjunto-fila" key={a.nombre}><span><Icono nombre="clip" tamano={14} /> {a.nombre}</span>
          <span className="tenue mono">{tamano(a.tamano, idioma)}</span>
          <button className="boton boton--fantasma boton--sm" onClick={() => void llamar('guardar_adjunto', uuid, a.nombre)}>{t('entrada.guardar_adjunto')}</button>
          {editable && <button className="boton boton--fantasma boton--sm boton--icono" onClick={() => void mutar('quitar_adjunto', uuid, a.nombre)} title={t('comun.quitar')} aria-label={t('comun.quitar')}><Icono nombre="cerrar" tamano={14} /></button>}
        </div>
      ))}
      {editable && (
        <div className="galeria__pie">
          <button className="boton boton--sm" onClick={anadir}><Icono nombre={fotos ? 'imagen' : 'clip'} tamano={14} />{fotos ? t('fotos.anadir') : t('entrada.anadir_adjunto')}</button>
          <span className="nota">{fotos ? t('fotos.soltar') : t('entrada.soltar')}</span>
        </div>
      )}
      {actual && (
        <div className="visor" onMouseDown={(e) => { if (e.target === e.currentTarget) setVisor(null) }}>
          <div className="visor__barra">
            <span className="visor__nombre">{actual.nombre} · {tamano(actual.tamano, idioma)} · {visor! + 1}/{imagenes.length}</span>
            <button className="boton boton--sm" onClick={() => void llamar('guardar_adjunto', uuid, actual.nombre)}><Icono nombre="disco" tamano={14} />{t('fotos.guardar')}</button>
            {editable && <button className="boton boton--sm boton--peligro" onClick={() => { void mutar('quitar_adjunto', uuid, actual.nombre); setVisor(null) }}><Icono nombre="papelera" tamano={14} />{t('fotos.quitar')}</button>}
            <button className="boton boton--fantasma boton--icono" onClick={() => setVisor(null)} aria-label={t('comun.cerrar')}><Icono nombre="cerrar" /></button>
          </div>
          <div className="visor__lienzo">
            {imagenes.length > 1 && <button className="visor__paso" onClick={() => setVisor((visor! - 1 + imagenes.length) % imagenes.length)} aria-label={t('fotos.anterior')}><Icono nombre="izquierda" tamano={28} /></button>}
            {urls[actual.nombre] ? <img src={urls[actual.nombre]} alt={actual.nombre} draggable={false} /> : <span className="nota">{t('comun.cargando')}</span>}
            {imagenes.length > 1 && <button className="visor__paso" onClick={() => setVisor((visor! + 1) % imagenes.length)} aria-label={t('fotos.siguiente')}><Icono nombre="derecha" tamano={28} /></button>}
          </div>
        </div>
      )}
    </div>
  )
}

/** Historial de versiones de la entrada, con restauración. */
export function Historial({ uuid, historial, editable, mutar }: {
  uuid: string; historial: { indice: number; titulo: string; modificada: string | null }[]; editable: boolean; mutar: Mutar
}) {
  const { t, idioma } = useApp()
  if (historial.length === 0) return <span className="nota" style={{ padding: '0 10px' }}>{t('entrada.sin_historial')}</span>
  return <>{[...historial].reverse().map((h) => (
    <div className="historial-fila" key={h.indice}><span>{h.titulo || t('entrada.sin_titulo')}</span>
      <span className="tenue">{fecha(h.modificada, idioma, true)}</span>
      {editable && <button className="boton boton--fantasma boton--sm" onClick={() => void mutar('restaurar_historial', uuid, h.indice)}>{t('entrada.restaurar')}</button>}</div>
  ))}</>
}

/** Código TOTP con su cuenta atrás; se refresca cada segundo mientras está a la vista. */
export function FilaTotp({ uuid, activo }: { uuid: string; activo: boolean }) {
  const { t, copiar } = useApp()
  const [totp, setTotp] = useState<{ codigo: string; restante: number; periodo: number } | null>(null)
  useEffect(() => {
    if (!activo) { setTotp(null); return }
    let vigente = true
    const leer = () => void llamar<{ totp: { codigo: string; restante: number; periodo: number } | null }>('totp', uuid)
      .then((r) => { if (vigente && r.ok) setTotp(r.totp) })
    leer()
    const reloj = window.setInterval(leer, 1000)
    return () => { vigente = false; window.clearInterval(reloj) }
  }, [activo, uuid])
  if (!totp) return null
  return (
    <div className="dato">
      <span className="dato__clave">{t('entrada.totp')}</span>
      <span className="totp" onDoubleClick={() => void copiar(uuid, '__totp__')}><span className="totp__codigo">{totp.codigo.replace(/^(\d{3})(\d{3})$/, '$1 $2')}</span>
        <span className="totp__barra"><i style={{ width: `${(totp.restante / totp.periodo) * 100}%` }} /></span>
        <span className="tenue mono">{totp.restante}s</span></span>
      <span className="dato__acciones"><button className="boton boton--fantasma boton--sm boton--icono" onClick={() => void copiar(uuid, '__totp__')} title={t('tip.copiar')} aria-label={t('tip.copiar')}><Icono nombre="copiar" tamano={14} /></button></span>
    </div>
  )
}

/** Campos propios de la entrada (y el TOTP): nombre, valor y si va protegido. */
export function EditorCampos({ campos, alCambiar, ver }: { campos: { clave: string; valor: string | null; protegido: boolean }[]; alCambiar: (c: { clave: string; valor: string | null; protegido: boolean }[]) => void; ver: boolean }) {
  const { t } = useApp()
  const cambiarEn = (i: number, cambio: Partial<{ clave: string; valor: string; protegido: boolean }>) => alCambiar(campos.map((x, j) => (j === i ? { ...x, ...cambio } : x)))
  return (
    <div className="campo"><span className="campo__rotulo">{t('entrada.personalizados')}</span>
      {campos.map((c, i) => (
        <div className="personalizado" key={i}>
          <input className="control" value={c.clave} placeholder={t('entrada.nombre_campo')} onChange={(e) => cambiarEn(i, { clave: e.target.value })} />
          <input className={`control${c.protegido ? ' mono' : ''}`} type={c.protegido && !ver ? 'password' : 'text'} value={c.valor ?? ''} spellCheck={false}
                 placeholder={c.clave === 'otp' ? t('entrada.totp_secreto') : t('entrada.valor')} onChange={(e) => cambiarEn(i, { valor: e.target.value })} />
          <label className="casilla" title={t('entrada.protegido')}><input type="checkbox" checked={c.protegido}
                 onChange={(e) => cambiarEn(i, { protegido: e.target.checked })} /><Icono nombre="candado" tamano={14} /></label>
          <button className="boton boton--fantasma boton--icono" onClick={() => alCambiar(campos.filter((_, j) => j !== i))} aria-label={t('comun.quitar')} title={t('comun.quitar')}><Icono nombre="cerrar" tamano={14} /></button>
        </div>
      ))}
      <div className="grupo-control">
        <button className="boton boton--sm" onClick={() => alCambiar([...campos, { clave: '', valor: '', protegido: false }])}><Icono nombre="mas" tamano={14} />{t('entrada.anadir_campo')}</button>
        {!campos.some((c) => c.clave === 'otp') && <button className="boton boton--sm" onClick={() => alCambiar([...campos, { clave: 'otp', valor: '', protegido: true }])}><Icono nombre="reloj" tamano={14} />{t('entrada.totp')}</button>}
      </div>
    </div>
  )
}

/** Teclas comunes de los editores. Esc dentro de un diálogo abierto (generador) no cierra el editor. */
export function teclasEditor(e: React.KeyboardEvent, guardar: () => void, cancelar: () => void) {
  if ((e.target as HTMLElement).closest('.velo')) return
  const ctrl = e.ctrlKey || e.metaKey
  if (e.key === 'Escape') { e.preventDefault(); e.stopPropagation(); cancelar() }
  else if (ctrl && (e.key === 'Enter' || e.key.toLowerCase() === 's')) { e.preventDefault(); e.stopPropagation(); guardar() }
}
