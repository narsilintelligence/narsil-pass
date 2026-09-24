import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import escudo64 from './marca/escudo-64.png'
import { llamar, type Campo, type Detalle, type Filtros, type Grupo, type Info, type RefSalud, type Resumen, type Salud, type Seccion } from './api'
import { useApp } from './contexto'
import { Icono } from './iconos'
import { fecha, type Clave } from './i18n'
import { Confirmar, Dialogo, PedirTexto } from './Dialogos'
import { Generador } from './Generador'
import { Ajustes } from './Ajustes'
import { Dato, EditorCampos, FilaTotp, Galeria, Historial, teclasEditor, type Mutar } from './Piezas'
import { ChipEstado, EditorIdentidad, VistaIdentidad } from './Identidad'
import { Atajos, PanelSalud, type PestanaSalud } from './Salud'
import { ESTADOS, ESTANDAR, OCULTOS, normalizarOtp } from './ficha'
import { agruparPorSeccion, carpetaVisible, mapaUbicacion, type Bloque } from './listado'

type Vista = Seccion | 'todo'
const VISTAS: { id: Vista; icono: string }[] = [
  { id: 'todo', icono: 'capas' }, { id: 'interno', icono: 'edificio' }, { id: 'externo', icono: 'globo' }, { id: 'identidades', icono: 'identidad' },
]
const ICONO_BLOQUE: Record<Bloque, string> = { interno: 'edificio', externo: 'globo', identidades: 'identidad', sin_seccion: 'carpeta' }
const SECCIONES: Seccion[] = ['interno', 'externo', 'identidades']
const ALERTAS = ['cualquiera', 'repetida', 'debil', 'renovar', 'caducada', 'por_caducar'] as const
const REVISION_MS = 30 * 60 * 1000   // aviso periódico de caducidad y renovación

type Modo = { tipo: 'ver' } | { tipo: 'editar' } | { tipo: 'nueva'; identidad: boolean }
type DialogoPrincipal = null | 'generador' | 'ajustes' | 'cambio_externo' | 'atajos'
  | { tipo: 'salud'; pestana: PestanaSalud }
  | { tipo: 'grupo'; padre?: string; uuid?: string; nombre?: string }
  | { tipo: 'confirmar'; titulo: string; texto: string; accion: () => void }
  | { tipo: 'mover'; uuid: string }
  | { tipo: 'seccion'; grupo: Grupo }

