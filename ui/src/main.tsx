import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './estilos.css'
import { llamar, type Estado } from './api'
import { Proveedor } from './contexto'
import { App } from './App'

// El menú contextual del motor web no aporta nada en un gestor de contraseñas salvo en los campos.
document.addEventListener('contextmenu', (e) => {
  const destino = e.target as HTMLElement
  if (!destino.closest('input, textarea, .seleccionable')) e.preventDefault()
})

void (async () => {
  let r = await llamar<Estado>('estado')
  for (let intento = 0; !r.ok && intento < 20; intento++) {
    await new Promise((x) => window.setTimeout(x, 250))
    r = await llamar<Estado>('estado')
  }
  if (!r.ok) {  // nunca una ventana en blanco: se dice qué pasa y dónde está el registro
    const raiz = document.getElementById('raiz')!
    raiz.className = 'fallo-arranque'
    raiz.textContent = 'NARSIL Pass no ha podido iniciar la interfaz. Consulte el registro en %APPDATA%\\NARSIL Pass\\registro.'
    return
  }
  const estado = r
  document.documentElement.lang = estado.idioma
  createRoot(document.getElementById('raiz')!).render(
    <StrictMode>
      <Proveedor idiomaInicial={estado.idioma}><App estadoInicial={estado} /></Proveedor>
    </StrictMode>,
  )
})()
