import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { viteSingleFile } from 'vite-plugin-singlefile'

// Un único index.html con todo dentro (código, estilos, fuentes, escudo): la ventana lo carga como
// file:// y la aplicación no abre ningún puerto ni pide nada a la red.
export default defineConfig({
  plugins: [react(), viteSingleFile()],
  base: './',
  build: { assetsInlineLimit: 100_000_000, cssCodeSplit: false, target: 'es2020', reportCompressedSize: false },
})