export function Principal({ infoInicial, alBloquear }: { infoInicial: Info; alBloquear: () => void }) {
  const { t, idioma, error, copiar } = useApp()
  const [info, setInfo] = useState(infoInicial)
  const [arbol, setArbol] = useState<Grupo | null>(null)
  const [vista, setVista] = useState<Vista>('todo')
  const [grupo, setGrupo] = useState<string>(infoInicial.raiz)
  const [texto, setTexto] = useState('')
  const [filtros, setFiltros] = useState<Filtros>({})
  const [verFiltros, setVerFiltros] = useState(false)
  const [facetas, setFacetas] = useState<{ servicios: string[]; usuarios: string[] }>({ servicios: [], usuarios: [] })
  const [lista, setLista] = useState<Resumen[]>([])
  const [sel, setSel] = useState<string | null>(null)
  const [tipoSel, setTipoSel] = useState<'identidad' | 'entrada' | null>(null)
  const [modo, setModo] = useState<Modo>({ tipo: 'ver' })
  const [dialogo, setDialogo] = useState<DialogoPrincipal>(null)
  const [menuNueva, setMenuNueva] = useState(false)
  const [contexto, setContexto] = useState<{ x: number; y: number; e: Resumen } | null>(null)
  const [version, setVersion] = useState(0)
  const [salud, setSalud] = useState<Salud | null>(null)
  const [descartado, setDescartado] = useState('')
  const buscador = useRef<HTMLInputElement>(null)

  const recargar = useCallback(() => setVersion((v) => v + 1), [])
  const ambito = vista === 'todo' ? null : info.secciones[vista]
  const nFiltros = Object.values(filtros).filter(Boolean).length
  const q = texto.trim()   // solo espacios no es una búsqueda
  const buscando = !!q || nFiltros > 0
  // Con su contenido anidado se listan la base entera, la papelera y la raíz de cada sección; una
  // carpeta cualquiera muestra solo sus entradas, como en KeePassXC.
  const recursivo = !buscando && (grupo === info.raiz || grupo === info.papelera || SECCIONES.some((s) => info.secciones[s] === grupo))

  useEffect(() => {
    let vigente = true
    void (async () => {
      const [g, i, l, f, s] = await Promise.all([
        llamar<{ arbol: Grupo }>('grupos'), llamar<{ info: Info }>('info'),
        // Sin búsqueda: el grupo elegido con todo lo que cuelga de él (en «Toda la base», la base entera
        // menos la papelera). La búsqueda por texto es siempre en toda la base; los filtros solos se
        // quedan en la vista actual.
        llamar<{ lista: Resumen[] }>('entradas', buscando ? null : grupo, q, buscando ? { ...filtros, ambito: q ? null : ambito } : null, recursivo),
        llamar<{ servicios: string[]; usuarios: string[] }>('facetas', q ? null : ambito), llamar<{ salud: Salud }>('salud'),
      ])
      if (!vigente) return
      if (g.ok) setArbol(g.arbol)
      if (i.ok) setInfo(i.info)
      if (l.ok) setLista(l.lista); else error(l.error)
      if (f.ok) setFacetas({ servicios: f.servicios, usuarios: f.usuarios })
      if (s.ok) setSalud(s.salud)
    })()
    return () => { vigente = false }
  }, [grupo, q, filtros, ambito, buscando, recursivo, version, error])

  // Aviso periódico: la salud se vuelve a calcular cada media hora aunque no se toque nada.
  useEffect(() => {
    const reloj = window.setInterval(() => void llamar<{ salud: Salud }>('salud').then((r) => { if (r.ok) setSalud(r.salud) }), REVISION_MS)
    return () => window.clearInterval(reloj)
  }, [])

  // Si una sección deja de existir (su grupo se borró), se vuelve a la base completa.
  useEffect(() => {
    if (vista !== 'todo' && !info.secciones[vista]) { setVista('todo'); setGrupo(info.raiz) }
  }, [info, vista])

  // Soltar un fichero fuera de una zona de adjuntos no debe hacer que la ventana lo abra.
  useEffect(() => {
    const no = (e: DragEvent) => { if (e.dataTransfer?.types.includes('Files')) e.preventDefault() }
    window.addEventListener('dragover', no)
    window.addEventListener('drop', no)
    return () => { window.removeEventListener('dragover', no); window.removeEventListener('drop', no) }
  }, [])

  /** Toda operación que cambia la base pasa por aquí: errores, aviso de cambio externo y recarga. */
  const mutar: Mutar = useCallback(async (metodo: string, ...args: unknown[]) => {
    const r = await llamar<{ aviso?: string; uuid?: string }>(metodo, ...args)
    if (!r.ok) { error(r.error); return null }
    if (r.aviso === 'cambio_externo') setDialogo('cambio_externo')
    else if (r.aviso) error(r.aviso)
    recargar()
    return r as Record<string, unknown>
  }, [error, recargar])

  const guardar = useCallback(async (forzar = false) => {
    const r = await llamar<{ info: Info }>('guardar', forzar)
    if (r.ok) { setInfo(r.info); setDialogo(null) }
    else if (r.error === 'cambio_externo') setDialogo('cambio_externo')
    else error(r.error)
  }, [error])

  const guardarComo = useCallback(async () => {
    const r = await llamar<{ info?: Info; cancelado?: boolean }>('guardar_como')
    if (r.ok && r.info) { setInfo(r.info); setDialogo(null) } else if (!r.ok) error(r.error)
  }, [error])

  const cambiarVista = useCallback((v: Vista, g?: string) => {
    const destino = g ?? (v === 'todo' ? info.raiz : info.secciones[v])
    if (!destino) return
    setVista(v); setGrupo(destino); setTexto(''); setFiltros({}); setSel(null); setModo({ tipo: 'ver' })
  }, [info])

  const vistaDe = useCallback((g: string): Vista => {
    for (const s of SECCIONES) {
      const u = info.secciones[s]
      if (u && (u === g || buscarGrupo(buscarGrupo(arbol, u), g))) return s
    }
    return 'todo'
  }, [info, arbol])

  /** ¿La vista del grupo g muestra una entrada que vive en el grupo h? */
  const seVe = (g: string, h: string) => g === h || ((g === info.raiz || SECCIONES.some((s) => info.secciones[s] === g))
    && !!buscarGrupo(buscarGrupo(arbol, g), h) && !ubicacion.get(h)?.papelera)

  const irA = useCallback((r: RefSalud) => {
    setVista(vistaDe(r.grupo)); setGrupo(r.grupo); setTexto(''); setFiltros({}); setSel(r.uuid); setModo({ tipo: 'ver' }); setDialogo(null)
  }, [vistaDe])

  const organizar = useCallback(async () => {
    const r = await mutar('preparar_secciones')
    const s = r?.secciones as Info['secciones'] | undefined
    if (s?.interno) { setInfo((i) => ({ ...i, secciones: s })); setVista('interno'); setGrupo(s.interno); setSel(null) }
  }, [mutar])

  const grupoActual = useMemo(() => buscarGrupo(arbol, grupo), [arbol, grupo])
  const ubicacion = useMemo(() => mapaUbicacion(arbol, info.secciones), [arbol, info.secciones])
  // La búsqueda y los filtros nunca devuelven nada de la papelera: buscando, no se está «en la papelera».
  const enPapelera = !buscando && (ubicacion.get(grupo)?.papelera ?? !!grupoActual?.papelera)
  const seleccion = lista.find((e) => e.uuid === sel) ?? null
  // En «Toda la base» y en cualquier búsqueda, los resultados van en bloques por sección.
  const agrupado = !enPapelera && (vista === 'todo' || !!q)
  const bloques = useMemo(() => (agrupado ? agruparPorSeccion(lista, ubicacion) : [{ id: null as Bloque | null, filas: lista }]),
    [agrupado, lista, ubicacion])
  const listaVisible = useMemo(() => bloques.flatMap((b) => b.filas), [bloques])
  const cerrarDialogo = useCallback(() => setDialogo(null), [])

  const nueva = useCallback((identidad: boolean) => { setMenuNueva(false); setSel(null); setModo({ tipo: 'nueva', identidad }) }, [])
  const eliminar = useCallback((e: Resumen) => {
    if (enPapelera) setDialogo({ tipo: 'confirmar', titulo: t('comun.eliminar'), texto: t('principal.confirmar_eliminar_def', { t: e.titulo || t('entrada.sin_titulo') }),
      accion: () => { void mutar('eliminar_entrada', e.uuid); setSel(null) } })
    else { void mutar('eliminar_entrada', e.uuid); setSel(null) }
  }, [enPapelera, mutar, t])

  // Teclado: atajos de KeePassXC y navegación por la lista. Los editores y diálogos tienen los suyos.
  useEffect(() => {
    const tecla = (e: KeyboardEvent) => {
      if (dialogo || contexto) return
      const enCampo = ['INPUT', 'TEXTAREA', 'SELECT'].includes(document.activeElement?.tagName ?? '')
      if (e.key === 'F1') { e.preventDefault(); setDialogo('atajos'); return }
      const ctrl = e.ctrlKey || e.metaKey
      if (!ctrl) {
        if (enCampo || modo.tipo !== 'ver' || e.altKey || e.shiftKey) return
        const enBoton = ['BUTTON', 'A'].includes(document.activeElement?.tagName ?? '')
        if ((e.key === 'ArrowDown' || e.key === 'ArrowUp') && listaVisible.length) {
          e.preventDefault()
          const i = listaVisible.findIndex((x) => x.uuid === sel)
          const j = i < 0 ? 0 : Math.max(0, Math.min(listaVisible.length - 1, i + (e.key === 'ArrowDown' ? 1 : -1)))
          setSel(listaVisible[j].uuid)
        } else if (e.key === 'Enter' && seleccion && !enPapelera && !enBoton) { e.preventDefault(); setModo({ tipo: 'editar' }) }
        else if (e.key === 'Delete' && seleccion && !enBoton) { e.preventDefault(); eliminar(seleccion) }
        return
      }
      const k = e.key.toLowerCase()
      if (k === 'f') { e.preventDefault(); buscador.current?.focus(); buscador.current?.select() }
      else if (k === 'l') { e.preventDefault(); alBloquear() }
      else if (k === 's') { e.preventDefault(); void guardar() }
      else if (['1', '2', '3', '4'].includes(k) && modo.tipo === 'ver') { e.preventDefault(); cambiarVista(VISTAS[Number(k) - 1].id) }
      else if (enCampo || modo.tipo !== 'ver') return
      else if (k === 'n' && !enPapelera) { e.preventDefault(); nueva(vista === 'identidades') }
      else if (!sel) return
      else if (k === 'b') { e.preventDefault(); void copiar(sel, 'UserName') }
      else if (k === 'c' && !window.getSelection()?.toString()) { e.preventDefault(); void copiar(sel, 'Password') }
      else if (k === 'u') { e.preventDefault(); void copiar(sel, 'URL') }
      else if (k === 't' && seleccion?.totp) { e.preventDefault(); void copiar(sel, '__totp__') }
      else if (k === 'e' && !enPapelera) { e.preventDefault(); setModo({ tipo: 'editar' }) }
      else if (k === 'd' && !enPapelera) { e.preventDefault(); void mutar('duplicar_entrada', sel) }
    }
    window.addEventListener('keydown', tecla)
    return () => window.removeEventListener('keydown', tecla)
  }, [dialogo, contexto, modo, listaVisible, sel, seleccion, enPapelera, vista, alBloquear, guardar, copiar, cambiarVista, nueva, eliminar, mutar])

  useEffect(() => {
    if (sel) document.querySelector(`[data-uuid="${CSS.escape(sel)}"]`)?.scrollIntoView({ block: 'nearest' })
  }, [sel])

  useEffect(() => {
    if (!contexto) return
    const cerrar = () => setContexto(null)
    const tecla = (e: KeyboardEvent) => { if (e.key === 'Escape') cerrar() }
    window.addEventListener('mousedown', cerrar)
    window.addEventListener('keydown', tecla)
    window.addEventListener('blur', cerrar)
    return () => { window.removeEventListener('mousedown', cerrar); window.removeEventListener('keydown', tecla); window.removeEventListener('blur', cerrar) }
  }, [contexto])

  const raizVista = vista === 'todo' || !ambito ? arbol : buscarGrupo(arbol, ambito)
  const sinOrganizar = SECCIONES.some((s) => !info.secciones[s])
  const aviso = salud ? { c: salud.caducadas.length, p: salud.por_caducar.length, r: salud.renovar.length } : null
  const firmaAviso = aviso ? `${aviso.c}-${aviso.p}-${aviso.r}` : ''
  const verAviso = !!aviso && aviso.c + aviso.p + aviso.r > 0 && firmaAviso !== descartado
  const titulo = buscando ? (lista.length === 1 ? t('principal.resultado_uno') : t('principal.resultados', { n: lista.length }))
    : vista === 'todo' && grupo === info.raiz ? t('seccion.todo') : grupoActual?.nombre ?? ''
  // Una identidad va siempre a su sección; una entrada creada desde la raíz de «Toda la base» va a
  // Servicios internos, para que no quede suelta fuera de las secciones.
  const destinoNueva = (identidad: boolean) => (identidad
    ? (vista !== 'identidades' ? info.secciones.identidades ?? grupo : grupo)
    : (grupo === info.raiz ? info.secciones.interno ?? grupo : grupo))

  const alGuardarNueva = (identidad: boolean) => async (campos: Campo[], etiquetas: string[], expira: string) => {
    const destino = destinoNueva(identidad)
    const r = await mutar('crear_entrada', destino, campos, etiquetas, expira || null)
    if (r?.uuid) {
      if (destino !== grupo) { setVista(vistaDe(destino)); setGrupo(destino); setTexto(''); setFiltros({}) }
      setSel(r.uuid as string); setModo({ tipo: 'ver' })
    }
  }
  const alGuardarEdicion = async (campos: Campo[], etiquetas: string[], expira: string) => {
    if (sel && await mutar('editar_entrada', sel, campos, etiquetas, expira)) setModo({ tipo: 'ver' })
  }

  return (
    <div className="app">
      <header className="cabecera">
        <div className="cabecera__marca"><img src={escudo64} alt="" />
          <div><div className="n">NARSIL</div><div className="p">{t('marca.producto')}</div></div></div>
        <div className="cabecera__base">
          <strong title={info.ruta ?? ''}>{info.nombre || '—'}</strong>
          <span className="chip chip--formato" data-tip={`${info.cifrado} · ${info.kdf}`}>{info.formato}</span>
        </div>
        <div className="buscador">
          <Icono nombre="lupa" />
          <input ref={buscador} className="control" value={texto} spellCheck={false}
                 placeholder={t('principal.buscar')}
                 onChange={(e) => { setTexto(e.target.value); setSel(null); setModo({ tipo: 'ver' }) }}
                 onKeyDown={(e) => {
                   if (e.key === 'Escape') {
                     const elegida = lista.find((x) => x.uuid === sel)
                     if (elegida && !seVe(grupo, elegida.grupo)) { setVista(vistaDe(elegida.grupo)); setGrupo(elegida.grupo) }
                     setTexto(''); (e.target as HTMLInputElement).blur()
                   }
                   else if (e.key === 'ArrowDown' && listaVisible.length) { e.preventDefault(); setSel(listaVisible[0].uuid); (e.target as HTMLInputElement).blur() }
                 }} />
        </div>
        <span className={`estado-guardado${info.cambios ? ' estado-guardado--pendiente' : ''}`}>
          {info.cambios ? t('principal.sin_guardar') : t('principal.guardado')}</span>
        {info.cambios && <button className="boton boton--sm" onClick={() => void guardar()} data-tip={t('tip.guardar')}><Icono nombre="disco" />{t('comun.guardar')}</button>}
        <div className="envoltura-menu">
          <button className="boton boton--primario boton--sm" onClick={() => setMenuNueva(!menuNueva)} disabled={enPapelera} data-tip={t('tip.nueva_entrada')}>
            <Icono nombre={vista === 'identidades' ? 'identidad' : 'mas'} />{vista === 'identidades' ? t('principal.nueva_identidad') : t('principal.nueva_entrada')}<Icono nombre="abajo" tamano={12} /></button>
          {menuNueva && (
            <div className="menu" onMouseLeave={() => setMenuNueva(false)}>
              <button onClick={() => nueva(false)}><Icono nombre="llave" />{t('principal.nueva_entrada')}</button>
              <button onClick={() => nueva(true)}><Icono nombre="identidad" />{t('principal.nueva_identidad')}</button>
            </div>
          )}
        </div>
        <button className="boton boton--fantasma boton--icono con-insignia" onClick={() => setDialogo({ tipo: 'salud', pestana: 'repetidas' })} data-tip={t('tip.salud')} aria-label={t('salud.boton')}>
          <Icono nombre="escudo" />{salud && salud.total > 0 && <span className="insignia">{salud.total > 99 ? '99+' : salud.total}</span>}</button>
        <button className="boton boton--fantasma boton--icono" onClick={() => setDialogo('generador')} data-tip={t('tip.generador')} aria-label={t('principal.generador')}><Icono nombre="dado" /></button>
        <button className="boton boton--fantasma boton--icono" onClick={() => setDialogo('atajos')} data-tip={t('tip.atajos')} aria-label={t('atajos.titulo')}><Icono nombre="teclado" /></button>
        <button className="boton boton--fantasma boton--icono" onClick={() => setDialogo('ajustes')} data-tip={t('tip.ajustes')} data-tip-lado="izquierda" aria-label={t('principal.ajustes')}><Icono nombre="ajustes" /></button>
        <button className="boton boton--fantasma boton--icono" onClick={alBloquear} data-tip={t('tip.bloquear')} data-tip-lado="izquierda" aria-label={t('principal.bloquear')}><Icono nombre="candado" /></button>
      </header>

      <div className="franja">
        {verAviso && aviso && (
          <div className="banda" role="status">
            <Icono nombre="aviso" />
            <strong>{t('aviso.titulo')}</strong>
            <span>{[aviso.c && t('aviso.caducadas', { n: aviso.c }), aviso.p && t('aviso.por_caducar', { n: aviso.p }), aviso.r && t('aviso.renovar', { n: aviso.r })].filter(Boolean).join(' · ')}</span>
            <button className="boton boton--sm" onClick={() => setDialogo({ tipo: 'salud', pestana: aviso.c + aviso.p > 0 ? 'caducidad' : 'renovar' })}>{t('aviso.revisar')}</button>
            <button className="boton boton--fantasma boton--sm boton--icono" onClick={() => setDescartado(firmaAviso)} title={t('aviso.descartar')} aria-label={t('aviso.descartar')}><Icono nombre="cerrar" tamano={14} /></button>
          </div>
        )}
      </div>

      <div className="cuerpo">
        <nav className="columna columna--grupos">
          <div className="vistas" role="group" aria-label={t('tip.secciones')}>
            {VISTAS.map((v) => {
              const u = v.id === 'todo' ? info.raiz : info.secciones[v.id]
              return (
                <button key={v.id} className={`vista${vista === v.id ? ' vista--activa' : ''}`} disabled={!u} onClick={() => cambiarVista(v.id)}>
                  <Icono nombre={v.icono} /><span className="vista__nombre">{t(`seccion.${v.id}` as Clave)}</span>
                  <span className="nodo__cuenta">{u ? total(buscarGrupo(arbol, u)) : ''}</span>
                </button>
              )
            })}
            {info.papelera && (
              <button className={`vista vista--menor${grupo === info.papelera ? ' vista--activa' : ''}`} onClick={() => cambiarVista('todo', info.papelera!)}>
                <Icono nombre="papelera" /><span className="vista__nombre">{buscarGrupo(arbol, info.papelera)?.nombre ?? ''}</span>
                <span className="nodo__cuenta">{total(buscarGrupo(arbol, info.papelera), true) || ''}</span>
              </button>
            )}
          </div>
          {sinOrganizar && (
            <div className="organizar">
              <p>{t('seccion.sin_organizar')}</p>
              <span className="nota">{t('seccion.organizar_ayuda')}</span>
              <button className="boton boton--sm boton--primario" onClick={() => void organizar()}><Icono nombre="capas" tamano={14} />{t('seccion.organizar')}</button>
            </div>
          )}
          <div className="separador" />
          {raizVista && <ArbolGrupos nodo={raizVista} activo={buscando ? '' : grupo} raiz ocultarPapelera={vista !== 'todo'}
            alElegir={(u) => { setGrupo(u); setTexto(''); setFiltros({}); setSel(null); setModo({ tipo: 'ver' }) }}
            alNuevo={(padre) => setDialogo({ tipo: 'grupo', padre })}
            alRenombrar={(g) => setDialogo({ tipo: 'grupo', uuid: g.uuid, nombre: g.nombre })}
            alSeccion={vista === 'todo' ? (g) => setDialogo({ tipo: 'seccion', grupo: g }) : undefined}
            alEliminar={(g) => setDialogo({ tipo: 'confirmar', titulo: t('comun.eliminar'), texto: t('principal.confirmar_grupo', { t: g.nombre }),
              accion: () => { void mutar('eliminar_grupo', g.uuid); if (grupo === g.uuid) setGrupo(raizVista.uuid) } })}
            alVaciar={() => setDialogo({ tipo: 'confirmar', titulo: t('principal.vaciar_papelera'), texto: t('principal.confirmar_vaciar'),
              accion: () => void mutar('vaciar_papelera') })} />}
        </nav>

        <section className="columna columna--lista">
          <div className="lista__barra">
            <span className="lista__titulo">{titulo}</span>
            <button className={`boton boton--fantasma boton--sm${nFiltros ? ' boton--marcado' : ''}`} onClick={() => setVerFiltros(!verFiltros)}
                    title={t('tip.filtros')} aria-label={t('filtro.titulo')} aria-expanded={verFiltros}>
              <Icono nombre="filtro" tamano={14} />{nFiltros > 0 && nFiltros}</button>
          </div>
          {verFiltros && (
            <div className="filtros">
              <Selector rotulo={t('filtro.servicio')} valor={filtros.servicio ?? ''} opciones={facetas.servicios.map((s) => [s, s])}
                        alCambiar={(v) => setFiltros({ ...filtros, servicio: v })} />
              <Selector rotulo={t('filtro.usuario')} valor={filtros.usuario ?? ''} opciones={facetas.usuarios.map((s) => [s, s])}
                        alCambiar={(v) => setFiltros({ ...filtros, usuario: v })} />
              <Selector rotulo={t('filtro.alerta')} valor={filtros.alerta ?? ''}
                        opciones={ALERTAS.map((a) => [a, a === 'cualquiera' ? t('filtro.con_avisos') : t(`alerta.${a}` as Clave)])}
                        alCambiar={(v) => setFiltros({ ...filtros, alerta: v })} />
              {vista === 'identidades' ? (
                <Selector rotulo={t('filtro.estado')} valor={filtros.estado ?? ''} opciones={ESTADOS.map((s) => [s, t(`estado.${s}` as Clave)])}
                          alCambiar={(v) => setFiltros({ ...filtros, estado: v })} />
              ) : (
                <Selector rotulo={t('filtro.tipo')} valor={filtros.tipo ?? ''}
                          opciones={[['entrada', t('filtro.solo_entradas')], ['identidad', t('filtro.solo_identidades')]]}
                          alCambiar={(v) => setFiltros({ ...filtros, tipo: v })} />
              )}
              {nFiltros > 0 && <button className="enlace filtros__limpiar" onClick={() => setFiltros({})}>{t('filtro.limpiar')}</button>}
            </div>
          )}
          {lista.length === 0 ? (
            <div className="vacio">{buscando ? t('principal.vacio_busqueda') : t('principal.vacio_grupo')}
              {!q && nFiltros > 0 && vista !== 'todo' && (
                <div style={{ marginTop: 12 }}><button className="enlace" onClick={() => { setVista('todo'); setGrupo(info.raiz); setSel(null) }}>{t('principal.filtrar_todo')}</button></div>
              )}</div>
          ) : (
            <ul className={`lista${agrupado ? ' lista--agrupada' : ''}`} role="listbox">
              {bloques.map((b) => [
                b.id && (
                  <li key={`bloque-${b.id}`} role="presentation" className={`bloque-lista bloque-lista--${b.id}`}>
                    {b.id !== 'sin_seccion' && info.secciones[b.id] ? (
                      <button className="bloque-lista__boton" onClick={() => cambiarVista(b.id as Seccion)} title={t('tip.ir_seccion')}>
                        <Icono nombre={ICONO_BLOQUE[b.id]} tamano={15} /><span>{t(`seccion.${b.id}` as Clave)}</span></button>
                    ) : <span className="bloque-lista__boton"><Icono nombre={ICONO_BLOQUE[b.id]} tamano={15} /><span>{t('seccion.sin_seccion')}</span></span>}
                    <span className="nodo__cuenta">{b.filas.length}</span>
                  </li>
                ),
                ...b.filas.map((e) => {
                const graves = e.alertas.filter((a) => a !== 'renovar' && a !== 'por_caducar')
                const carpeta = carpetaVisible(e, ubicacion, info.raiz)
                return (
                  <li key={e.uuid} data-uuid={e.uuid} role="option" aria-selected={sel === e.uuid} className={`fila${sel === e.uuid ? ' fila--activa' : ''}`}
                      onClick={() => { setSel(e.uuid); setModo({ tipo: 'ver' }) }}
                      onDoubleClick={() => void copiar(e.uuid, 'Password')}
                      onContextMenu={(ev) => { ev.preventDefault(); setSel(e.uuid); setModo({ tipo: 'ver' }); setContexto({ x: ev.clientX, y: ev.clientY, e }) }}>
                    <span className={`fila__icono${e.tipo === 'identidad' ? ' fila__icono--identidad' : ''}`}><Icono nombre={e.tipo === 'identidad' ? 'identidad' : 'llave'} /></span>
                    <span className="fila__texto">
                      <div className="fila__titulo">{e.tipo === 'identidad' && e.estado && <i className={`punto punto--${e.estado}`} />}{e.titulo || t('entrada.sin_titulo')}</div>
                      <div className="fila__sub">{carpeta && <span className="fila__carpeta"><Icono nombre="carpeta" tamano={12} />{carpeta}</span>}
                        {e.usuario || e.url || fecha(e.modificada, idioma)}</div>
                    </span>
                    <span className="fila__marcas">
                      {e.alertas.length > 0 && <span className={graves.length ? 'marca--peligro' : 'marca--aviso'} title={e.alertas.map((a) => t(`alerta.${a}` as Clave)).join(' · ')}><Icono nombre="aviso" tamano={14} /></span>}
                      {e.totp && <Icono nombre="reloj" tamano={14} />}
                      {e.tipo === 'identidad' && e.servicios > 0 && <span className="fila__numero" title={t('identidad.pestana_servicios')}><Icono nombre="globo" tamano={13} />{e.servicios}</span>}
                      {e.fotos > 0 ? <span className="fila__numero" title={t('identidad.pestana_fotos')}><Icono nombre="imagen" tamano={13} />{e.fotos}</span>
                        : e.adjuntos > 0 && <Icono nombre="clip" tamano={14} />}
                    </span>
                  </li>
                )
                }),
              ])}
            </ul>
          )}
        </section>

        <section className="columna columna--detalle">
          {modo.tipo === 'nueva' ? (
            modo.identidad
              ? <EditorIdentidad alCerrar={() => setModo({ tipo: 'ver' })} alGuardar={alGuardarNueva(true)} />
              : <Editor alCerrar={() => setModo({ tipo: 'ver' })} alGuardar={alGuardarNueva(false)} />
          ) : modo.tipo === 'editar' && sel ? (
            (seleccion?.tipo ?? tipoSel) === 'identidad'
              ? <EditorIdentidad uuid={sel} alCerrar={() => setModo({ tipo: 'ver' })} alGuardar={alGuardarEdicion} />
              : <Editor uuid={sel} alCerrar={() => setModo({ tipo: 'ver' })} alGuardar={alGuardarEdicion} />
          ) : sel ? (
            <Seleccion uuid={sel} version={version} mutar={mutar} alTipo={setTipoSel}
                       alEditar={() => setModo({ tipo: 'editar' })}
                       alMover={() => setDialogo({ tipo: 'mover', uuid: sel })}
                       alEliminado={() => setSel(null)} />
          ) : (
            <div className="vacio" style={{ paddingTop: 120 }}>{t('principal.selecciona')}</div>
          )}
        </section>
      </div>

      {contexto && (
        <div className="menu menu--contexto" style={{ left: Math.min(contexto.x, window.innerWidth - 250), top: Math.min(contexto.y, window.innerHeight - 330) }}
             onMouseDown={(e) => e.stopPropagation()}>
          {([['usuario', 'UserName', 'menu.copiar_usuario', 'Ctrl+B'], ['llave', 'Password', 'menu.copiar_contrasena', 'Ctrl+C'],
            ['globo', 'URL', 'menu.copiar_url', 'Ctrl+U']] as const).map(([icono, clave, texto, tecla]) => (
            <button key={clave} onClick={() => { void copiar(contexto.e.uuid, clave); setContexto(null) }}><Icono nombre={icono} />{t(texto)}<kbd>{tecla}</kbd></button>
          ))}
          {contexto.e.totp && <button onClick={() => { void copiar(contexto.e.uuid, '__totp__'); setContexto(null) }}><Icono nombre="reloj" />{t('menu.copiar_totp')}<kbd>Ctrl+T</kbd></button>}
          {!enPapelera && <>
            <div className="menu__separador" />
            <button onClick={() => { setModo({ tipo: 'editar' }); setContexto(null) }}><Icono nombre="lapiz" />{t('comun.editar')}<kbd>Ctrl+E</kbd></button>
            <button onClick={() => { void mutar('duplicar_entrada', contexto.e.uuid); setContexto(null) }}><Icono nombre="duplicar" />{t('entrada.duplicar')}<kbd>Ctrl+D</kbd></button>
          </>}
          <button onClick={() => { setDialogo({ tipo: 'mover', uuid: contexto.e.uuid }); setContexto(null) }}><Icono nombre="mover" />{t('entrada.mover')}</button>
          <button className="menu__peligro" onClick={() => { eliminar(contexto.e); setContexto(null) }}><Icono nombre="papelera" />{t('comun.eliminar')}<kbd>Supr</kbd></button>
        </div>
      )}

      {dialogo === 'generador' && <Generador alCerrar={cerrarDialogo} />}
      {dialogo === 'atajos' && <Atajos alCerrar={cerrarDialogo} />}
      {dialogo === 'ajustes' && <Ajustes info={info} alCerrar={() => { setDialogo(null); recargar() }} mutar={mutar} />}
      {dialogo && typeof dialogo === 'object' && dialogo.tipo === 'salud' && salud && (
        <PanelSalud salud={salud} inicial={dialogo.pestana} alIr={irA} alCerrar={cerrarDialogo} mutar={mutar} />
      )}
      {dialogo === 'cambio_externo' && (
        <Dialogo titulo={t('principal.cambio_externo_titulo')} alCerrar={cerrarDialogo} pie={<>
          <button className="boton" onClick={cerrarDialogo}>{t('comun.cancelar')}</button>
          <button className="boton boton--peligro" onClick={() => void guardar(true)}>{t('principal.sobrescribir')}</button>
          <button className="boton boton--primario" onClick={() => void guardarComo()}>{t('principal.guardar_como')}</button>
        </>}><div className="dialogo__cuerpo"><p className="nota" style={{ margin: 0 }}>{t('principal.cambio_externo_texto')}</p></div></Dialogo>
      )}
      {dialogo && typeof dialogo === 'object' && dialogo.tipo === 'grupo' && (
        <PedirTexto titulo={dialogo.uuid ? t('principal.renombrar') : t('principal.nuevo_grupo')} rotulo={t('principal.nombre_grupo')}
                    inicial={dialogo.nombre} alCerrar={cerrarDialogo}
                    alAceptar={(n) => void (dialogo.uuid ? mutar('renombrar_grupo', dialogo.uuid, n) : mutar('crear_grupo', dialogo.padre ?? null, n))} />
      )}
      {dialogo && typeof dialogo === 'object' && dialogo.tipo === 'confirmar' && (
        <Confirmar titulo={dialogo.titulo} texto={dialogo.texto} accion={t('comun.eliminar')} peligro alAceptar={dialogo.accion} alCerrar={cerrarDialogo} />
      )}
      {dialogo && typeof dialogo === 'object' && dialogo.tipo === 'mover' && arbol && (
        <Dialogo titulo={t('entrada.mover')} alCerrar={cerrarDialogo}>
          <div className="dialogo__cuerpo" style={{ maxHeight: 420, overflow: 'auto' }}>
            <ArbolGrupos nodo={arbol} activo="" raiz alElegir={(u) => { void mutar('mover_entrada', dialogo.uuid, u); setDialogo(null) }} />
          </div>
        </Dialogo>
      )}
      {dialogo && typeof dialogo === 'object' && dialogo.tipo === 'seccion' && (
        <DialogoSeccion grupo={dialogo.grupo} secciones={info.secciones} alCerrar={cerrarDialogo}
                        alElegir={(s) => {
                          const actual = SECCIONES.find((x) => info.secciones[x] === dialogo.grupo.uuid)
                          void (s ? mutar('asignar_seccion', s, dialogo.grupo.uuid) : actual ? mutar('asignar_seccion', actual, null) : Promise.resolve(null))
                          setDialogo(null)
                        }} />
      )}
    </div>
  )
}

