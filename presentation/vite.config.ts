import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import sidecarTail from './vite-plugins/sidecar-tail';
import sidecarSkills from './vite-plugins/sidecar-skills';

export default defineConfig({
  plugins: [react(), sidecarTail(), sidecarSkills()],
  server: {
    host: true,
    port: 5173,
    strictPort: true,
  },
});
