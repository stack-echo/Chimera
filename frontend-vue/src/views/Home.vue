<template>
  <div class="home-container">
    <div class="sidebar">
      <div class="brand-area">
        <h2>Chimera RAG</h2>
        <span class="version-tag">v0.4.0 SaaS</span>
      </div>

      <div class="context-section">
        <label class="section-label">当前工作区 (Org)</label>
        <select
            :value="userStore.currentOrgId"
            @change="handleOrgChange"
            class="org-selector"
        >
          <option
              v-for="org in userStore.userOrgs"
              :key="org.org_id"
              :value="org.org_id"
          >
            {{ org.name }}
          </option>
        </select>

        <div class="debug-info">
          <small>Org ID: {{ userStore.currentOrgId }}</small>
          <small>KB ID: {{ userStore.currentKbId }}</small>
        </div>
      </div>

      <div class="divider"></div>

      <div class="upload-section">
        <label class="section-label">知识库录入</label>
        <div class="file-drop-zone">
          <input type="file" ref="fileInput" @change="resetUploadStatus" />
        </div>

        <button
            @click="triggerUpload"
            :disabled="uploading || !fileInput?.files?.length"
            class="action-btn upload-btn"
            :class="{ 'processing': uploading }"
        >
          {{ uploading ? '正在解析 ETL...' : '上传并入库' }}
        </button>

        <div v-if="uploadStatus" :class="['status-msg', uploadStatusType]">
          {{ uploadStatus }}
        </div>
      </div>

      <div class="spacer"></div>

      <div class="user-profile">
        <div class="avatar">{{ userStore.userInfo.name?.[0]?.toUpperCase() || 'U' }}</div>
        <div class="info">
          <div class="username">{{ userStore.userInfo.name || 'User' }}</div>
          <button @click="handleLogout" class="logout-link">退出登录</button>
        </div>
      </div>
    </div>

    <div class="main-area">
      <header class="chat-header">
        <div class="header-content">
          <h3>{{ userStore.currentOrgName }} 智能助手</h3>
          <span class="status-badge online">在线</span>
        </div>
        <button @click="clearHistory" class="clear-btn" title="清空对话">
          🗑️ 清空记录
        </button>
      </header>

      <div class="messages-container" ref="chatContainer">
        <div v-if="messages.length === 0" class="empty-state">
          <p>👋 欢迎来到 <b>{{ userStore.currentOrgName }}</b></p>
          <p>请上传文档，或直接提问。</p>
        </div>

        <div
            v-for="(msg, index) in messages"
            :key="index"
            :class="['message-row', msg.role]"
        >
          <div class="avatar">
            {{ msg.role === 'user' ? '👤' : '🤖' }}
          </div>
          <div class="message-bubble">
            <div class="message-text">{{ msg.content }}</div>
            <span v-if="msg.role === 'ai' && msg.loading" class="typing-cursor">|</span>
          </div>
        </div>
      </div>

      <div class="input-section">
        <div class="input-wrapper">
          <input
              v-model="query"
              @keyup.enter="sendMessage"
              :placeholder="`向 ${userStore.currentOrgName} 提问...`"
              :disabled="loading"
          />
          <button @click="sendMessage" :disabled="loading || !query.trim()">
            {{ loading ? '...' : '发送' }}
          </button>
        </div>
        <div class="footer-note">Chimera-RAG 生成的内容可能包含幻觉，请以原文为准。</div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, nextTick, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useUserStore } from '../store/user'
import request from '../api/request' // 用于上传 (Axios)

// 1. 初始化
const router = useRouter()
const userStore = useUserStore()
const chatContainer = ref(null)
const fileInput = ref(null)

// 2. 响应式状态
const query = ref('')
const messages = reactive([])
const loading = ref(false)
const uploading = ref(false)
const uploadStatus = ref('')
const uploadStatusType = ref('info') // info, success, error

// 3. 核心功能：滚动到底部
const scrollToBottom = async () => {
  await nextTick()
  if (chatContainer.value) {
    chatContainer.value.scrollTop = chatContainer.value.scrollHeight
  }
}

// 4. 核心功能：切换组织 (Context Switch)
const handleOrgChange = (e) => {
  const newOrgId = parseInt(e.target.value)
  const targetOrg = userStore.userOrgs.find(o => o.org_id === newOrgId)

  if (targetOrg) {
    // 关键：更新 Pinia 状态
    userStore.setContext(targetOrg)
    // 关键：清空当前对话，防止数据串台
    clearHistory()
    resetUploadStatus()
  }
}