function Selector({ rotulo, valor, opciones, alCambiar }: { rotulo: string; valor: string; opciones: [string, string][]; alCambiar: (v: string) => void }) {
  const { t } = useApp()
  return (
    <label className="campo"><span className="campo__rotulo">{rotulo}</span>
      <select className="control" value={valor} onChange={(e) => alCambiar(e.target.value)}>
        <option value="">{t('filtro.todos')}</option>
        {opciones.map(([v, r]) => <option key={v} value={v}>{r}</option>)}
        {valor && !opciones.some(([v]) => v === valor) && <option value={valor}>{valor}</option>}
      </select></label>
  )
}

function DialogoSeccion({ grupo, secciones, alElegir, alCerrar }: {
  grupo: Grupo; secciones: Info['secciones']; alElegir: (s: Seccion | null) => void; alCerrar: () => void
}) {
  const { t } = useApp()
  const actual = SECCIONES.find((s) => secciones[s] === grupo.uuid) ?? null
  return (
    <Dialogo titulo={t('seccion.asignar')} alCerrar={alCerrar}>
      <div className="dialogo__cuerpo">
        <p className="nota" style={{ margin: 0 }}>{t('seccion.asignar_texto', { g: grupo.nombre })}</p>
        {[...SECCIONES, null].map((s) => (
          <button key={s ?? 'ninguna'} className={`salud__fila${actual === s ? ' salud__fila--activa' : ''}`} onClick={() => alElegir(s)}>
            <Icono nombre={s ? VISTAS.find((v) => v.id === s)!.icono : 'cerrar'} tamano={15} />
            <span className="salud__texto"><span className="salud__titulo">{s ? t(`seccion.${s}` as Clave) : t('seccion.ninguna')}</span></span>
            {actual === s && <Icono nombre="ok" tamano={15} />}
          </button>
        ))}
      </div>
    </Dialogo>
  )
}

