<template>
  <div class="insight-container">
    <!-- 1. 顶部栏：增加版本标识 -->
    <div class="header-actions">
      <h2>📊 Chimera 运营看板 <a-tag color="arcoblue">v0.6.0 Enterprise</a-tag></h2>
      <div class="filters">
        <a-select
            v-model="currentApp"
            style="width: 200px"
            placeholder="选择应用"
            @change="handleAppChange"
        >
          <a-option v-for="opt in appOptions" :key="opt.value" :value="opt.value">
            {{ opt.label }}
          </a-option>
        </a-select>
        <a-button type="primary" @click="fetchData">
          <template #icon><icon-refresh /></template>刷新数据
        </a-button>
      </div>
    </div>

    <!-- 2. 核心指标卡片：引入知识资产维度 -->
    <a-grid :cols="4" :col-gap="16" class="stat-cards">
      <a-grid-item>
        <a-card hoverable>
          <a-statistic title="总 Token 消耗" :value="stats.total_tokens" show-group-separator>
            <template #prefix>🪙</template>
          </a-statistic>
        </a-card>
      </a-grid-item>
      <a-grid-item>
        <a-card hoverable>
          <a-statistic title="知识分片数 (Chunks)" :value="stats.total_chunks" show-group-separator>
            <template #prefix><icon-layers /></template>
          </a-statistic>
        </a-card>
      </a-grid-item>
      <a-grid-item>
        <a-card hoverable>
          <div class="density-box">
            <div class="label">知识密度 (Nodes/Chunk)</div>
            <div class="content">
              <a-progress type="circle" :percent="Math.min(stats.knowledge_density / 10, 1)" :show-text="false" size="mini" />
              <span class="value">{{ stats.knowledge_density.toFixed(1) }}</span>
            </div>
          </div>
        </a-card>
      </a-grid-item>
      <a-grid-item>
        <a-card hoverable>
          <a-statistic title="平均耗时" :value="stats.avg_duration_ms" :precision="0">
            <template #prefix>⏱️</template>
            <template #suffix>ms</template>
          </a-statistic>
        </a-card>
      </a-grid-item>
    </a-grid>

    <!-- 3. 趋势与分布图表 -->
    <div class="charts-row">
      <a-card class="chart-card main-chart" title="推理成本与 Token 消耗趋势">
        <div class="chart-box">
          <v-chart :option="tokenChartOption" autoresize />
        </div>
      </a-card>
      <a-card class="chart-card sub-chart" title="检索召回模式分布">
        <div class="chart-box">
          <v-chart :option="recallChartOption" autoresize />
        </div>
      </a-card>
    </div>

    <!-- 4. 详细日志表格：增加检索模式标识 -->
    <a-card class="table-card" title="运行日志 (Run History)">
      <a-table
          :data="logs"
          :pagination="pagination"
          @page-change="handlePageChange"
          :loading="loading"
      >
        <template #columns>
          <a-table-column title="时间" data-index="created_at">
            <template #cell="{ record }">
              {{ new Date(record.created_at).toLocaleString() }}
            </template>
          </a-table-column>
          <a-table-column title="检索模式">
            <template #cell="{ record }">
              <!-- 根据 Token 消耗或后端返回的标识判断是否开启了图增强 -->
              <a-tag v-if="record.total_tokens > 800" color="orange" size="small">
                <template #icon><icon-share-alt /></template>Graph-Enhanced
              </a-tag>
              <a-tag v-else color="green" size="small">Vector-Only</a-tag>
            </template>
          </a-table-column>
          <a-table-column title="Query" data-index="query" ellipsis tooltip />
          <a-table-column title="Tokens" data-index="total_tokens" />
          <a-table-column title="耗时" data-index="duration_ms">
            <template #cell="{ record }">
              <a-tag :color="record.duration_ms > 5000 ? 'orange' : 'green'">
                {{ (record.duration_ms / 1000).toFixed(2) }}s
              </a-tag>
            </template>
          </a-table-column>
          <a-table-column title="操作">
            <template #cell="{ record }">
              <a-space>
                <a-button size="mini" type="text" @click="viewDetail(record)">详情</a-button>
                <a-button size="mini" type="text" @click="jumpToSigNoz(record.trace_id)">
                  <icon-link /> Trace
                </a-button>
              </a-space>
            </template>
          </a-table-column>
        </template>
      </a-table>
    </a-card>

    <!-- 5. 详情抽屉 (保留并增强) -->
    <a-drawer
        :visible="drawerVisible"
        @ok="drawerVisible = false"
        @cancel="drawerVisible = false"
        width="600px"
        :footer="false"
    >
      <template #title>
        🔍 链路追踪详情 (ID: {{ currentLog.trace_id || 'N/A' }})
      </template>

      <div v-if="currentLog" class="detail-content">
        <a-descriptions :column="2" bordered title="基础运行指标">
          <a-descriptions-item label="用户">{{ currentLog.user }}</a-descriptions-item>
          <a-descriptions-item label="状态">
            <a-badge :status="currentLog.status === 'success' ? 'success' : 'danger'" :text="currentLog.status" />
          </a-descriptions-item>
          <a-descriptions-item label="总耗时">{{ currentLog.duration_ms }} ms</a-descriptions-item>
          <a-descriptions-item label="Token 消耗">{{ currentLog.total_tokens }}</a-descriptions-item>
          <a-descriptions-item label="Trace ID" :span="2">
            <a-typography-paragraph copyable>{{ currentLog.trace_id }}</a-typography-paragraph>
          </a-descriptions-item>
        </a-descriptions>

        <a-divider />

        <h3>🗣️ 对话快照</h3>
        <div class="chat-snapshot">
          <div class="chat-bubble user">
            <div class="role-label">User Query</div>
            <div class="bubble-content">{{ currentLog.query }}</div>
          </div>
          <div class="chat-bubble ai">
            <div class="role-label">AI Response</div>
            <div class="bubble-content">{{ currentLog.answer || '(流式生成未完全记录)' }}</div>
          </div>
        </div>

        <a-divider />

        <a-collapse>
          <a-collapse-item header="🛠️ 原始调试信息 (Raw Metadata)" key="1">
            <pre class="json-box">{{ JSON.stringify(currentLog, null, 2) }}</pre>
          </a-collapse-item>
        </a-collapse>
      </div>
    </a-drawer>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { getAppStats, getLogList } from '../api/insight'
