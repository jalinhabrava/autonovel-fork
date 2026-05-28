import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'node:path';

export default defineConfig({
  plugins: [react()],
  build: {
    outDir: path.resolve(__dirname, '../static/react-shell'),
    emptyOutDir: true,
    rollupOptions: {
      input: path.resolve(__dirname, 'src/main.tsx'),
      output: {
        entryFileNames: 'app.js',
        assetFileNames: 'app.css',
      },
    },
  },
});
