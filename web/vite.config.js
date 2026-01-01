import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    // 端口号可以固定一下，方便记忆
    port: 3000,
    // 代理配置：解决跨域
    proxy: {
      '/api': {
        target: 'http://localhost:8080', // 指向你的 Go 后端
        changeOrigin: true,
        // rewrite: (path) => path.replace(/^\/api/, '') // 你的后端路由本身就有 /api，所以这里不需要 rewrite
      }
    }
  }
})