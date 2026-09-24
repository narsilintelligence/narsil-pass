// Iconos monocromos de trazo, dibujados para NARSIL Pass (sin dependencias). Heredan el color del
// texto: se tiñen con la paleta desde CSS, nunca con colores propios.
const TRAZOS: Record<string, string> = {
  candado: 'M6 11h12v9H6z M8.5 11V8a3.5 3.5 0 0 1 7 0v3',
  llave: 'M14.5 9.5a4 4 0 1 1-1.2-2.8 M13.3 11.8L20 18.5 M17 15.5l2-2 M18.5 17l1.5-1.5',
  carpeta: 'M3 7h6l2 2h10v10H3z',
  mas: 'M12 5v14 M5 12h14',
  lupa: 'M11 17a6 6 0 1 0 0-12 6 6 0 0 0 0 12z M15.5 15.5L20 20',
  copiar: 'M9 9h10v11H9z M5 15V4h10',
  ojo: 'M2.5 12s3.5-6.5 9.5-6.5S21.5 12 21.5 12 18 18.5 12 18.5 2.5 12 2.5 12z M12 14.5a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5z',
  ojo_cerrado: 'M3 3l18 18 M10.6 5.6C11 5.5 11.5 5.5 12 5.5c6 0 9.5 6.5 9.5 6.5a17 17 0 0 1-3 3.8 M6.4 6.6A17 17 0 0 0 2.5 12s3.5 6.5 9.5 6.5c1.6 0 3-.5 4.2-1.1',
  papelera: 'M4 7h16 M9 7V4h6v3 M6 7l1 13h10l1-13',
  lapiz: 'M4 20h4L19 9l-4-4L4 16z M13.5 6.5l4 4',
  reloj: 'M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18z M12 7v5l3 2',
  disco: 'M5 4h11l3 3v13H5z M8 4v5h7V4 M8 20v-6h8v6',
  ajustes: 'M4 7h9 M17 7h3 M4 17h3 M11 17h9 M15 5v4 M9 15v4',
  dado: 'M5 5h14v14H5z M9 9h.01 M15 9h.01 M12 12h.01 M9 15h.01 M15 15h.01',
  usuario: 'M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8z M5 20c0-3.5 3-6 7-6s7 2.5 7 6',
  identidad: 'M3 6h18v12H3z M8.5 12a2 2 0 1 0 0-4 2 2 0 0 0 0 4z M5.5 16c.4-1.5 1.6-2.5 3-2.5s2.6 1 3 2.5 M14 10h4 M14 13h4',
  globo: 'M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18z M3 12h18 M12 3c2.5 2.5 3.5 5.5 3.5 9s-1 6.5-3.5 9c-2.5-2.5-3.5-5.5-3.5-9s1-6.5 3.5-9z',
  clip: 'M20 11.5l-8 8a5 5 0 0 1-7-7l8.5-8.5a3.3 3.3 0 0 1 4.7 4.7L9.7 17.2a1.7 1.7 0 0 1-2.4-2.4L15 7',
  historial: 'M3.5 12a8.5 8.5 0 1 0 2.5-6 M3.5 4.5V9H8 M12 8v4.5l3 1.5',
  salir: 'M10 4H5v16h5 M15 8l4 4-4 4 M19 12H9',
  derecha: 'M9 6l6 6-6 6',
  abajo: 'M6 9l6 6 6-6',
  cerrar: 'M6 6l12 12 M18 6L6 18',
  ok: 'M5 12.5l4.5 4.5L19 7.5',
  aviso: 'M12 4l9.5 16h-19z M12 10v4.5 M12 17.5h.01',
  mover: 'M4 12h13 M13 7l5 5-5 5',
  duplicar: 'M8 8h11v11H8z M5 16V5h11 M13.5 11v5 M11 13.5h5',
  refrescar: 'M20 11a8 8 0 1 0-2.3 5.7 M20 4v7h-7',
  papel: 'M6 3h9l4 4v14H6z M14 3v5h5',
  edificio: 'M4 21V5l8-2v18 M12 8h8v13 M7 8h2 M7 12h2 M7 16h2 M15 12h2 M15 16h2 M3 21h18',
  capas: 'M12 3l9 5-9 5-9-5z M3 13l9 5 9-5 M3 17l9 5 9-5',
  escudo: 'M12 3l8 3v6c0 4.5-3.4 8-8 9-4.6-1-8-4.5-8-9V6z M8.5 12l2.5 2.5 4.5-5',
  filtro: 'M4 5h16l-6 7.5V19l-4 2v-8.5z',
  teclado: 'M3 7h18v11H3z M7 11h.01 M11 11h.01 M15 11h.01 M7 14.5h10',
  imagen: 'M4 5h16v14H4z M4 16l5-5 4 4 3-3 4 4 M15 9.5h.01',
  izquierda: 'M15 6l-6 6 6 6',
}

export function Icono({ nombre, tamano = 16, className }: { nombre: keyof typeof TRAZOS | string; tamano?: number; className?: string }) {
  return (
    <svg className={className} width={tamano} height={tamano} viewBox="0 0 24 24" fill="none" stroke="currentColor"
         strokeWidth={1.7} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" focusable="false">
      <path d={TRAZOS[nombre] ?? ''} />
    </svg>
  )
}