function buscarGrupo(n: Grupo | null, uuid: string): Grupo | null {
  if (!n) return null
  if (n.uuid === uuid) return n
  for (const h of n.hijos) { const r = buscarGrupo(h, uuid); if (r) return r }
  return null
}

/** Entradas del grupo y de sus subgrupos; la papelera no cuenta salvo que se pida. */
function total(n: Grupo | null, conPapelera = false): number {
  if (!n || (n.papelera && !conPapelera)) return 0
  return n.entradas + n.hijos.reduce((s, h) => s + total(h), 0)
}

function ArbolGrupos({ nodo, activo, raiz = false, ocultarPapelera = false, alElegir, alNuevo, alRenombrar, alEliminar, alVaciar, alSeccion }: {
  nodo: Grupo; activo: string; raiz?: boolean; ocultarPapelera?: boolean; alElegir: (u: string) => void; alNuevo?: (padre: string) => void
  alRenombrar?: (g: Grupo) => void; alEliminar?: (g: Grupo) => void; alVaciar?: () => void; alSeccion?: (g: Grupo) => void
}) {
  const { t } = useApp()
  const [abierto, setAbierto] = useState(true)
  const hijos = nodo.hijos.filter((h) => !(ocultarPapelera && h.papelera))
  return (
    <ul className="arbol">
      <li>
        <div className={`nodo${activo === nodo.uuid ? ' nodo--activo' : ''}`} onClick={() => alElegir(nodo.uuid)}
             data-tip={nodo.papelera ? t('tip.papelera') : undefined}>
          <span className="plegar" onClick={(e) => { e.stopPropagation(); setAbierto(!abierto) }}>
            {hijos.length > 0 && <Icono nombre={abierto ? 'abajo' : 'derecha'} tamano={12} />}</span>
          <Icono nombre={nodo.papelera ? 'papelera' : 'carpeta'} />
          <span className="nodo__nombre">{nodo.nombre}</span>
          <span className="nodo__cuenta">{nodo.entradas || ''}</span>
          {alNuevo && (
            <span className="nodo__acciones" onClick={(e) => e.stopPropagation()}>
              {nodo.papelera ? (
                <button className="boton boton--fantasma boton--sm boton--icono" onClick={alVaciar} aria-label={t('principal.vaciar_papelera')} title={t('principal.vaciar_papelera')}><Icono nombre="papelera" tamano={14} /></button>
              ) : (<>
                <button className="boton boton--fantasma boton--sm boton--icono" onClick={() => alNuevo(nodo.uuid)} aria-label={t('principal.subgrupo')} title={t('principal.subgrupo')}><Icono nombre="mas" tamano={14} /></button>
                <button className="boton boton--fantasma boton--sm boton--icono" onClick={() => alRenombrar?.(nodo)} aria-label={t('principal.renombrar')} title={t('principal.renombrar')}><Icono nombre="lapiz" tamano={14} /></button>
                {!raiz && alSeccion && <button className="boton boton--fantasma boton--sm boton--icono" onClick={() => alSeccion(nodo)} aria-label={t('seccion.asignar')} title={t('tip.seccion')}><Icono nombre="capas" tamano={14} /></button>}
                {!raiz && <button className="boton boton--fantasma boton--sm boton--icono" onClick={() => alEliminar?.(nodo)} aria-label={t('comun.eliminar')} title={t('comun.eliminar')}><Icono nombre="papelera" tamano={14} /></button>}
              </>)}
            </span>
          )}
        </div>
        {abierto && hijos.length > 0 && hijos.map((h) => (
          <ArbolGrupos key={h.uuid} nodo={h} activo={activo} ocultarPapelera={ocultarPapelera} alElegir={alElegir} alNuevo={alNuevo}
                       alRenombrar={alRenombrar} alEliminar={alEliminar} alVaciar={alVaciar} alSeccion={alSeccion} />
        ))}
      </li>
    </ul>
  )
}

