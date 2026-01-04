<template>
  <div class="graph-container">
    <div v-if="!hasData" class="empty-graph">
      <a-empty description="暂无关联知识网络" />
    </div>
    <v-chart v-else class="chart" :option="chartOption" autoresize />
  </div>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { GraphChart } from 'echarts/charts'
import { TooltipComponent, LegendComponent } from 'echarts/components'
import VChart from 'vue-echarts'

use([CanvasRenderer, GraphChart, TooltipComponent, LegendComponent])

const props = defineProps({
  data: {
    type: Object,
    default: () => ({ nodes: [], edges: [] })
  }
})

const hasData = computed(() => props.data?.nodes?.length > 0)

const chartOption = ref({})

// 监听数据变化，重新渲染图表
watch(() => props.data, (newData) => {
  if (!newData || !newData.nodes) return

  // 1. 定义节点分类（颜色区分）
  const categories = [...new Set(newData.nodes.map(n => n.type))].map(t => ({ name: t }))

  chartOption.value = {
    tooltip: { trigger: 'item' },
    legend: [{ data: categories.map(c => c.name), orient: 'horizontal', bottom: 0 }],
    series: [
      {
        type: 'graph',
        layout: 'force',
        data: newData.nodes.map(n => ({
          id: n.id,
          name: n.label,
          category: n.type,
          symbolSize: 40,
          draggable: true
        })),
        links: newData.edges.map(e => ({
          source: e.source,
          target: e.target,
          label: { show: true, formatter: e.label, fontSize: 10 }
        })),
        categories: categories,
        force: {
          repulsion: 200,
          edgeLength: 120,
          gravity: 0.1
        },
        roam: true,
        label: {
          show: true,
          position: 'inside',
          fontSize: 10
        },
        lineStyle: {
          color: 'source',
          curveness: 0.2,
          width: 2
        },
        emphasis: {
          focus: 'adjacency',
          lineStyle: { width: 4 }
        }
      }
    ]
  }
}, { deep: true })
</script>

<style scoped>
.graph-container { width: 100%; height: 100%; min-height: 300px; background: #fff; position: relative; }
.chart { width: 100%; height: 100%; }
.empty-graph { display: flex; align-items: center; justify-content: center; height: 100%; color: #999; }
</style>