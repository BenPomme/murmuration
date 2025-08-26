import { defineConfig } from 'vite'
import { resolve } from 'path'

// https://vitejs.dev/config/
export default defineConfig({
  resolve: {
    alias: {
      '@': resolve(__dirname, './src'),
      '@/scenes': resolve(__dirname, './src/scenes'),
      '@/systems': resolve(__dirname, './src/systems'),
      '@/types': resolve(__dirname, './src/types'),
      '@/utils': resolve(__dirname, './src/utils'),
      '@/config': resolve(__dirname, './src/config'),
    },
  },
  server: {
    port: 3000,
    open: true,
    host: 'localhost',
    cors: true,
    hmr: {
      overlay: true,
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: true,
    minify: 'esbuild',
    target: 'es2020',
    cssCodeSplit: true,
    rollupOptions: {
      input: {
        main: resolve(__dirname, 'index.html'),
      },
      output: {
        manualChunks: {
          phaser: ['phaser'],
        },
        chunkFileNames: 'assets/[name]-[hash].js',
        entryFileNames: 'assets/[name]-[hash].js',
        assetFileNames: 'assets/[name]-[hash].[ext]',
      },
    },
    // Increase chunk size warning limit for Phaser
    chunkSizeWarningLimit: 1000,
  },
  // Optimize dependency pre-bundling for Phaser
  optimizeDeps: {
    include: ['phaser'],
    exclude: [],
  },
  define: {
    // Define environment variables for production builds
    __DEV__: JSON.stringify(process.env.NODE_ENV !== 'production'),
  },
  // Enable CSS preprocessing
  css: {
    devSourcemap: true,
    preprocessorOptions: {
      // Add any CSS preprocessor options here if needed
    },
  },
})