/** Carga la entrada seleccionada y la muestra como identidad operativa o como credencial. */
function Seleccion({ uuid, version, mutar, alTipo, alEditar, alMover, alEliminado }: {
  uuid: string; version: number; mutar: Mutar; alTipo: (t: 'identidad' | 'entrada') => void
  alEditar: () => void; alMover: () => void; alEliminado: () => void
}) {
  const { error } = useApp()
  const [d, setD] = useState<Detalle | null>(null)
  useEffect(() => {
    let vigente = true
    void llamar<{ entrada: Detalle }>('entrada', uuid).then((r) => {
      if (!vigente) return
      if (r.ok) { setD(r.entrada); alTipo(r.entrada.tipo) } else error(r.error)
    })
    return () => { vigente = false }
  }, [uuid, version, error, alTipo])
  if (!d || d.uuid !== uuid) return null
  return d.tipo === 'identidad'
    ? <VistaIdentidad d={d} mutar={mutar} alEditar={alEditar} alMover={alMover} alEliminado={alEliminado} />
    : <VistaEntrada d={d} mutar={mutar} alEditar={alEditar} alMover={alMover} alEliminado={alEliminado} />
}

function VistaEntrada({ d, mutar, alEditar, alMover, alEliminado }: {
  d: Detalle; mutar: Mutar; alEditar: () => void; alMover: () => void; alEliminado: () => void
}) {
  const { t, idioma } = useApp()
  const [confirmar, setConfirmar] = useState(false)
  const etiqueta = (c: string) => (ESTANDAR.includes(c) ? t(`campo.${c}` as Clave) : c)
  const campos = d.campos.filter((c) => c.clave !== 'Title' && !OCULTOS.includes(c.clave) && !(c.vacio && !c.valor))
  const titulo = d.titulo || t('entrada.sin_titulo')
  const editable = !d.en_papelera

  return (
    <div className="detalle">
      <div className="detalle__cabeza">
        <h1 className="detalle__titulo seleccionable">{titulo}</h1>
        <div className="detalle__acciones">
          {editable && <button className="boton boton--sm" onClick={alEditar}><Icono nombre="lapiz" tamano={14} />{t('comun.editar')}</button>}
          {editable && <button className="boton boton--sm boton--icono" onClick={() => void mutar('duplicar_entrada', d.uuid)} title={t('entrada.duplicar')} aria-label={t('entrada.duplicar')}><Icono nombre="duplicar" tamano={14} /></button>}
          <button className="boton boton--sm boton--icono" onClick={alMover} title={t('entrada.mover')} aria-label={t('entrada.mover')}><Icono nombre="mover" tamano={14} /></button>
          <button className="boton boton--sm boton--icono boton--peligro" title={t('comun.eliminar')} aria-label={t('comun.eliminar')}
                  onClick={() => (d.en_papelera ? setConfirmar(true) : void mutar('eliminar_entrada', d.uuid).then(alEliminado))}><Icono nombre="papelera" tamano={14} /></button>
        </div>
      </div>
      <div className="etiquetas">
        {d.en_papelera && <span className="chip chip--aviso">{t('entrada.en_papelera')}</span>}
        {d.alertas.map((a) => <span key={a} className={`chip ${a === 'renovar' || a === 'por_caducar' ? 'chip--aviso' : 'chip--peligro'}`}>{t(`alerta.${a}` as Clave)}</span>)}
        {!d.caducada && d.expira && <span className="chip">{t('entrada.caduca_el', { f: fecha(d.expira, idioma) })}</span>}
        {d.estado && <ChipEstado estado={d.estado} />}
        {d.etiquetas.map((e) => <span key={e} className="chip">{e}</span>)}
      </div>

      <div className="bloque">
        {campos.map((c) => <Dato key={c.clave} uuid={d.uuid} clave={c.clave} rotulo={etiqueta(c.clave)} valor={c.valor} protegido={c.protegido} vacio={c.vacio} mono={c.clave === 'Password'} />)}
        <FilaTotp uuid={d.uuid} activo={d.totp} />
      </div>

      <div className="bloque"><div className="bloque__titulo">{t('entrada.adjuntos')}</div>
        <Galeria uuid={d.uuid} adjuntos={d.adjuntos_lista} editable={editable} mutar={mutar} /></div>

      <div className="bloque"><div className="bloque__titulo">{t('entrada.historial')}</div>
        <Historial uuid={d.uuid} historial={d.historial} editable={editable} mutar={mutar} /></div>

      <p className="nota" style={{ margin: 0 }}>{t('entrada.creada')}: {fecha(d.fechas.CreationTime, idioma, true)} · {t('entrada.modificada')}: {fecha(d.fechas.LastModificationTime, idioma, true)}</p>
      {confirmar && <Confirmar titulo={t('comun.eliminar')} texto={t('principal.confirmar_eliminar_def', { t: titulo })} accion={t('comun.eliminar')} peligro
                               alAceptar={() => void mutar('eliminar_entrada', d.uuid).then(alEliminado)} alCerrar={() => setConfirmar(false)} />}
    </div>
  )
}

