import { useCallback, useEffect, useState } from 'react'
import { llamar, type Estado, type Info } from './api'
import { useApp } from './contexto'
import { Desbloqueo } from './Desbloqueo'
import { Principal } from './Principal'

export function App({ estadoInicial }: { estadoInicial: Estado }) {
  const { t, error } = useApp()
  const [estado, setEstado] = useState(estadoInicial)
  const [info, setInfo] = useState<Info | null>(estadoInicial.abierta ? estadoInicial.info : null)
  const [aviso, setAviso] = useState('')

  const bloquear = useCallback(async (porInactividad = false) => {
    const b = await llamar('bloquear', true)
    // Si Python no ha podido guardar, la base sigue abierta: no se finge un bloqueo que no existe.
    if (!b.ok) { error(b.error ?? 'interno'); return }
    const r = await llamar<Estado>('estado')
    if (r.ok) setEstado({ ...r, inicial: info?.ruta ?? r.inicial })
    setAviso(porInactividad ? t('desbloqueo.bloqueada') : '')
    setInfo(null)
  }, [info, t, error])

  // Bloqueo por inactividad: cualquier tecla o movimiento reinicia la cuenta.
  useEffect(() => {
    if (!info || !estado.preferencias.bloqueo_minutos) return
    let ultimo = Date.now()
    const actividad = () => { ultimo = Date.now() }
    const eventos = ['mousemove', 'mousedown', 'keydown', 'wheel', 'touchstart']
    eventos.forEach((e) => window.addEventListener(e, actividad, { passive: true }))
    const reloj = window.setInterval(() => {
      if (Date.now() - ultimo > estado.preferencias.bloqueo_minutos * 60_000) void bloquear(true)
    }, 5000)
    return () => { eventos.forEach((e) => window.removeEventListener(e, actividad)); window.clearInterval(reloj) }
  }, [info, estado.preferencias.bloqueo_minutos, bloquear])

  // Las preferencias se pueden cambiar en Ajustes: se releen al volver a la pantalla principal.
  useEffect(() => {
    if (!info) return
    const reloj = window.setInterval(() => {
      void llamar<Estado>('estado').then((r) => { if (r.ok && r.preferencias.bloqueo_minutos !== estado.preferencias.bloqueo_minutos) setEstado(r) })
    }, 15000)
    return () => window.clearInterval(reloj)
  }, [info, estado.preferencias.bloqueo_minutos])

  if (!info) return <Desbloqueo key={estado.inicial ?? ''} estado={estado} aviso={aviso} alAbrir={(i) => { setAviso(''); setInfo(i) }} />
  return <Principal infoInicial={info} alBloquear={() => void bloquear()} />
}
