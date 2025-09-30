import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import path from 'path'
import { jsxLocPlugin } from '@builder.io/vite-plugin-jsx-loc';

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss(), jsxLocPlugin()],
  resolve: {
    alias: {
      "@": path.resolve(new URL('./src', import.meta.url).pathname),
    }
  }
})