import {
  IconRefresh, IconLayers, IconShareAlt, IconLink, IconDice, IconHistory
} from '@arco-design/web-vue/es/icon'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart, PieChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, TitleComponent, LegendComponent } from 'echarts/components'

use([CanvasRenderer, LineChart, PieChart, GridComponent, TooltipComponent, TitleComponent, LegendComponent])

const loading = ref(false)
const drawerVisible = ref(false)
const currentLog = ref({})
const currentApp = ref('default_chat_app')

const appOptions = ref([
  { label: '默认对话应用', value: 'default_chat_app' },
])

const stats = reactive({
  total_tokens: 0,
  total_calls: 0,
  avg_duration_ms: 0,
  total_chunks: 0,       // v0.6.0
  knowledge_density: 0,  // v0.6.0
  success_rate: 100
})

const logs = ref([])
const pagination = reactive({ current: 1, pageSize: 10, total: 0 })

const tokenChartOption = ref({})
const recallChartOption = ref({})

const fetchData = async () => {
  loading.value = true
  try {
    const statsRes = await getAppStats({ app_id: currentApp.value, days: 7 })
    const sData = statsRes.data || {}

    // 映射数据
    stats.total_tokens = sData.total_tokens || 0
    stats.total_calls = sData.total_calls || 0
    stats.avg_duration_ms = sData.avg_duration_ms || 0
    stats.total_chunks = sData.total_chunks || 0
    stats.knowledge_density = sData.knowledge_density || 0

    renderCharts(sData.daily_stats || [])

    const logRes = await getLogList({
      page: pagination.current,
      page_size: pagination.pageSize,
      app_id: currentApp.value
    })
    logs.value = logRes.data.list || []
    pagination.total = logRes.data.total || 0
  } catch (e) {
    console.error("加载监控数据失败:", e)
  } finally {
    loading.value = false
  }
}

const renderCharts = (dailyData) => {
  // 1. 趋势折线图
  tokenChartOption.value = {
    tooltip: { trigger: 'axis' },
    xAxis: { type: 'category', data: dailyData.map(d => d.date) },
    yAxis: { type: 'value', name: 'Tokens' },
    series: [{
      data: dailyData.map(d => d.tokens),
      type: 'line',
      smooth: true,
      areaStyle: { opacity: 0.1 },
      itemStyle: { color: '#1890ff' }
    }]
  }

  // 2. 召回比例分布 (模拟数据，实际可从后端聚合获取)
  recallChartOption.value = {
    tooltip: { trigger: 'item' },
    legend: { bottom: '0', icon: 'circle' },
    series: [{
      type: 'pie',
      radius: ['40%', '70%'],
      avoidLabelOverlap: false,
      itemStyle: { borderRadius: 10, borderColor: '#fff', borderWidth: 2 },
      label: { show: false },
      data: [
        { value: 72, name: '纯向量召回' },
        { value: 28, name: '图谱认知增强' }
      ]
    }]
  }
}

const jumpToSigNoz = (traceId) => {
  if (!traceId) return
  // 指向你 docker-compose 中 signoz 的查询地址
  window.open(`http://localhost:3301/trace/${traceId}`)
}

const handlePageChange = (page) => {
  pagination.current = page
  fetchData()
}

const viewDetail = (record) => {
  currentLog.value = record
  drawerVisible.value = true
}

const handleAppChange = () => {
  pagination.current = 1
  fetchData()
}

onMounted(fetchData)
</script>

<style scoped>
.insight-container { padding: 20px; background: #f0f2f5; min-height: 100vh; }
.header-actions { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
.stat-cards { margin-bottom: 20px; }

/* 知识密度自定义样式 */
.density-box { display: flex; flex-direction: column; height: 100%; justify-content: center; }
.density-box .label { font-size: 13px; color: #86909c; margin-bottom: 8px; }
.density-box .content { display: flex; align-items: center; gap: 15px; }
.density-box .value { font-size: 24px; font-weight: bold; color: #1d2129; }

.charts-row { display: grid; grid-template-columns: 2fr 1fr; gap: 16px; margin-bottom: 20px; }
.chart-box { height: 320px; }

.chat-snapshot { background: #f8f9fa; padding: 15px; border-radius: 8px; }
.chat-bubble { margin-bottom: 15px; }
.role-label { font-size: 12px; color: #999; margin-bottom: 4px; font-weight: bold; }
.bubble-content { padding: 10px; border-radius: 6px; font-size: 14px; line-height: 1.5; white-space: pre-wrap; background: #fff; border: 1px solid #e5e6eb; }
.user .bubble-content { background: #e6f7ff; border-color: #91d5ff; }

.json-box { background: #232323; color: #a9d1ff; padding: 12px; border-radius: 4px; font-size: 12px; overflow-x: auto; }
</style>