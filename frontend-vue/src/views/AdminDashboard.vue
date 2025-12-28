<template>
  <div class="admin-container">
    <div class="header">
      <h1>⚙️ 组织管理后台</h1>
      <div class="user-info">
        <span>当前身份: {{ userStore.userInfo.role }}</span>
        <button @click="handleLogout" class="logout-btn">退出登录</button>
      </div>
    </div>

    <div class="content">
      <div class="card">
        <h3>👥 成员管理</h3>
        <p>管理组织下的成员及权限 (开发中...)</p>
      </div>
      <div class="card">
        <h3>📚 知识库配置</h3>
        <p>当前组织 KB ID: {{ userStore.currentKbId }}</p>
        <p>在这里配置 MinIO 存储策略和 Qdrant 索引 (开发中...)</p>
      </div>
      <div class="card">
        <h3>📊 用量统计</h3>
        <p>Token 消耗与 API 调用次数 (开发中...)</p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { useUserStore } from '../store/user'
import { useRouter } from 'vue-router'

const userStore = useUserStore()
const router = useRouter()

const handleLogout = () => {
  userStore.logout()
  router.push('/login')
}
</script>

<style scoped>
.admin-container { padding: 20px; background: #f0f2f5; min-height: 100vh; }
.header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 30px; background: white; padding: 15px 20px; border-radius: 8px; }
.logout-btn { background: #ff4d4f; color: white; border: none; padding: 5px 15px; border-radius: 4px; margin-left: 10px; cursor: pointer; }
.content { display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 20px; }
.card { background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.05); }
h3 { margin-top: 0; color: #1890ff; }
</style>