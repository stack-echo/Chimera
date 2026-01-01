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
import request from '../api/request' // 🔥 引入 axios 实例

const router = useRouter()
const userStore = useUserStore()
const loading = ref(false)

const form = reactive({
  username: 'admin', // 默认填好方便测试
  password: '123',
  role: 'user'
})

const handleLogin = async () => {
  if (!form.username || !form.password) {
    alert('请输入账号密码')
    return
  }

  loading.value = true

  try {
    // 🔥 1. 调用真实后端接口
    const res = await request.post('/auth/login', {
      username: form.username,
      password: form.password
    })

    // 注意：根据你的 Go AuthHandler，返回结构应该是 { token: "...", username: "...", user_id: 1 }
    // 如果你的 request.js 拦截器里没有剥离 data 层，这里可能需要 res.data.token

    // 假设 request.js 拦截器直接返回了 response.data
    const token = res.token
    const user = {
      name: res.username,
      id: res.user_id,
      role: form.role // 暂时前端透传，实际上应该解析 Token 或由后端返回
    }

    // 2. 存入 Pinia 和 LocalStorage
    userStore.login(token, user)

    // 3. 跳转
    if (form.role === 'admin') {
      router.push('/admin/insights') // 直接跳到监控台
    } else {
      router.push('/chat')
    }

  } catch (e) {
    console.error(e)
    alert('登录失败: ' + (e.response?.data?.error || e.message))
  } finally {
    loading.value = false
  }
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