import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  build: {
    outDir: 'dist',
    assetsDir: 'assets',
    sourcemap: false,
    rollupOptions: {
      output: {
        manualChunks: {
          // React must be first and separate
          'react-vendor': ['react', 'react-dom'],
          // UI libraries that depend on React
          'ui-vendor': ['@radix-ui/react-accordion', '@radix-ui/react-avatar', '@radix-ui/react-dialog', '@radix-ui/react-dropdown-menu', '@radix-ui/react-hover-card', '@radix-ui/react-popover', '@radix-ui/react-scroll-area', '@radix-ui/react-separator', '@radix-ui/react-slot', '@radix-ui/react-tooltip'],
          // Chart libraries
          'charts-vendor': ['recharts', '@nivo/bar', '@nivo/core', '@nivo/funnel', 'd3-array'],
          // Animation libraries
          'animation-vendor': ['framer-motion'],
          // State management
          'state-vendor': ['@tanstack/react-query', 'zustand'],
          // Routing
          'router-vendor': ['react-router-dom'],
          // Form libraries
          'form-vendor': ['react-hook-form', '@hookform/resolvers', 'zod'],
          // Tremor UI
          'tremor-vendor': ['@tremor/react'],
          // Icons
          'icons-vendor': ['lucide-react'],
          // Utilities
          'utils-vendor': ['clsx', 'tailwind-merge', 'class-variance-authority'],
        },
        // 청크 크기 제한 설정
        chunkFileNames: (chunkInfo) => {
          const facadeModuleId = chunkInfo.facadeModuleId ? chunkInfo.facadeModuleId.split('/').pop() : 'chunk'
          return `js/[name]-[hash].js`
        },
        assetFileNames: (assetInfo) => {
          const info = assetInfo.name.split('.')
          const ext = info[info.length - 1]
          if (/\.(css)$/.test(assetInfo.name)) {
            return `css/[name]-[hash].${ext}`
          }
          return `assets/[name]-[hash].${ext}`
        }
      },
    },
    // 청크 크기 경고 임계값 조정
    chunkSizeWarningLimit: 1000,
    // 압축 최적화 (esbuild 사용 - 더 빠르고 안정적)
    minify: 'esbuild',
    esbuild: {
      drop: ['console', 'debugger'],
    },
  },
  server: {
    port: 3000,
    proxy: {
      '/analytics': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})
