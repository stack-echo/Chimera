<template>
  <div class="insight-container">
    <!-- 1. 顶部栏 -->
    <div class="header-actions">
      <h2>📊 监控中台 (Chimera Insight)</h2>
      <div class="filters">
        <a-select
            v-model="currentApp"
            style="width: 200px"
            placeholder="选择应用"
            @change="handleAppChange"
        >
          <a-option
              v-for="opt in appOptions"
              :key="opt.value"
              :value="opt.value"
          >
            {{ opt.label }}
          </a-option>
        </a-select>
        <a-range-picker style="width: 250px" disabled /> <!-- 预留 -->
        <a-button type="primary" @click="fetchData">刷新</a-button>
      </div>
    </div>

    <!-- 2. 核心指标卡片 -->
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
          <a-statistic title="总调用次数" :value="stats.total_calls" show-group-separator>
            <template #prefix>🤖</template>
          </a-statistic>
        </a-card>
      </a-grid-item>
      <a-grid-item>
        <a-card hoverable>
          <a-statistic title="平均耗时 (ms)" :value="stats.avg_duration_ms" :precision="0">
            <template #prefix>⏱️</template>
            <template #suffix>ms</template>
          </a-statistic>
        </a-card>
      </a-grid-item>
      <a-grid-item>
        <a-card hoverable>
          <a-statistic title="成功率" :value="stats.success_rate" :precision="1">
            <template #prefix>✅</template>
            <template #suffix>%</template>
          </a-statistic>
        </a-card>
      </a-grid-item>
    </a-grid>

    <!-- 3. 趋势图表 -->
    <a-card class="chart-card" title="近 7 天 Token 消耗趋势">
      <div style="height: 300px">
        <v-chart :option="chartOption" autoresize />
      </div>
    </a-card>

    <!-- 4. 详细日志表格 -->
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
          <a-table-column title="用户" data-index="user" />
          <a-table-column title="Query" data-index="query" ellipsis tooltip />
          <a-table-column title="Tokens" data-index="total_tokens" />
          <a-table-column title="耗时" data-index="duration_ms">
            <template #cell="{ record }">
              <a-tag :color="record.duration_ms > 5000 ? 'orange' : 'green'">
                {{ (record.duration_ms / 1000).toFixed(2) }}s
              </a-tag>
            </template>
          </a-table-column>
          <a-table-column title="状态" data-index="status">
            <template #cell="{ record }">
              <a-badge :status="record.status === 'success' ? 'success' : 'danger'" :text="record.status" />
            </template>
          </a-table-column>
          <a-table-column title="操作">
            <template #cell="{ record }">
              <a-button size="mini" @click="viewDetail(record)">详情</a-button>
            </template>
          </a-table-column>
        </template>
      </a-table>
    </a-card>
    <!-- 🔥 新增：详情抽屉 -->
    <a-drawer
        :visible="drawerVisible"
        @ok="drawerVisible = false"
        @cancel="drawerVisible = false"
        width="600px"
        :footer="false"
    >
      <template #title>
        🔍 链路详情 (Trace: {{ currentLog.trace_id || 'N/A' }})
      </template>

      <div v-if="currentLog" class="detail-content">
        <!-- 1. 概览信息 -->
        <a-descriptions :column="2" bordered title="基础指标">
          <a-descriptions-item label="用户">{{ currentLog.user }}</a-descriptions-item>
          <a-descriptions-item label="状态">
            <a-tag :color="currentLog.status === 'success' ? 'green' : 'red'">
              {{ currentLog.status }}
            </a-tag>
          </a-descriptions-item>
          <a-descriptions-item label="总耗时">{{ currentLog.duration_ms }} ms</a-descriptions-item>
          <a-descriptions-item label="Token 消耗">{{ currentLog.total_tokens }}</a-descriptions-item>
        </a-descriptions>

        <a-divider />

        <!-- 2. 对话还原 -->
        <h3>🗣️ 对话快照</h3>
        <div class="chat-snapshot">
          <div class="chat-bubble user">
            <div class="role-label">User</div>
            <div class="bubble-content">{{ currentLog.query }}</div>
          </div>
          <div class="chat-bubble ai">
            <div class="role-label">AI Agent</div>
            <div class="bubble-content">{{ currentLog.answer || '(无回答内容)' }}</div>
          </div>
        </div>

        <a-divider />

        <!-- 3. 技术细节 (JSON) -->
        <a-collapse>
          <a-collapse-item header="🛠️ 原始元数据 (Meta Info)" key="1">
            <pre class="json-box">{{ currentLog }}</pre>
          </a-collapse-item>
        </a-collapse>
      </div>
    </a-drawer>
  </div> <!-- 结束 div -->