const clearHistory = () => {
  messages.splice(0, messages.length)
}

const handleLogout = () => {
  userStore.logout()
  router.push('/login')
}

// 5. 核心功能：上传文件 (调用 Go 接口)
const resetUploadStatus = () => {
  uploadStatus.value = ''
  uploadStatusType.value = 'info'
}

const triggerUpload = async () => {
  const file = fileInput.value?.files[0]
  if (!file) return

  uploading.value = true
  uploadStatus.value = '📤 正在上传并触发 ETL 解析...'
  uploadStatusType.value = 'info'

  const formData = new FormData()
  formData.append('file', file)
  // 🔥 关键：带上当前的 KB ID，保证传到正确的库
  formData.append('kb_id', userStore.currentKbId)

  try {
    // 使用 axios 实例 (src/api/request.js)
    const res = await request.post('/files/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })

    uploadStatus.value = `✅ 上传成功! 文档ID: ${res.data.doc_id}。后台正在切片入库...`
    uploadStatusType.value = 'success'
    fileInput.value.value = '' // 清空 input
  } catch (e) {
    console.error(e)
    uploadStatus.value = `❌ 上传失败: ${e.response?.data?.msg || e.message}`
    uploadStatusType.value = 'error'
  } finally {
    uploading.value = false
  }
}

// 6. 核心功能：流式对话 (调用 Go -> Python)
// ⚠️ 这里使用原生 fetch，因为 axios 处理流比较麻烦
const sendMessage = async () => {
  if (!query.value.trim() || loading.value) return

  const userQ = query.value
  query.value = '' // 清空输入框

  // 添加用户消息
  messages.push({ role: 'user', content: userQ })
  scrollToBottom()

  // 添加 AI 占位消息
  const aiMsg = reactive({ role: 'ai', content: '', loading: true })
  messages.push(aiMsg)
  loading.value = true

  try {
    const response = await fetch('/api/v1/chat/completions', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        // 🔥 关键：手动添加 Token，因为原生 fetch 不走 axios 拦截器
        'Authorization': `Bearer ${userStore.token}`
      },
      body: JSON.stringify({
        query: userQ,
        kb_id: userStore.currentKbId,  // 必传：当前知识库 ID
        org_id: userStore.currentOrgId, // 必传：当前组织 ID
        stream: true
      })
    })

    if (!response.ok) {
      throw new Error(`请求失败: ${response.statusText}`)
    }

    // 处理流式响应
    const reader = response.body.getReader()
    const decoder = new TextDecoder('utf-8')

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      const chunk = decoder.decode(value, { stream: true })
      // 简单拼接 (如果后端返回的是纯文本流)
      aiMsg.content += chunk
      scrollToBottom()
    }

  } catch (e) {
    aiMsg.content += `\n[系统错误: ${e.message}]`
  } finally {
    aiMsg.loading = false
    loading.value = false
    scrollToBottom()
  }
}
</script>

<style scoped>
/* ================= 布局样式 ================= */
.home-container {
  display: flex;
  height: 100vh;
  background-color: #f5f7fa;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
}

/* --- 侧边栏 --- */
.sidebar {
  width: 280px;
  background: #ffffff;
  border-right: 1px solid #e1e4e8;
  display: flex;
  flex-direction: column;
  padding: 20px;
  box-shadow: 2px 0 5px rgba(0,0,0,0.02);
}

