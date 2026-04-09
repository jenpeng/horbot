import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  build: {
    minify: 'terser',
    cssCodeSplit: true,
    sourcemap: false,
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (!id.includes('node_modules') && !id.includes('/src/')) {
            return undefined;
          }

          if (id.includes('node_modules/react/') || id.includes('node_modules/react-dom/')) {
            return 'react';
          }

          if (id.includes('node_modules/react-router') || id.includes('node_modules/@remix-run/')) {
            return 'router';
          }

          if (id.includes('node_modules/lucide-react')) {
            return 'icons';
          }

          if (id.includes('node_modules/axios')) {
            return 'network';
          }

          if (id.includes('/src/services/webmcp/') || id.includes('/src/hooks/useWebMCPTools.ts')) {
            return 'webmcp';
          }

          if (id.includes('/src/services/skills.ts') || id.includes('/src/pages/SkillsPage.tsx')) {
            return 'skills';
          }

          if (id.includes('/src/hooks/useConfigurationState.ts') || id.includes('/src/pages/ConfigPage.tsx')) {
            return 'config';
          }

          return undefined;
        },
      },
    },
  },
  server: {
    port: 3000,
    host: true,
    hmr: {
      overlay: true,
    },
    watch: {
      usePolling: true,
      interval: 100,
    },
    proxy: {
      '/api/chat/stream': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        configure: (proxy, _options) => {
          proxy.on('error', (err, _req, _res) => {
            console.log('[Proxy Error]', err);
          });
          proxy.on('proxyReq', (proxyReq, req, _res) => {
            console.log('[Proxy Request]', req.url);
            proxyReq.setHeader('Cache-Control', 'no-cache');
            proxyReq.setHeader('Connection', 'keep-alive');
          });
          proxy.on('proxyRes', (proxyRes, req, _res) => {
            console.log('[Proxy Response]', proxyRes.statusCode, req.url);
          });
        },
      },
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/ws': {
        target: 'ws://localhost:8000',
        ws: true,
      },
    },
  },
})
