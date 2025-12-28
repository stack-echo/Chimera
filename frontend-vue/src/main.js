// src/main.js
import { createApp } from 'vue'
import App from './App.vue'

// 🔥 1. 引入 Router 和 Pinia
import router from './router'
import { createPinia } from 'pinia'

const app = createApp(App)

// 🔥 2. 挂载插件
app.use(createPinia()) // 启用 Store
app.use(router)        // 启用路由

// 3. 挂载应用
app.mount('#app')