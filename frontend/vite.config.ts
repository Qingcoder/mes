import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    host: true,          // 监听 0.0.0.0，手机可用局域网 IP 访问
    port: 5173,
    strictPort: true,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8007',
        changeOrigin: true,
      },
    },
  },
})
