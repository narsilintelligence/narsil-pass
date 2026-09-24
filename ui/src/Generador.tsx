import { useCallback, useEffect, useState } from 'react'
import { llamar } from './api'
import { useApp } from './contexto'
import { Icono } from './iconos'
import { Dialogo } from './Dialogos'

export function Generador({ alCerrar, alUsar }: { alCerrar: () => void; alUsar?: (v: string) => void }) {
  const { t, copiarTexto } = useApp()
  const [modo, setModo] = useState<'contrasena' | 'frase'>('contrasena')
  const [longitud, setLongitud] = useState(24)
  const [conjuntos, setConjuntos] = useState({ minusculas: true, mayusculas: true, digitos: true, simbolos: true, parecidos: false })
  const [palabras, setPalabras] = useState(6)
  const [separador, setSeparador] = useState('-')
  const [mayuscula, setMayuscula] = useState(false)
  const [numero, setNumero] = useState(false)
  const [salida, setSalida] = useState({ texto: '', bits: 0 })

  const generar = useCallback(async () => {
    const r = await llamar<{ texto: string; bits: number }>('generar', modo === 'frase'
      ? { modo, palabras, separador, mayuscula, numero } : { modo, longitud, ...conjuntos })
    if (r.ok) setSalida({ texto: r.texto, bits: r.bits })
  }, [modo, palabras, separador, mayuscula, numero, longitud, conjuntos])

  useEffect(() => { void generar() }, [generar])

  const casilla = (clave: keyof typeof conjuntos, rotulo: string) => (
    <label className="casilla"><input type="checkbox" checked={conjuntos[clave]}
      onChange={(e) => setConjuntos({ ...conjuntos, [clave]: e.target.checked })} />{rotulo}</label>
  )
  return (
    <Dialogo titulo={t('generador.titulo')} alCerrar={alCerrar} pie={<>
      <button className="boton" onClick={() => void generar()}><Icono nombre="refrescar" tamano={14} />{t('generador.otra')}</button>
      <button className="boton" onClick={() => void copiarTexto(salida.texto)}><Icono nombre="copiar" tamano={14} />{t('comun.copiar')}</button>
      {alUsar && <button className="boton boton--primario" onClick={() => alUsar(salida.texto)}>{t('generador.usar')}</button>}
    </>}>
      <div className="pestanas">
        {(['contrasena', 'frase'] as const).map((m) => (
          <button key={m} className={`pestana${modo === m ? ' pestana--activa' : ''}`} onClick={() => setModo(m)}>{t(`generador.${m}`)}</button>
        ))}
      </div>
      <div className="dialogo__cuerpo">
        <div className="salida-generador">{salida.texto}</div>
        <span className="nota">{t('generador.entropia', { b: salida.bits })}</span>
        {modo === 'contrasena' ? (<>
          <label className="campo"><span className="campo__rotulo">{t('generador.longitud')}: {longitud}</span>
            <input type="range" min={8} max={96} value={longitud} onChange={(e) => setLongitud(Number(e.target.value))} style={{ accentColor: 'var(--n-bronce-vivo)' }} /></label>
          <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap' }}>
            {casilla('minusculas', t('generador.minusculas'))}{casilla('mayusculas', t('generador.mayusculas'))}
            {casilla('digitos', t('generador.digitos'))}{casilla('simbolos', t('generador.simbolos'))}
          </div>
          {casilla('parecidos', t('generador.parecidos'))}
        </>) : (<>
          <label className="campo"><span className="campo__rotulo">{t('generador.palabras')}: {palabras}</span>
            <input type="range" min={3} max={12} value={palabras} onChange={(e) => setPalabras(Number(e.target.value))} style={{ accentColor: 'var(--n-bronce-vivo)' }} /></label>
          <label className="campo"><span className="campo__rotulo">{t('generador.separador')}</span>
            <input className="control mono" style={{ width: 80 }} maxLength={3} value={separador} onChange={(e) => setSeparador(e.target.value)} /></label>
          <label className="casilla"><input type="checkbox" checked={mayuscula} onChange={(e) => setMayuscula(e.target.checked)} />{t('generador.mayuscula')}</label>
          <label className="casilla"><input type="checkbox" checked={numero} onChange={(e) => setNumero(e.target.checked)} />{t('generador.numero')}</label>
        </>)}
      </div>
    </Dialogo>
  )
}
