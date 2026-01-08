<template>
  <div class="home-container">
    <!-- 1. 侧边栏 (保持原有逻辑) -->
    <div class="sidebar">
      <div class="brand-area">
        <h2>Chimera RAG</h2>
        <span class="version-tag">v0.6.0 Graph</span>
      </div>

      <div class="context-section">
        <label class="section-label">工作区 (Org)</label>
        <a-select :model-value="userStore.currentOrgId" @change="handleOrgChange" placeholder="切换组织">
          <a-option v-for="org in userStore.userOrgs" :key="org.org_id" :value="org.org_id">
            {{ org.name }}
          </a-option>
        </a-select>
      </div>

      <div class="divider"></div>

      <div class="upload-section">
        <label class="section-label">知识库管理</label>
        <a-upload draggable action="/" :auto-upload="false" @change="onFileChange" />
        <a-button type="primary" long :loading="uploading" @click="triggerUpload" style="margin-top: 10px">
          {{ uploading ? 'ETL 抽取中...' : '上传并构建图谱' }}
        </a-button>
        <div v-if="uploadStatus" :class="['status-msg', uploadStatusType]">{{ uploadStatus }}</div>
      </div>

      <div class="spacer"></div>

      <!-- 用户信息 -->
      <div class="user-profile">
        <a-avatar :style="{ backgroundColor: '#7265e6' }">{{ userStore.userInfo.name?.[0] || 'U' }}</a-avatar>
        <div class="info">
          <div class="username">{{ userStore.userInfo.name || 'User' }}</div>
          <a-link @click="handleLogout" status="danger" size="small">退出登录</a-link>
        </div>
      </div>
    </div>

    <!-- 2. 主区域：采用 Flex 布局实现双栏 -->
    <div class="main-layout">
      <!-- 2.1 左侧：对话流 -->
      <div class="chat-area">
        <header class="chat-header">
          <div class="header-left">
            <h3>{{ userStore.currentOrgName }} 智能助手</h3>
            <a-badge status="success" text="GraphRAG 已就绪" style="margin-left: 10px" />
          </div>
          <a-button size="small" @click="clearHistory">清空对话</a-button>
        </header>

        <!-- 对话内容 -->
        <div class="messages-container" ref="chatContainer">
          <!-- 实时思考状态条 (解决 currentThoughts "unused" 问题) -->
          <div v-if="loading && currentThoughts.length > 0" class="realtime-status">
            <a-alert type="info" show-icon size="mini">
              正在处理: {{ currentThoughts[currentThoughts.length - 1] }}
            </a-alert>
          </div>

          <div v-for="(msg, index) in messages" :key="index" :class="['message-row', msg.role]">
            <div class="avatar-icon">{{ msg.role === 'user' ? '👤' : '🤖' }}</div>
            <div class="message-content">
              <!-- 思考链展示 -->
              <div v-if="msg.thoughts && msg.thoughts.length" class="thought-box">
                <a-collapse :default-active-key="[]" :bordered="false">
                  <a-collapse-item header="查看 AI 思考过程" key="1">
                    <div v-for="(t, i) in msg.thoughts" :key="i" class="thought-step">
                      <icon-search /> {{ t }}
                    </div>
                  </a-collapse-item>
                </a-collapse>
              </div>

              <!-- 正文 -->
              <div class="message-bubble">
                <div class="message-text">{{ msg.content }}</div>
                <span v-if="msg.loading" class="typing-cursor">|</span>
              </div>

              <!-- 引用文献 -->
              <div v-if="msg.references && msg.references.length" class="ref-container">
                <div class="ref-title">📚 参考文献：</div>
                <div class="ref-list">
                  <a-tooltip v-for="(ref, i) in msg.references" :key="i" :content="ref.content">
                    <a-tag size="mini" color="arcoblue" bordered>
                      {{ ref.metadata.file_name }} (P{{ ref.metadata.page_number }})
                    </a-tag>
                  </a-tooltip>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- 输入框 -->
        <div class="input-section">
          <a-input-search
              v-model="query"
              size="large"
              placeholder="请输入问题，支持跨文档深度推理..."
              button-text="发送"
              :loading="loading"
              @search="sendMessage"
              @press-enter="sendMessage"
          />
        </div>
      </div>

      <!-- 2.2 右侧：知识洞察面板 (任务 4.2) -->
      <div class="insight-panel" :class="{ 'collapsed': !currentGraphData.nodes?.length }">
        <div class="panel-header">
          <span class="title">🧠 知识拓扑图谱</span>
          <a-button type="text" size="mini" @click="currentGraphData = { nodes: [], edges: [] }">关闭</a-button>
        </div>
        <div class="graph-wrapper">
          <!-- 引入之前的 KnowledgeGraph 组件 -->
          <KnowledgeGraph :data="currentGraphData" />
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { useUserStore } from '../store/user'
import { IconSearch } from '@arco-design/web-vue/es/icon'
import request from '../api/request'
import KnowledgeGraph from '../components/KnowledgeGraph.vue'

// 1. 初始化
const router = useRouter()
const userStore = useUserStore()
const chatContainer = ref(null)

// 2. 响应式状态
const query = ref('')
const loading = ref(false)
const messages = reactive([])
const uploading = ref(false)
const uploadStatus = ref('')
const uploadStatusType = ref('info')
const fileToUpload = ref(null)

// 🔥 解决 Unused 警告的核心：在模板中渲染它们
const currentGraphData = ref({ nodes: [], edges: [] })
const currentThoughts = ref([])

// 3. 滚动逻辑
const scrollToBottom = async () => {
  await nextTick()
  if (chatContainer.value) {
    chatContainer.value.scrollTop = chatContainer.value.scrollHeight
  }
}

