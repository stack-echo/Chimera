<template>
  <div class="login-container">
    <div class="login-card">
      <h2>Chimera RAG</h2>
      <p class="subtitle">企业级多租户知识库系统 v0.4.0</p>

      <div class="form-item">
        <label>账号</label>
        <input v-model="form.username" placeholder="admin / user" />
      </div>

      <div class="form-item">
        <label>密码</label>
        <input v-model="form.password" type="password" />
      </div>

      <div class="role-selector">
        <label>登录身份：</label>
        <div class="radio-group">
          <label>
            <input type="radio" v-model="form.role" value="user" />
            普通用户 (对话)
          </label>
          <label>
            <input type="radio" v-model="form.role" value="admin" />
            组织管理员 (管理)
          </label>
        </div>
      </div>

      <button @click="handleLogin" :disabled="loading">
        {{ loading ? '登录中...' : '登 录' }}
      </button>
      <div style="margin-top: 15px; text-align: center; font-size: 14px;">
        还没有账号？ <router-link to="/register" style="color: #42b983;">立即注册</router-link>
      </div>
    </div>
  </div>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useUserStore } from '../store/user'
// import request from '../api/request'

const router = useRouter()
const userStore = useUserStore()
const loading = ref(false)

const form = reactive({
  username: 'admin',
  password: '123',
  role: 'user' // 默认为普通用户
})

const handleLogin = async () => {
  loading.value = true

  // 模拟 API 请求延时
  setTimeout(() => {
    // 假设这是后端返回的数据
    const mockResponse = {
      token: 'mock-jwt-token-xyz',
      user: {
        id: 1,
        name: form.username,
        role: form.role // 后端告诉我们这个用户是什么角色
      }
    }

    // 1. 调用 Store 更新状态
    userStore.login(mockResponse.token, mockResponse.user)

    // 2. 根据角色路由分流
    if (form.role === 'admin') {
      alert('欢迎管理员！即将进入控制台...')
      router.push('/admin')
    } else {
      alert('欢迎回来！即将进入对话工作台...')
      router.push('/chat') // 也就是之前的 Home.vue
    }

    loading.value = false
  }, 800)
}
</script>

<style scoped>
.login-container { display: flex; justify-content: center; align-items: center; height: 100vh; background: #2c3e50; }
.login-card { width: 350px; background: white; padding: 30px; border-radius: 10px; box-shadow: 0 4px 20px rgba(0,0,0,0.2); }
h2 { text-align: center; margin-bottom: 5px; color: #333; }
.subtitle { text-align: center; color: #666; font-size: 0.9em; margin-bottom: 20px; }
.form-item { margin-bottom: 15px; }
.form-item label { display: block; margin-bottom: 5px; font-weight: bold; }
input[type="text"], input[type="password"] { width: 100%; padding: 10px; box-sizing: border-box; border: 1px solid #ddd; border-radius: 4px; }
.role-selector { margin-bottom: 20px; background: #f8f9fa; padding: 10px; border-radius: 4px; }
.radio-group { display: flex; gap: 15px; margin-top: 5px; }
button { width: 100%; padding: 12px; background: #42b983; color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 16px; font-weight: bold; }
button:hover { background: #3aa876; }
</style>