</template>


<script setup>
import { ref, reactive, onMounted, computed } from 'vue'
import { getAppStats, getLogList } from '../api/insight'
// ECharts 引用保持不变...
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, TitleComponent } from 'echarts/components'

use([CanvasRenderer, LineChart, GridComponent, TooltipComponent, TitleComponent])

// --- 状态定义 ---
const loading = ref(false)
const drawerVisible = ref(false)
const currentLog = ref({})

// 1. 应用列表 (动态化)
const currentApp = ref('default_chat_app')
const appOptions = ref([
  { label: '默认对话应用', value: 'default_chat_app' },
  // 可以在这里扩展，或者从后端 /api/v1/apps 接口拉取
])

// 2. 核心指标 (动态化)
const stats = reactive({
  total_tokens: 0,
  total_calls: 0,
  avg_duration_ms: 0,
  success_rate: 100 // 🔥 新增
})

const logs = ref([])
const pagination = reactive({
  current: 1,
  pageSize: 10,
  total: 0
})

const chartOption = ref({})

// --- 方法定义 ---

// 获取综合数据
const fetchData = async () => {
  loading.value = true
  try {
    // A. 获取统计数据 (后端计算)
    const statsRes = await getAppStats({ app_id: currentApp.value, days: 7 })
    const sData = statsRes.data || {} // 防空

    stats.total_tokens = sData.total_tokens || 0
    stats.total_calls = sData.total_calls || 0
    stats.avg_duration_ms = sData.avg_duration_ms || 0

    // 渲染图表
    renderChart(sData.daily_stats || [])

    // B. 获取日志列表
    const logRes = await getLogList({
      page: pagination.current,
      page_size: pagination.pageSize,
      app_id: currentApp.value
    })

    logs.value = logRes.data.list || []
    pagination.total = logRes.data.total || 0

    // 🔥 C. 前端计算成功率 (基于当前列表样本，更精确做法是后端提供)
    if (logs.value.length > 0) {
      const successCount = logs.value.filter(l => l.status === 'success').length
      stats.success_rate = (successCount / logs.value.length) * 100
    } else {
      stats.success_rate = 100
    }

  } catch (e) {
    console.error("加载数据失败:", e)
  } finally {
    loading.value = false
  }
}

// 渲染图表
const renderChart = (dailyData) => {
  const dates = dailyData.map(d => d.date)
  const tokens = dailyData.map(d => d.tokens)
  const calls = dailyData.map(d => d.calls) // 也可以画调用次数

  chartOption.value = {
    tooltip: {
      trigger: 'axis',
      formatter: '{b}<br/>Token消耗: {c}'
    },
    grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
    xAxis: { type: 'category', data: dates },
    yAxis: { type: 'value', name: 'Tokens' },
    series: [{
      name: 'Token消耗',
      data: tokens,
      type: 'line',
      smooth: true,
      symbol: 'circle',
      symbolSize: 8,
      areaStyle: { opacity: 0.2 },
      itemStyle: { color: '#1890ff' },
      lineStyle: { width: 3 }
    }]
  }
}

const handlePageChange = (page) => {
  pagination.current = page
  fetchData()
}

// 查看详情 (从表格行数据直接获取，利用之前后端补全的 Answer 字段)
const viewDetail = (record) => {
  currentLog.value = record
  drawerVisible.value = true
}

// 格式化时间
const formatTime = (ts) => {
  if (!ts) return '-'
  return new Date(ts).toLocaleString()
}

// 切换应用时刷新
const handleAppChange = () => {
  pagination.current = 1
  fetchData()
}

onMounted(() => {
  fetchData()
})
</script>

<style scoped>
.insight-container { padding: 20px; background: #f0f2f5; min-height: 100vh; }
.header-actions { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
.filters { display: flex; gap: 10px; }
.stat-cards { margin-bottom: 20px; }
.chart-card { margin-bottom: 20px; }
.table-card { background: white; }
/* 新增详情页样式 */
.chat-snapshot {
  background: #f8f9fa;
  padding: 15px;
  border-radius: 8px;
}
.chat-bubble { margin-bottom: 15px; }
.role-label { font-size: 12px; color: #999; margin-bottom: 4px; }
.bubble-content {
  padding: 10px;
  border-radius: 6px;
  font-size: 14px;
  line-height: 1.5;
  white-space: pre-wrap;
}
.user .bubble-content { background: #e6f7ff; border: 1px solid #91d5ff; }
.ai .bubble-content { background: #fff; border: 1px solid #dcdfe6; }
.json-box { background: #2d2d2d; color: #ccc; padding: 10px; border-radius: 4px; overflow-x: auto; font-size: 12px; }
</style>