// 4. 对话逻辑 (v0.6.0 多路流解析器)
const sendMessage = async () => {
  if (!query.value.trim() || loading.value) return

  const userQ = query.value
  query.value = ''
  currentThoughts.value = [] // 重置当前思考

  // A. 记录用户消息
  messages.push({ role: 'user', content: userQ })

  // B. 初始化 AI 占位消息
  const aiMsg = reactive({
    role: 'ai',
    content: '',
    thoughts: [],
    references: [],
    loading: true
  })
  messages.push(aiMsg)
  loading.value = true
  scrollToBottom()

  try {
    const response = await fetch('/api/v1/chat/stream', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${userStore.token}`
      },
      body: JSON.stringify({
        query: userQ,
        kb_id: userStore.currentKbId,
        org_id: userStore.currentOrgId,
        stream: true
      })
    })

    if (!response.ok) throw new Error('网络请求异常')

    const reader = response.body.getReader()
    const decoder = new TextDecoder('utf-8')
    let buffer = ""

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const parts = buffer.split('\n\n')
      buffer = parts.pop()

      for (const part of parts) {
        const payload = part.replace(/^data:\s*/, '').trim()
        if (!payload) continue

        // --- 多路分流逻辑 ---
        if (payload.startsWith('THOUGHT: ')) {
          const content = payload.replace('THOUGHT: ', '')
          aiMsg.thoughts.push(content)
          currentThoughts.value.push(content) // 用于顶部状态条
        }
        else if (payload.startsWith('GRAPH: ')) {
          try {
            currentGraphData.value = JSON.parse(payload.replace('GRAPH: ', ''))
          } catch (e) { console.error("图谱解析失败", e) }
        }
        else if (payload.startsWith('REF: ')) {
          try {
            aiMsg.references = JSON.parse(payload.replace('REF: ', ''))
          } catch (e) { console.error("引用解析失败", e) }
        }
        else {
          aiMsg.content += payload // 答案片段
        }
        scrollToBottom()
      }
    }
  } catch (e) {
    aiMsg.content = `[错误]: ${e.message}`
  } finally {
    aiMsg.loading = false
    loading.value = false
  }
}

// 5. 其他辅助逻辑 (保持简洁)
const onFileChange = (fileList) => {
  if (fileList.length > 0) fileToUpload.value = fileList[0].file
}

const triggerUpload = async () => {
  if (!fileToUpload.value) return
  uploading.value = true
  const formData = new FormData()
  formData.append('file', fileToUpload.value)
  formData.append('kb_id', userStore.currentKbId)
  try {
    await request.post('/files/upload', formData)
    uploadStatus.value = "✅ 上传成功，后台正在构建图谱..."
    uploadStatusType.value = "success"
  } catch (e) {
    uploadStatus.value = "❌ 上传失败"
    uploadStatusType.value = "error"
  } finally { uploading.value = false }
}

const handleOrgChange = (val) => {
  const target = userStore.userOrgs.find(o => o.org_id === val)
  if (target) userStore.setContext(target)
  clearHistory()
}

const clearHistory = () => {
  messages.splice(0, messages.length)
  currentGraphData.value = { nodes: [], edges: [] }
}

const handleLogout = () => {
  userStore.logout()
  router.push('/login')
}
</script>

<style scoped>
.home-container { display: flex; height: 100vh; background: #f4f7f9; }
.sidebar { width: 260px; background: #fff; border-right: 1px solid #e5e6eb; padding: 20px; display: flex; flex-direction: column; }
.main-layout { flex: 1; display: flex; overflow: hidden; }

/* 聊天区 */
.chat-area { flex: 1; display: flex; flex-direction: column; background: #fff; }
.chat-header { height: 60px; padding: 0 20px; display: flex; align-items: center; justify-content: space-between; border-bottom: 1px solid #f2f3f5; }
.messages-container { flex: 1; overflow-y: auto; padding: 20px; background: #fafafa; }
.realtime-status { margin-bottom: 15px; }

/* 消息气泡样式增强 */
.message-row { display: flex; margin-bottom: 24px; gap: 12px; }
.message-row.user { flex-direction: row-reverse; }
.message-content { max-width: 80%; }
.message-bubble { padding: 12px 16px; border-radius: 8px; background: #fff; border: 1px solid #e5e6eb; line-height: 1.6; }
.user .message-bubble { background: #165dff; color: #fff; border: none; }

/* 思考链样式 */
.thought-box { margin-bottom: 8px; opacity: 0.8; }
.thought-step { font-size: 12px; color: #86909c; margin-bottom: 4px; }

/* 引用样式 */
.ref-container { margin-top: 10px; padding-top: 10px; border-top: 1px dashed #e5e6eb; }
.ref-title { font-size: 11px; color: #86909c; margin-bottom: 5px; }
.ref-list { display: flex; flex-wrap: wrap; gap: 4px; }

/* 图谱面板 */
.insight-panel { width: 450px; background: #fff; border-left: 1px solid #e5e6eb; transition: all 0.3s; display: flex; flex-direction: column; }
.insight-panel.collapsed { width: 0; opacity: 0; overflow: hidden; }
.panel-header { padding: 15px; border-bottom: 1px solid #f2f3f5; display: flex; justify-content: space-between; }
.graph-wrapper { flex: 1; padding: 10px; }

.input-section { padding: 20px; border-top: 1px solid #f2f3f5; }
.typing-cursor { animation: blink 1s infinite; font-weight: bold; }
@keyframes blink { 50% { opacity: 0; } }
</style>