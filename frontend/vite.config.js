import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// Bibliotecas, icones e logos em arquivos proprios: mudam pouco, entao o
// navegador os guarda em cache entre um deploy e outro e so baixa de novo o
// codigo do app (varredura: antes era um arquivo unico de 521 KB).
function chunks(id) {
  if (id.includes('node_modules/lucide-react')) return 'icones';
  if (id.includes('node_modules/react') || id.includes('node_modules/scheduler')) return 'react';
  if (id.includes('src/serviceLogos')) return 'logos';
  return undefined;
}

export default defineConfig({
  plugins: [react()],
  server: { proxy: { '/api': 'http://127.0.0.1:5050' } },
  build: { rollupOptions: { output: { manualChunks: chunks } } },
});