.brand-area {
  margin-bottom: 25px;
  display: flex;
  align-items: center;
  gap: 10px;
}
.brand-area h2 { margin: 0; font-size: 20px; color: #1f2d3d; }
.version-tag { background: #e6f7ff; color: #1890ff; font-size: 10px; padding: 2px 6px; border-radius: 4px; }

.section-label {
  display: block;
  font-size: 12px;
  color: #8492a6;
  margin-bottom: 8px;
  font-weight: 600;
  text-transform: uppercase;
}

.org-selector {
  width: 100%;
  padding: 10px;
  border: 1px solid #dcdfe6;
  border-radius: 6px;
  background-color: #fff;
  font-size: 14px;
  margin-bottom: 5px;
  cursor: pointer;
}
.org-selector:focus { border-color: #1890ff; outline: none; }

.debug-info { font-size: 10px; color: #c0c4cc; display: flex; gap: 10px; margin-bottom: 20px; }

.divider { height: 1px; background: #ebeef5; margin: 10px 0 20px 0; }

.file-drop-zone input { width: 100%; font-size: 12px; }

.action-btn {
  width: 100%;
  padding: 10px;
  border: none;
  border-radius: 6px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.3s;
  margin-top: 10px;
}
.upload-btn { background: #1890ff; color: white; }
.upload-btn:hover { background: #40a9ff; }
.upload-btn:disabled { background: #a0cfff; cursor: not-allowed; }
.upload-btn.processing { cursor: wait; opacity: 0.8; }

.status-msg { font-size: 12px; margin-top: 10px; line-height: 1.4; padding: 8px; border-radius: 4px; }
.status-msg.info { color: #606266; background: #f4f4f5; }
.status-msg.success { color: #67c23a; background: #f0f9eb; }
.status-msg.error { color: #f56c6c; background: #fef0f0; }

.spacer { flex: 1; }

.user-profile {
  display: flex;
  align-items: center;
  gap: 10px;
  padding-top: 15px;
  border-top: 1px solid #ebeef5;
}
.user-profile .avatar {
  width: 36px; height: 36px;
  background: #7265e6; color: white;
  border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  font-weight: bold;
}
.user-profile .info { display: flex; flex-direction: column; }
.user-profile .username { font-weight: 600; font-size: 14px; color: #303133; }
.logout-link { border: none; background: none; color: #909399; font-size: 12px; cursor: pointer; padding: 0; text-align: left; }
.logout-link:hover { color: #f56c6c; }

/* --- 主区域 --- */
.main-area {
  flex: 1;
  display: flex;
  flex-direction: column;
  background: white;
}

.chat-header {
  height: 60px;
  border-bottom: 1px solid #e1e4e8;
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 20px;
}
.chat-header h3 { margin: 0; font-size: 16px; font-weight: 600; }
.status-badge { font-size: 12px; margin-left: 8px; padding: 2px 6px; border-radius: 10px; }
.status-badge.online { background: #e1f3d8; color: #67c23a; }
.clear-btn { background: none; border: 1px solid #dcdfe6; padding: 5px 10px; border-radius: 4px; color: #606266; cursor: pointer; font-size: 12px; }
.clear-btn:hover { border-color: #f56c6c; color: #f56c6c; }

.messages-container {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 20px;
  background: #f9fafc;
}

.empty-state { text-align: center; color: #909399; margin-top: 100px; }

.message-row { display: flex; gap: 12px; max-width: 80%; }
.message-row.user { align-self: flex-end; flex-direction: row-reverse; }
.message-row.ai { align-self: flex-start; }

.message-row .avatar {
  width: 32px; height: 32px;
  background: #fff; border: 1px solid #dcdfe6;
  border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  font-size: 18px;
  flex-shrink: 0;
}
.message-row.user .avatar { background: #d9ecff; border: none; }

.message-bubble {
  padding: 12px 16px;
  border-radius: 8px;
  font-size: 14px;
  line-height: 1.6;
  position: relative;
  box-shadow: 0 1px 2px rgba(0,0,0,0.05);
}
.message-row.user .message-bubble { background: #1890ff; color: white; border-top-right-radius: 2px; }
.message-row.ai .message-bubble { background: white; color: #303133; border: 1px solid #ebeef5; border-top-left-radius: 2px; }

.message-text { white-space: pre-wrap; /* 关键：保留换行 */ word-break: break-word; }

.typing-cursor { display: inline-block; animation: blink 1s infinite; margin-left: 5px; font-weight: bold; }
@keyframes blink { 50% { opacity: 0; } }

.input-section { padding: 20px; border-top: 1px solid #e1e4e8; background: white; }
.input-wrapper { display: flex; gap: 10px; }
.input-wrapper input {
  flex: 1;
  padding: 12px;
  border: 1px solid #dcdfe6;
  border-radius: 6px;
  outline: none;
  font-size: 14px;
}
.input-wrapper input:focus { border-color: #1890ff; }
.input-wrapper button {
  padding: 0 25px;
  background: #1890ff;
  color: white;
  border: none;
  border-radius: 6px;
  font-weight: 600;
  cursor: pointer;
}
.input-wrapper button:disabled { background: #a0cfff; }

.footer-note { text-align: center; font-size: 11px; color: #c0c4cc; margin-top: 10px; }
</style>