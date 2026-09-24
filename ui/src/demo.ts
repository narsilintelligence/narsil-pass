// Doble en memoria del puente, solo para la compilación de demostración (capturas y pruebas de
// interfaz). Imita las respuestas de app/api.py; los datos son inventados.
type Obj = Record<string, unknown>
interface C { clave: string; valor: string; protegido: boolean }
interface E { uuid: string; grupo: string; campos: C[]; etiquetas: string[]; expira: string | null; alertas: string[]
  adjuntos: { nombre: string; tamano: number }[]; historial: { titulo: string; modificada: string }[]; modificada: string }

const retrato = (fondo: string, piel: string, pelo: string) => 'data:image/svg+xml;utf8,' + encodeURIComponent(
  `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 300 300"><defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1">` +
  `<stop offset="0" stop-color="${fondo}"/><stop offset="1" stop-color="#141B2E"/></linearGradient></defs>` +
  `<rect width="300" height="300" fill="url(#g)"/><path d="M60 300c8-62 44-96 90-96s82 34 90 96z" fill="#2a3656"/>` +
  `<circle cx="150" cy="128" r="58" fill="${piel}"/><path d="M92 124c0-44 26-70 58-70s58 26 58 70c-12-22-30-34-58-34s-46 12-58 34z" fill="${pelo}"/></svg>`)