function Editor({ uuid, alCerrar, alGuardar }: {
  uuid?: string; alCerrar: () => void
  alGuardar: (campos: Campo[], etiquetas: string[], expira: string) => Promise<void>
}) {
  const { t, error } = useApp()
  const [estandar, setEstandar] = useState<Record<string, string> | null>(null)
  const [otros, setOtros] = useState<Campo[]>([])
  const [etiquetas, setEtiquetas] = useState('')
  const [caduca, setCaduca] = useState(false)
  const [fechaCaduca, setFechaCaduca] = useState('')
  const [ver, setVer] = useState(false)
  const [bits, setBits] = useState(0)
  const [generador, setGenerador] = useState(false)
  const [aviso, setAviso] = useState('')
  const [inicial, setInicial] = useState('')
  const [descartar, setDescartar] = useState(false)

  useEffect(() => {
    if (!uuid) {
      const vacio = Object.fromEntries(ESTANDAR.map((c) => [c, '']))
      setEstandar(vacio); setOtros([]); setInicial(JSON.stringify([vacio, [], '', false, '']))
      return
    }
    void llamar<{ entrada: Detalle }>('para_editar', uuid).then((r) => {
      if (!r.ok) { error(r.error); return }
      const d = r.entrada
      const est = Object.fromEntries(ESTANDAR.map((c) => [c, d.campos.find((x) => x.clave === c)?.valor ?? '']))
      const resto = d.campos.filter((c) => !ESTANDAR.includes(c.clave)).map((c) => ({ ...c, valor: c.valor ?? '' }))
      const tags = d.etiquetas.join(', ')
      const f = d.expira ? d.expira.slice(0, 10) : ''
      setEstandar(est); setOtros(resto); setEtiquetas(tags); setCaduca(!!d.expira); setFechaCaduca(f)
      setInicial(JSON.stringify([est, resto, tags, !!d.expira, f]))
    })
  }, [uuid, error])

  const contrasena = estandar?.Password ?? ''
  useEffect(() => {
    let vigente = true
    void llamar<{ bits: number }>('calidad', contrasena).then((r) => { if (vigente && r.ok) setBits(r.bits) })
    return () => { vigente = false }
  }, [contrasena])
  if (!estandar) return null

  const sucio = JSON.stringify([estandar, otros, etiquetas, caduca, fechaCaduca]) !== inicial
  const cancelar = () => (sucio ? setDescartar(true) : alCerrar())
  const poner = (k: string, v: string) => setEstandar({ ...estandar, [k]: v })
  const guardar = async () => {
    const claves = otros.map((c) => c.clave.trim())
    // En una entrada normal los campos Ficha.* y Servicio.* se respetan si ya venían (por ejemplo, de KeePassXC).
    if (new Set(claves).size !== claves.length || claves.some((c) => !c || ESTANDAR.includes(c))) { setAviso(t('entrada.campo_existe')); return }
    const campos: Campo[] = [...ESTANDAR.map((c) => ({ clave: c, valor: estandar[c] ?? '', protegido: c === 'Password' })),
      ...otros.map((c) => ({ ...c, clave: c.clave.trim() }))]
    await alGuardar(normalizarOtp(campos), etiquetas.split(',').map((x) => x.trim()).filter(Boolean), caduca && fechaCaduca ? `${fechaCaduca}T00:00:00+00:00` : '')
  }
  const color = bits < 50 ? 'var(--n-peligro)' : bits < 80 ? 'var(--n-aviso)' : 'var(--n-exito)'

  return (
    <div className="editor" onKeyDown={(e) => teclasEditor(e, () => void guardar(), cancelar)}>
      <h1 className="detalle__titulo">{uuid ? estandar.Title || t('entrada.sin_titulo') : t('entrada.nueva')}</h1>
      <label className="campo"><span className="campo__rotulo">{t('campo.Title')}</span>
        <input className="control" autoFocus value={estandar.Title} onChange={(e) => poner('Title', e.target.value)} /></label>
      <div className="editor__fila">
        <label className="campo"><span className="campo__rotulo">{t('campo.UserName')}</span>
          <input className="control" value={estandar.UserName} spellCheck={false} onChange={(e) => poner('UserName', e.target.value)} /></label>
        <label className="campo"><span className="campo__rotulo">{t('campo.URL')}</span>
          <input className="control" value={estandar.URL} spellCheck={false} onChange={(e) => poner('URL', e.target.value)} /></label>
      </div>
      <label className="campo"><span className="campo__rotulo">{t('campo.Password')}</span>
        <div className="grupo-control">
          <input className="control mono" type={ver ? 'text' : 'password'} value={contrasena} spellCheck={false} autoComplete="new-password"
                 onChange={(e) => poner('Password', e.target.value)} />
          <button type="button" className="boton boton--icono" onClick={() => setVer(!ver)} title={t('tip.mostrar')} aria-label={t('tip.mostrar')}><Icono nombre={ver ? 'ojo_cerrado' : 'ojo'} /></button>
          <button type="button" className="boton boton--icono" onClick={() => setGenerador(true)} title={t('principal.generador')} aria-label={t('principal.generador')}><Icono nombre="dado" /></button>
        </div>
        <div className="calidad"><i style={{ width: `${Math.min(100, bits / 1.28)}%`, background: color }} /></div>
        <span className="nota">{t('entrada.calidad', { b: bits })}</span></label>
      <label className="campo"><span className="campo__rotulo">{t('campo.Notes')}</span>
        <textarea className="control" value={estandar.Notes} onChange={(e) => poner('Notes', e.target.value)} /></label>

      <EditorCampos campos={otros} ver={ver} alCambiar={(c) => setOtros(c.map((x) => ({ ...x, valor: x.valor ?? '' })))} />

      <div className="editor__fila">
        <label className="campo"><span className="campo__rotulo">{t('entrada.etiquetas')}</span>
          <input className="control" value={etiquetas} placeholder={t('entrada.etiquetas_ayuda')} onChange={(e) => setEtiquetas(e.target.value)} /></label>
        <div className="campo"><span className="campo__rotulo">{t('entrada.fecha_caducidad')}</span>
          <div className="grupo-control"><label className="casilla"><input type="checkbox" checked={caduca} onChange={(e) => setCaduca(e.target.checked)} />{t('entrada.caduca')}</label>
            <input className="control" type="date" disabled={!caduca} value={fechaCaduca} onChange={(e) => setFechaCaduca(e.target.value)} /></div></div>
      </div>

      {aviso && <p className="error" style={{ margin: 0 }}>{aviso}</p>}
      <div className="editor__pie">
        <button className="boton" onClick={cancelar}>{t('comun.cancelar')}</button>
        <button className="boton boton--primario" onClick={() => void guardar()}><Icono nombre="ok" tamano={14} />{t('comun.guardar')}</button>
      </div>
      {generador && <Generador alCerrar={() => setGenerador(false)} alUsar={(v) => { poner('Password', v); setVer(true); setGenerador(false) }} />}
      {descartar && <Confirmar titulo={t('editor.descartar_titulo')} texto={t('editor.descartar_texto')} accion={t('editor.descartar')} peligro
                               alAceptar={alCerrar} alCerrar={() => setDescartar(false)} />}
    </div>
  )
}
