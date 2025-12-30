// src/main.js
import { createApp } from 'vue'
import App from './App.vue'
import router from './router'
import { createPinia } from 'pinia'

// 🔥 1. 引入 Arco Design 及其样式
import ArcoVue from '@arco-design/web-vue';
import '@arco-design/web-vue/dist/arco.css'; // 务必引入 CSS，否则是一堆乱码

const app = createApp(App)

app.use(createPinia())
app.use(router)

// 🔥 2. 挂载 Arco
app.use(ArcoVue);

app.mount('#app')