export function crearDemo() {
  let abierta = false
  let idioma = 'es'
  let renovar = 180
  const pref = { recordar_recientes: true, bloqueo_minutos: 5, portapapeles_segundos: 12, autoguardado: true, copia_previa: true }
  const g = (uuid: string, nombre: string, hijos: Obj[] = [], papelera = false) => ({ uuid, nombre, entradas: 0, papelera, hijos })
  const arbol = g('raiz', 'Unidad de análisis', [
    g('int', 'Servicios internos', [g('infra', 'Infraestructura')]),
    g('ext', 'Servicios externos', [g('fuentes', 'Fuentes abiertas')]),
    g('id', 'Identidades operativas'),
    g('pap', 'Papelera', [], true)])
  const secciones = { interno: 'int', externo: 'ext', identidades: 'id' }
  const hace = (d: number) => new Date(Date.now() - d * 86400000).toISOString()
  const c = (clave: string, valor: string, protegido = false): C => ({ clave, valor, protegido })
  const id = (x: Record<string, string>) => Object.entries(x).map(([k, v]) => c(k, v, k === 'Password' || k.endsWith('.contrasena')))
  const entradas: E[] = [
    { uuid: 'e1', grupo: 'int', campos: [c('Title', 'Intranet de la unidad'), c('UserName', 'analista.07'), c('Password', 'Rb8#tLq2!Vn4', true), c('URL', 'https://intranet.unidad.local'), c('Notes', '')],
      etiquetas: ['interno'], expira: null, alertas: ['repetida'], adjuntos: [], historial: [], modificada: hace(12) },
    { uuid: 'e2', grupo: 'infra', campos: [c('Title', 'VPN corporativa'), c('UserName', 'analista.07'), c('Password', 'correcto-caballo-bateria-grapa', true), c('URL', 'vpn.unidad.local'), c('Notes', 'Perfil WireGuard en el portátil de la unidad.')],
      etiquetas: [], expira: null, alertas: ['renovar'], adjuntos: [{ nombre: 'perfil-wg.conf', tamano: 412 }], historial: [], modificada: hace(410) },
    { uuid: 'e3', grupo: 'infra', campos: [c('Title', 'Servidor de análisis'), c('UserName', 'admin'), c('Password', 'kQ9!mZ4#pX7@', true), c('URL', 'https://analisis.unidad.local'), c('Notes', '')],
      etiquetas: ['nodo'], expira: hace(-6), alertas: ['por_caducar'], adjuntos: [], historial: [], modificada: hace(40) },
    { uuid: 'e4', grupo: 'ext', campos: [c('Title', 'Correo de la operación'), c('UserName', 'norte.analisis@proton.example'), c('Password', 'V7#qz!Lr9@kTm2$w', true), c('URL', 'https://mail.proton.me'), c('Notes', 'Buzón compartido del equipo.'), c('otp', 'otpauth://totp/x?secret=GEZDGNBVGY3TQOJQ', true)],
      etiquetas: ['correo', 'equipo'], expira: null, alertas: [], adjuntos: [], historial: [{ titulo: 'Correo de la operación', modificada: hace(20) }], modificada: hace(2) },
    { uuid: 'e5', grupo: 'ext', campos: [c('Title', 'Foro de seguridad'), c('UserName', 'n0rte'), c('Password', '1234', true), c('URL', 'https://foro.example'), c('Notes', '')],
      etiquetas: [], expira: null, alertas: ['debil'], adjuntos: [], historial: [], modificada: hace(30) },
    { uuid: 'e6', grupo: 'fuentes', campos: [c('Title', 'Registro mercantil'), c('UserName', 'unidad.analisis'), c('Password', 'Hy7@pL3!xC6&', true), c('URL', 'https://www.registradores.org'), c('Notes', '')],
      etiquetas: [], expira: hace(3), alertas: ['caducada'], adjuntos: [], historial: [], modificada: hace(90) },
    { uuid: 'i1', grupo: 'id', etiquetas: ['virtual-humint'], expira: null, alertas: ['repetida'], modificada: hace(5),
      adjuntos: [{ nombre: 'retrato-perfil.jpg', tamano: 184320 }, { nombre: 'viaje-lisboa.jpg', tamano: 402113 }, { nombre: 'estudio.png', tamano: 251900 }, { nombre: 'leyenda.pdf', tamano: 88120 }],
      historial: [{ titulo: 'Marta Ribas', modificada: hace(9) }],
      campos: id({ Title: 'Marta Ribas', UserName: 'marta.ribas.viajes@correo.example', Password: 'kH3!pQ9z#Lm2-x8Vr', URL: 'https://correo.example', Notes: '',
        'NARSIL.Tipo': 'identidad', 'Ficha.nombre': 'Marta', 'Ficha.apellidos': 'Ribas Soler', 'Ficha.alias': 'martaviaja_ejemplo', 'Ficha.genero': 'Mujer',
        'Ficha.fecha_nacimiento': '1991-04-17', 'Ficha.lugar_nacimiento': 'Valencia', 'Ficha.nacionalidad': 'Española', 'Ficha.idiomas': 'Español, valenciano, inglés (B2)',
        'Ficha.ciudad_residencia': 'Lisboa', 'Ficha.pais_residencia': 'Portugal', 'Ficha.correo': 'marta.ribas.viajes@correo.example', 'Ficha.telefono': '+351 900 000 000',
        'Ficha.estudios': 'Grado en Bellas Artes', 'Ficha.centro_estudios': 'Universidad de ejemplo', 'Ficha.profesion': 'Fotógrafa de viajes',
        'Ficha.lugar_trabajo': 'Autónoma', 'Ficha.intereses': 'Fotografía analógica, senderismo, cocina asiática.', 'Ficha.estatura': '1,68 m', 'Ficha.pelo': 'Castaño, media melena',
        'Ficha.dispositivo': 'Android dedicado', 'Ficha.huso_horario': 'Europe/Lisbon', 'Ficha.ubicacion_conexion': 'Salida por Lisboa',
        'Ficha.estado': 'activa', 'Ficha.operacion': 'Operación Norte', 'Ficha.responsable': 'Analista 07', 'Ficha.creada_el': '2026-05-27',
        'Ficha.cobertura': 'Fotógrafa freelance que vende reportajes de viaje a revistas pequeñas.', 'Ficha.pautas': 'No interactuar con perfiles de la investigación en su primer mes.',
        'Ficha.biografia': 'Nació en Valencia en 1991. Estudió Bellas Artes y se especializó en fotografía documental.\n\nDesde 2022 vive en Lisboa, trabaja por encargo y publica sus viajes en Instagram. Escribe en español informal, sin emojis, y responde por la tarde.',
        'Servicio.1.nombre': 'Instagram', 'Servicio.1.url': 'https://www.instagram.com/martaviaja_ejemplo', 'Servicio.1.id': '5800000001', 'Servicio.1.usuario': 'martaviaja_ejemplo',
        'Servicio.1.alias': 'Marta · viajes', 'Servicio.1.correo': 'marta.ribas.viajes@correo.example', 'Servicio.1.contrasena': 'Rb8#tLq2!Vn4',
        'Servicio.2.nombre': 'Correo', 'Servicio.2.url': 'https://correo.example', 'Servicio.2.usuario': 'marta.ribas.viajes@correo.example', 'Servicio.2.contrasena': 'kH3!pQ9z#Lm2-x8Vr', 'Servicio.2.telefono': '+351 900 000 000',
        'Servicio.3.nombre': 'Telegram', 'Servicio.3.id': '6000000001', 'Servicio.3.usuario': '@martaviaja_ejemplo', 'Servicio.3.telefono': '+351 900 000 000', 'Servicio.3.notas': 'Sesión solo en el Android dedicado.' }) },
    { uuid: 'i2', grupo: 'id', etiquetas: [], expira: null, alertas: [], modificada: hace(60), adjuntos: [], historial: [],
      campos: id({ Title: 'Iker Solano', UserName: '', Password: '', URL: '', Notes: '', 'NARSIL.Tipo': 'identidad', 'Ficha.nombre': 'Iker', 'Ficha.apellidos': 'Solano',
        'Ficha.profesion': 'Técnico de sistemas', 'Ficha.estado': 'reposo', 'Servicio.1.nombre': 'LinkedIn', 'Servicio.1.usuario': 'iker.solano.ejemplo', 'Servicio.1.contrasena': 'Mw5#tR8!yU2@oP7s' }) },
  ]
  const imagenes: Record<string, string> = {
    'retrato-perfil.jpg': retrato('#3a4a6e', '#d9b39a', '#4b2e22'), 'viaje-lisboa.jpg': retrato('#9F6A57', '#e0c0a8', '#2a1a14'),
    'estudio.png': retrato('#5f7f9e', '#caa089', '#6b4630'),
  }
  const val = (e: E, k: string) => e.campos.find((x) => x.clave === k)?.valor ?? ''
  const esId = (e: E) => val(e, 'NARSIL.Tipo') === 'identidad'
  const nServ = (e: E) => new Set(e.campos.map((x) => /^Servicio\.(\d+)\./.exec(x.clave)?.[1]).filter(Boolean)).size
  const resumen = (e: E) => ({ uuid: e.uuid, titulo: val(e, 'Title'), usuario: val(e, 'UserName'), url: val(e, 'URL'), grupo: e.grupo,
    etiquetas: e.etiquetas, modificada: e.modificada, expira: e.expira, caducada: !!e.expira && new Date(e.expira) < new Date(),
    totp: !!val(e, 'otp'), adjuntos: e.adjuntos.length, tipo: esId(e) ? 'identidad' : 'entrada', estado: val(e, 'Ficha.estado'),
    servicios: nServ(e), fotos: e.adjuntos.filter((a) => /\.(jpe?g|png)$/i.test(a.nombre)).length, alertas: e.alertas })
  const info = () => ({ nombre: 'Unidad de análisis', descripcion: '', formato: 'KDBX 4.0', es_v3: false, cifrado: 'ChaCha20', kdf: 'Argon2id',
    kdf_iteraciones: 12, kdf_memoria_mib: 64, ruta: 'C:\\Users\\operador\\Documents\\unidad.kdbx', cambios: false, papelera: 'pap', raiz: 'raiz',
    entradas: entradas.length, secciones, renovar_dias: renovar })
  const contar = (n: Obj): Obj => ({ ...n, entradas: entradas.filter((e) => e.grupo === n.uuid).length, hijos: (n.hijos as Obj[]).map(contar) })
  const debajo = (raiz: string): string[] => {
    const busca = (n: Obj): Obj | null => (n.uuid === raiz ? n : (n.hijos as Obj[]).map(busca).find(Boolean) ?? null)
    const todos = (n: Obj): string[] => [n.uuid as string, ...(n.hijos as Obj[]).flatMap(todos)]
    const r = busca(arbol)
    return r ? todos(r).filter((u) => raiz === 'pap' || u !== 'pap') : []
  }
  const ref = (e: E, campo = 'Password', extra: Obj = {}) => ({ uuid: e.uuid, titulo: val(e, 'Title'), grupo: e.grupo, campo, servicio: campo.startsWith('Servicio.') ? val(e, campo.replace('contrasena', 'nombre')) : '', ...extra })
  const por = (u: string) => entradas.find((x) => x.uuid === u)!
  const salud = () => ({
    repetidas: [[ref(por('e1')), ref(por('i1'), 'Servicio.1.contrasena')]], debiles: [ref(por('e5'), 'Password', { bits: 13 })],
    renovar: renovar ? [ref(por('e2'), 'Password', { dias: 410, fecha: hace(410) })] : [], caducadas: [ref(por('e6'), 'Password', { fecha: hace(3) })],
    por_caducar: [ref(por('e3'), 'Password', { fecha: hace(-6) })], renovar_dias: renovar, total: renovar ? 5 : 4,
  })
  const host = (u: string) => u.toLowerCase().replace(/^[a-z]+:\/\//, '').split(/[/:?#]/)[0].replace(/^www\./, '')
  const servicios = (e: E) => new Set([host(val(e, 'URL')), ...e.campos.filter((x) => /^Servicio\.\d+\.nombre$/.test(x.clave)).map((x) => x.valor.toLowerCase())].filter(Boolean))
  const usuarios = (e: E) => new Set([val(e, 'UserName'), ...e.campos.filter((x) => /^Servicio\.\d+\.usuario$/.test(x.clave)).map((x) => x.valor)].filter(Boolean))
  const ok = (x: Obj = {}) => Promise.resolve({ ok: true, ...x })
  const detalle = (e: E, claro: boolean) => ({ ...resumen(e),
    campos: e.campos.map((x) => ({ clave: x.clave, protegido: x.protegido, valor: x.protegido && !claro ? null : x.valor, vacio: !x.valor })),
    fechas: { CreationTime: hace(120), LastModificationTime: e.modificada }, historial: e.historial.map((h, i) => ({ indice: i, ...h })),
    adjuntos_lista: e.adjuntos, en_papelera: e.grupo === 'pap' })
  return {
    estado: () => ok({ version: '1.0.0', idioma, recientes: ['C:\\Users\\operador\\Documents\\unidad.kdbx', 'C:\\Users\\operador\\Documents\\personal.kdbx'], inicial: null, abierta,
      info: abierta ? info() : null, preferencias: pref, portapapeles_nativo: true }),
    guardar_preferencias: (x: Obj) => { if (typeof x.idioma === 'string') idioma = x.idioma; Object.assign(pref, x); return ok() },
    olvidar_reciente: () => ok(),
    elegir_base: () => ok({ ruta: 'C:\\Users\\operador\\Documents\\otra-base.kdbx' }),
    elegir_fichero_clave: () => ok({ ruta: null }), elegir_destino: () => ok({ ruta: 'C:\\Users\\operador\\Documents\\nueva.kdbx' }),
    crear_fichero_clave: () => ok({ ruta: null }),
    desbloquear: (_r: string, clave: string) => { if (clave !== 'demo') return Promise.resolve({ ok: false, error: 'credenciales' }); abierta = true; return ok({ info: info() }) },
    crear_base: () => { abierta = true; return ok({ info: info() }) },
    bloquear: () => { abierta = false; return ok() },
    info: () => ok({ info: info() }), grupos: () => ok({ arbol: contar(arbol) }),
    entradas: (grupo: string | null, texto: string, f: Obj | null, recursivo = false) => {
      if (!texto && !f) { const d = recursivo ? debajo(grupo || 'raiz') : [grupo || 'raiz']; return ok({ lista: entradas.filter((e) => d.includes(e.grupo)).map(resumen) }) }
      const filtros = f ?? {}
      const dentro = debajo((filtros.ambito as string) || 'raiz')
      return ok({ lista: entradas.filter((e) => dentro.includes(e.grupo))
        .filter((e) => !texto || JSON.stringify(e.campos.filter((x) => !x.protegido)).toLowerCase().includes(texto.toLowerCase()))
        .filter((e) => !filtros.servicio || servicios(e).has(String(filtros.servicio)))
        .filter((e) => !filtros.usuario || usuarios(e).has(String(filtros.usuario)))
        .filter((e) => !filtros.tipo || (esId(e) ? 'identidad' : 'entrada') === filtros.tipo)
        .filter((e) => !filtros.estado || val(e, 'Ficha.estado') === filtros.estado)
        .filter((e) => !filtros.alerta || (filtros.alerta === 'cualquiera' ? e.alertas.length > 0 : e.alertas.includes(String(filtros.alerta))))
        .map(resumen) })
    },
    facetas: (ambito: string | null) => { const d = debajo(ambito || 'raiz'); const es = entradas.filter((e) => d.includes(e.grupo))
      return ok({ servicios: [...new Set(es.flatMap((e) => [...servicios(e)]))].sort(), usuarios: [...new Set(es.flatMap((e) => [...usuarios(e)]))].sort() }) },
    salud: () => ok({ salud: salud() }),
    imagen: (_u: string, nombre: string) => (imagenes[nombre] ? ok({ url: imagenes[nombre] }) : Promise.resolve({ ok: false, error: 'no_encontrado' })),
    entrada: (u: string) => ok({ entrada: detalle(por(u), false) }),
    para_editar: (u: string) => ok({ entrada: detalle(por(u), true) }),
    revelar: (u: string, k: string) => ok({ valor: val(por(u), k) }),
    totp: (u: string) => ok({ totp: val(por(u), 'otp') ? { codigo: '482913', restante: 30 - Math.floor(Date.now() / 1000) % 30, periodo: 30 } : null }),
    copiar: () => ok({ nativo: true, segundos: pref.portapapeles_segundos }), copiar_texto: () => ok({ nativo: true, segundos: pref.portapapeles_segundos }),
    crear_entrada: (grupo: string | null, campos: C[], etiquetas: string[]) => { const uuid = 'n' + Date.now(); entradas.push({ uuid, grupo: grupo || 'raiz', campos, etiquetas: etiquetas || [], expira: null, alertas: [], adjuntos: [], historial: [], modificada: new Date().toISOString() }); return ok({ uuid, cambios: false }) },
    editar_entrada: (u: string, campos: C[], etiquetas: string[]) => { const e = por(u); e.historial.push({ titulo: val(e, 'Title'), modificada: e.modificada }); e.campos = campos; e.etiquetas = etiquetas || []; e.modificada = new Date().toISOString(); return ok({ cambios: false }) },
    duplicar_entrada: () => ok(), mover_entrada: (u: string, g2: string) => { por(u).grupo = g2 || 'raiz'; return ok() },
    eliminar_entrada: (u: string) => { por(u).grupo = 'pap'; return ok() },
    restaurar_historial: () => ok(), agregar_adjunto: () => ok(), agregar_imagenes: () => ok(), agregar_adjunto_datos: () => ok({ nombres: [] }),
    guardar_adjunto: () => ok(), quitar_adjunto: () => ok(),
    crear_grupo: () => ok(), renombrar_grupo: () => ok(), mover_grupo: () => ok(), eliminar_grupo: () => ok(), vaciar_papelera: () => ok(),
    preparar_secciones: () => ok({ secciones }), asignar_seccion: () => ok(), fijar_renovacion: (d: number) => { renovar = d; return ok() },
    guardar: () => ok({ info: info() }), guardar_como: () => ok({ info: info() }), ajustar_base: () => ok(), cambiar_clave: () => ok(),
    ajustar_seguridad: () => ok(), convertir_a_kdbx4: () => ok(),
    generar: (o: Obj) => ok(o.modo === 'frase' ? { texto: 'breeder-culture-sixteen-irritate-enviable-sequester', bits: 78 } : { texto: 'GN*7cH?5(zexo5{_$04M;5IZ', bits: 157 }),
    calidad: (t: string) => ok({ bits: Math.min(160, (t || '').length * 6) }),
  } as unknown as Record<string, (...args: unknown[]) => Promise<unknown>>
}
