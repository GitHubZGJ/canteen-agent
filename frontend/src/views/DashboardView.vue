<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import type { EChartsOption } from 'echarts'
import { fetchHeatmap, fetchOverview, fetchRanking, fetchTrend } from '../api/dashboard'
import type { Heatmap, Overview, RankItem, TrendItem } from '../api/types'
import { useAppStore } from '../stores/app'
import ChartPanel from '../components/ChartPanel.vue'

const appStore = useAppStore()
const range = ref<[string, string] | null>(null)
const overview = ref<Overview | null>(null)
const trend = ref<TrendItem[]>([])
const ranking = ref<RankItem[]>([])
const heatmap = ref<Heatmap | null>(null)
const loading = ref(false)

const money = (v: number | null) =>
  v === null ? '-' : `¥${v.toLocaleString('zh-CN', { maximumFractionDigits: 2 })}`
const pct = (v: number | null) => (v === null ? '-' : `${(v * 100).toFixed(1)}%`)
const int = (v: number | null) => (v === null ? '-' : v.toLocaleString('zh-CN'))
const score = (v: number | null) => (v === null ? '-' : v.toFixed(2))

const kpiDefs = [
  { key: 'revenue', label: '营收', fmt: money, invert: false },
  { key: 'orders', label: '订单数', fmt: int, invert: false },
  { key: 'avg_value', label: '客单价', fmt: money, invert: false },
  { key: 'gross_margin', label: '毛利率', fmt: pct, invert: false },
  { key: 'waste_rate', label: '浪费率', fmt: pct, invert: true },
  { key: 'satisfaction', label: '满意度', fmt: score, invert: false },
]

function deltaText(delta: number | null) {
  if (delta === null) return '环比 -'
  const value = delta * 100
  if (Math.abs(value) < 0.05) return '环比 0.0%'
  return `环比 ${value >= 0 ? '+' : ''}${value.toFixed(1)}%`
}

function deltaColor(delta: number | null, invert: boolean) {
  if (delta === null || Math.abs(delta * 100) < 0.05) return '#909399'
  const good = invert ? delta < 0 : delta > 0
  return good ? '#67c23a' : '#f56c6c'
}

async function loadAll() {
  loading.value = true
  try {
    const params = range.value ? { start: range.value[0], end: range.value[1] } : undefined
    const ov = await fetchOverview(params)
    overview.value = ov
    if (!range.value) range.value = [ov.range.start, ov.range.end]
    appStore.setRange(ov.range.start, ov.range.end)
    const p = { start: ov.range.start, end: ov.range.end }
    const [t, r, h] = await Promise.all([
      fetchTrend(p),
      fetchRanking({ ...p, scope: 'stall', limit: 8 }),
      fetchHeatmap(p),
    ])
    trend.value = t.items
    ranking.value = r.items
    heatmap.value = h
  } finally {
    loading.value = false
  }
}

onMounted(loadAll)

const trendOption = computed<EChartsOption>(() => ({
  tooltip: { trigger: 'axis' },
  legend: { data: ['营收', '订单数'] },
  xAxis: { type: 'category', data: trend.value.map((t) => t.date) },
  yAxis: [
    { type: 'value', name: '营收（元）' },
    { type: 'value', name: '订单数' },
  ],
  series: [
    {
      name: '营收',
      type: 'line',
      smooth: true,
      areaStyle: { opacity: 0.1 },
      data: trend.value.map((t) => t.revenue),
    },
    { name: '订单数', type: 'line', yAxisIndex: 1, data: trend.value.map((t) => t.orders) },
  ],
}))

const slotsOption = computed<EChartsOption>(() => ({
  tooltip: { trigger: 'axis' },
  xAxis: { type: 'category', data: overview.value?.slots.map((s) => s.label) ?? [] },
  yAxis: { type: 'value', name: '订单数' },
  series: [
    {
      type: 'bar',
      data: overview.value?.slots.map((s) => s.orders) ?? [],
      label: { show: true, position: 'top' },
      itemStyle: { color: '#409eff' },
    },
  ],
}))

const rankingOption = computed<EChartsOption>(() => ({
  tooltip: { trigger: 'axis' },
  grid: { left: 90 },
  xAxis: { type: 'value', name: '营收（元）' },
  yAxis: { type: 'category', inverse: true, data: ranking.value.map((r) => r.name) },
  series: [
    {
      type: 'bar',
      data: ranking.value.map((r) => r.revenue),
      label: { show: true, position: 'right' },
      itemStyle: { color: '#67c23a' },
    },
  ],
}))

const heatmapOption = computed<EChartsOption>(() => {
  const h = heatmap.value
  const max = h && h.data.length ? Math.max(...h.data.map((d) => d[2])) : 1
  return {
    tooltip: { position: 'top' },
    grid: { top: 30, bottom: 60 },
    xAxis: { type: 'category', data: (h?.hours ?? []).map((x) => `${x}:00`) },
    yAxis: { type: 'category', data: h?.days ?? [] },
    visualMap: {
      min: 0,
      max,
      orient: 'horizontal',
      left: 'center',
      bottom: 0,
      inRange: { color: ['#ebedf0', '#9be9a8', '#40c463', '#30a14e', '#216e39'] },
    },
    series: [{ type: 'heatmap', data: h?.data ?? [], label: { show: true } }],
  }
})
</script>

<template>
  <div v-loading="loading">
    <el-card style="margin-bottom: 16px">
      <div style="display: flex; justify-content: space-between; align-items: center">
        <span style="font-weight: 600">经营概览（环比上一等长周期）</span>
        <el-date-picker
          v-model="range"
          type="daterange"
          value-format="YYYY-MM-DD"
          start-placeholder="开始日期"
          end-placeholder="结束日期"
          :clearable="false"
          @change="loadAll"
        />
      </div>
    </el-card>

    <el-row :gutter="12" style="margin-bottom: 16px">
      <el-col v-for="def in kpiDefs" :key="def.key" :span="4">
        <el-card>
          <div style="color: #909399; font-size: 13px">{{ def.label }}</div>
          <div style="font-size: 22px; font-weight: 600; margin: 6px 0" data-testid="kpi-value">
            {{ def.fmt(overview?.kpis[def.key]?.value ?? null) }}
          </div>
          <div
            v-if="overview"
            :style="{ color: deltaColor(overview.kpis[def.key]?.delta, def.invert), fontSize: '12px' }"
          >
            {{ deltaText(overview.kpis[def.key]?.delta) }}
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="12" style="margin-bottom: 16px">
      <el-col :span="16">
        <el-card><div class="chart-title">营收与订单趋势</div><ChartPanel :option="trendOption" /></el-card>
      </el-col>
      <el-col :span="8">
        <el-card><div class="chart-title">时段分布</div><ChartPanel :option="slotsOption" /></el-card>
      </el-col>
    </el-row>

    <el-row :gutter="12">
      <el-col :span="10">
        <el-card><div class="chart-title">档口营收排行</div><ChartPanel :option="rankingOption" /></el-card>
      </el-col>
      <el-col :span="14">
        <el-card>
          <div class="chart-title">星期 × 时段订单热力</div>
          <ChartPanel :option="heatmapOption" />
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<style scoped>
.chart-title {
  font-weight: 600;
  margin-bottom: 8px;
}
</style>