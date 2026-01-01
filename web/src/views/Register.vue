<template>
  <div class="register-container">
    <div class="register-card">
      <h2>📝 注册新账号</h2>
      <p class="subtitle">加入 Chimera RAG 智能知识库</p>

      <div class="form-item">
        <label>用户名</label>
        <input v-model="form.username" placeholder="请输入用户名" />
      </div>

      <div class="form-item">
        <label>邮箱 (账号)</label>
        <input v-model="form.email" placeholder="user@example.com" />
      </div>

      <div class="form-item">
        <label>密码</label>
        <input v-model="form.password" type="password" placeholder="设置密码" />
      </div>

      <div class="form-item">
        <label>注册角色</label>
        <select v-model="form.role">
          <option value="user">普通用户 (User)</option>
          <option value="admin">组织管理员 (Admin)</option>
        </select>
      </div>

      <button @click="handleRegister" :disabled="loading" class="submit-btn">
        {{ loading ? '提交中...' : '立即注册' }}
      </button>

      <div class="footer-link">
        已有账号？ <router-link to="/login">去登录</router-link>
      </div>
    </div>
  </div>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import request from '../api/request' // 使用配置好的 axios

const router = useRouter()
const loading = ref(false)

const form = reactive({
  username: '',
  email: '',
  password: '',
  role: 'user'
})

const handleRegister = async () => {
  // 简单的非空校验
  if (!form.username || !form.email || !form.password) {
    alert('请填写完整信息')
    return
  }

  loading.value = true
  try {
    // 🔥 调用 Go 后端注册接口
    // 请确认你的 Go 路由是 /auth/register 还是 /register
    await request.post('/auth/register', {
      username: form.username,
      email: form.email,
      password: form.password,
      role: form.role // 如果后端支持直接传角色
    })

    alert('✅ 注册成功！请登录。')
    router.push('/login') // 跳转去登录
  } catch (e) {
    console.error(e)
    alert('注册失败: ' + (e.response?.data?.msg || e.message))
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.register-container { display: flex; justify-content: center; align-items: center; height: 100vh; background: #2c3e50; }
.register-card { width: 350px; background: white; padding: 30px; border-radius: 10px; box-shadow: 0 4px 20px rgba(0,0,0,0.2); }
h2 { text-align: center; margin-bottom: 5px; color: #333; }
.subtitle { text-align: center; color: #666; font-size: 0.9em; margin-bottom: 20px; }
.form-item { margin-bottom: 15px; }
.form-item label { display: block; margin-bottom: 5px; font-weight: bold; font-size: 14px; }
input, select { width: 100%; padding: 10px; box-sizing: border-box; border: 1px solid #ddd; border-radius: 4px; }
.submit-btn { width: 100%; padding: 12px; background: #1890ff; color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 16px; font-weight: bold; margin-top: 10px;}
.submit-btn:hover { background: #40a9ff; }
.footer-link { margin-top: 15px; text-align: center; font-size: 14px; }
.footer-link a { color: #1890ff; text-decoration: none; }
</style>