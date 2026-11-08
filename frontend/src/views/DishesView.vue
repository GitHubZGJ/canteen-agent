<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import type { EChartsOption } from 'echarts'
import { fetchNutrition, fetchPortfolio, fetchReviews, fetchWaste } from '../api/analysis'
import type { DishStat, NutritionAnalysis, Portfolio, ReviewsAnalysis, WasteAnalysis } from '../api/types'
import { useAppStore } from '../stores/app'
import ChartPanel from '../components/ChartPanel.vue'
import DishDrawer from '../components/DishDrawer.vue'

const appStore = useAppStore()
const tab = ref('portfolio')
const range = ref<[string, string] | null>(
  appStore.start ? [appStore.start, appStore.end] : null,
)
const loading = ref(false)
const portfolio = ref<Portfolio | null>(null)
const waste = ref<WasteAnalysis | null>(null)
const reviews = ref<ReviewsAnalysis | null>(null)
const nutrition = ref<NutritionAnalysis | null>(null)

const page = ref(1)
const drawerVisible = ref(false)
const drawerDishId = ref<number | null>(null)

const pct = (v: number) => `${(v * 100).toFixed(1)}%`
const money = (v: number) => `¥${v.toLocaleString('zh-CN', { maximumFractionDigits: 2 })}`

const QUADRANT_COLORS: Record<string, string> = {
  明星: '#67c23a',
  金牛: '#409eff',
  问题: '#e6a23c',
  瘦狗: '#f56c6c',
}
const SENTIMENT_LABELS: Record<string, string> = { pos: '正面', neu: '中性', neg: '负面' }

async function loadAll() {
  loading.value = true
  try {
    const params = range.value ? { start: range.value[0], end: range.value[1] } : undefined
    const pf = await fetchPortfolio(params)
    portfolio.value = pf
    if (!range.value) range.value = [pf.range.start, pf.range.end]
    appStore.setRange(pf.range.start, pf.range.end)
    const p = { start: pf.range.start, end: pf.range.end }
    const [w, r, n] = await Promise.all([fetchWaste(p), fetchReviews(p), fetchNutrition(p)])
    waste.value = w
    reviews.value = r
    nutrition.value = n
  } finally {
    loading.value = false
  }
}

onMounted(loadAll)

const pagedDishes = computed(() => {
  const all = portfolio.value?.dishes ?? []
  return all.slice((page.value - 1) * 10, page.value * 10)
})

function openDrawer(row: DishStat) {
  drawerDishId.value = row.dish_id
  drawerVisible.value = true
}

const scatterOption = computed<EChartsOption>(() => {
  const pf = portfolio.value
  const series = Object.keys(QUADRANT_COLORS).map((q) => ({
    name: q,
    type: 'scatter' as const,
    itemStyle: { color: QUADRANT_COLORS[q] },
    symbolSize: (val: number[]) => Math.max(6, Math.sqrt(val[2]) / 8),
    data: (pf?.dishes ?? [])
      .filter((d) => d.quadrant === q)
      .map((d) => [d.quantity, +(d.margin_rate * 100).toFixed(2), d.revenue, d.name]),
  }))
  if (series.length && pf) {
    Object.assign(series[0], {
      markLine: {
        silent: true,
        lineStyle: { type: 'dashed', color: '#909399' },
        data: [{ xAxis: pf.thresholds.qty_median }, { yAxis: pf.thresholds.margin_median * 100 }],
      },
    })
  }
  return {
    tooltip: {
      formatter: (p: unknown) => {
        const v = (p as { value: number[] }).value
        return `${v[3]}<br/>销量：${v[0]}　毛利率：${v[1]}%<br/>营收：¥${v[2].toLocaleString()}`
      },
    },
    legend: { data: Object.keys(QUADRANT_COLORS) },
    xAxis: { type: 'value', name: '销量' },
    yAxis: { type: 'value', name: '毛利率（%）' },
    series,
  }
})

const wasteTopOption = computed<EChartsOption>(() => ({
  tooltip: { trigger: 'axis' },
  grid: { left: 110 },
  xAxis: { type: 'value', name: '浪费量' },
  yAxis: { type: 'category', inverse: true, data: waste.value?.top_dishes.map((d) => d.name) ?? [] },
  series: [
    {
      type: 'bar',
      data: waste.value?.top_dishes.map((d) => d.wasted) ?? [],
      itemStyle: { color: '#e6a23c' },
      label: { show: true, position: 'right' },
    },
  ],
}))

const reasonOption = computed<EChartsOption>(() => ({
  tooltip: { trigger: 'item' },
  legend: { bottom: 0 },
  series: [
    {
      type: 'pie',
      radius: ['35%', '65%'],
      data: waste.value?.by_reason.map((r) => ({ name: r.reason, value: r.wasted })) ?? [],
    },
  ],
}))

const wasteTrendOption = computed<EChartsOption>(() => ({
  tooltip: { trigger: 'axis' },
  legend: { data: ['备餐量', '浪费量'] },
  xAxis: { type: 'category', data: waste.value?.trend.map((t) => t.date) ?? [] },
  yAxis: { type: 'value' },
  series: [
    { name: '备餐量', type: 'line', data: waste.value?.trend.map((t) => t.prepared) ?? [] },
    { name: '浪费量', type: 'line', data: waste.value?.trend.map((t) => t.wasted) ?? [] },
  ],
}))

const ratingDistOption = computed<EChartsOption>(() => ({
  tooltip: { trigger: 'axis' },
  xAxis: { type: 'category', data: ['1 星', '2 星', '3 星', '4 星', '5 星'] },
  yAxis: { type: 'value', name: '条数' },
  series: [
    {
      type: 'bar',
      itemStyle: { color: '#409eff' },
      data: [1, 2, 3, 4, 5].map((i) => reviews.value?.summary.rating_dist[String(i)] ?? 0),
      label: { show: true, position: 'top' },
    },
  ],
}))

const sentimentOption = computed<EChartsOption>(() => ({
  tooltip: { trigger: 'item' },
  legend: { bottom: 0 },
  series: [
    {
      type: 'pie',
      radius: ['35%', '65%'],
      data: Object.entries(reviews.value?.summary.sentiment_dist ?? {}).map(([k, v]) => ({
        name: SENTIMENT_LABELS[k] ?? k,
        value: v,
      })),
    },
  ],
}))

const tagOption = computed<EChartsOption>(() => {
  const entries = Object.entries(reviews.value?.summary.tag_counts ?? {}).slice(0, 10)
  return {
    tooltip: { trigger: 'axis' },
    grid: { left: 80 },
    xAxis: { type: 'value', name: '提及次数' },
    yAxis: { type: 'category', inverse: true, data: entries.map(([k]) => k) },
    series: [
      {
        type: 'bar',
        data: entries.map(([, v]) => v),
        itemStyle: { color: '#909399' },
        label: { show: true, position: 'right' },
      },
    ],
  }
})

const categoryOption = computed<EChartsOption>(() => ({
  tooltip: { trigger: 'item', formatter: '{b}：¥{c}（{d}%）' },
  legend: { bottom: 0 },
  series: [
    {
      type: 'pie',
      radius: ['35%', '65%'],
      data: nutrition.value?.category_share.map((c) => ({ name: c.category, value: c.revenue })) ?? [],
    },
  ],
}))
</script>

<template>
  <div v-loading="loading">
    <el-card style="margin-bottom: 16px">
      <div style="display: flex; justify-content: space-between; align-items: center">
        <span style="font-weight: 600">菜品分析</span>
        <el-date-picker
          v-model="range"
          type="daterange"
          value-format="YYYY-MM-DD"
          :clearable="false"
          @change="loadAll"
        />
      </div>
    </el-card>

    <el-tabs v-model="tab" type="border-card">
      <el-tab-pane label="组合分析" name="portfolio">
        <el-alert
          v-if="portfolio?.slow_movers.length"
          type="warning"
          :closable="false"
          style="margin-bottom: 12px"
          :title="`滞销预警：${portfolio.slow_movers.length} 个菜品连续 7 天日销量低于档口均值的 20%`"
        >
          <div v-for="s in portfolio.slow_movers" :key="s.dish_id" style="font-size: 12px">
            {{ s.name }}（{{ s.stall_name }}）：日均 {{ s.avg_daily_qty }}，阈值 {{ s.threshold_qty }}
          </div>
        </el-alert>
        <el-alert
          v-else-if="portfolio"
          type="success"
          :closable="false"
          title="当前区间无滞销菜品"
          style="margin-bottom: 12px"
        />
        <el-card style="margin-bottom: 12px">
          <div style="font-weight: 600; margin-bottom: 8px">
            销量 × 毛利率四象限（虚线为中位数，点击表格行看单品详情）
          </div>
          <ChartPanel :option="scatterOption" height="360px" />
        </el-card>
        <el-table :data="pagedDishes" size="small" @row-click="openDrawer">
          <el-table-column prop="name" label="菜品" width="130" />
          <el-table-column prop="stall_name" label="档口" width="100" />
          <el-table-column prop="category" label="品类" width="70" />
          <el-table-column prop="quantity" label="销量" width="80" sortable />
          <el-table-column label="营收" width="110" sortable prop="revenue">
            <template #default="{ row }">{{ money(row.revenue) }}</template>
          </el-table-column>
          <el-table-column label="毛利率" width="90">
            <template #default="{ row }">{{ pct(row.margin_rate) }}</template>
          </el-table-column>
          <el-table-column label="象限" width="80">
            <template #default="{ row }">
              <el-tag :color="QUADRANT_COLORS[row.quadrant]" style="color: #fff" size="small">
                {{ row.quadrant }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="ABC" width="70">
            <template #default="{ row }">
              <el-tag :type="row.abc === 'A' ? 'danger' : row.abc === 'B' ? 'warning' : 'info'" size="small">
                {{ row.abc }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="评分" width="70">
            <template #default="{ row }">{{ row.avg_rating ?? '-' }}</template>
          </el-table-column>
          <el-table-column label="浪费率" width="90">
            <template #default="{ row }">{{ pct(row.waste_rate) }}</template>
          </el-table-column>
        </el-table>
        <el-pagination
          v-model:current-page="page"
          :page-size="10"
          :total="portfolio?.dishes.length ?? 0"
          layout="prev, pager, next, total"
          style="margin-top: 12px; justify-content: flex-end"
        />
      </el-tab-pane>

      <el-tab-pane label="浪费分析" name="waste">
        <el-row :gutter="12" style="margin-bottom: 12px">
          <el-col :span="8">
            <el-card>备餐量：{{ waste?.totals.prepared.toLocaleString() }}</el-card>
          </el-col>
          <el-col :span="8">
            <el-card>浪费量：{{ waste?.totals.wasted.toLocaleString() }}</el-card>
          </el-col>
          <el-col :span="8">
            <el-card>浪费率：{{ waste ? pct(waste.totals.rate) : '-' }}</el-card>
          </el-col>
        </el-row>
        <el-alert
          v-if="waste?.alerts.length"
          type="error"
          :closable="false"
          style="margin-bottom: 12px"
          :title="`浪费预警：${waste.alerts.length} 个菜品浪费率超 15% 且备餐量 ≥ 50`"
        >
          <div v-for="a in waste.alerts" :key="a.dish_id" style="font-size: 12px">
            {{ a.name }}（{{ a.stall_name }}）：浪费 {{ a.wasted }} / 备餐 {{ a.prepared }}（{{ pct(a.waste_rate) }}）
          </div>
        </el-alert>
        <el-row :gutter="12">
          <el-col :span="12">
            <el-card><div class="chart-title">浪费量 Top 10</div><ChartPanel :option="wasteTopOption" /></el-card>
          </el-col>
          <el-col :span="12">
            <el-card><div class="chart-title">浪费原因构成</div><ChartPanel :option="reasonOption" /></el-card>
          </el-col>
        </el-row>
        <el-card style="margin-top: 12px">
          <div class="chart-title">备餐与浪费趋势</div>
          <ChartPanel :option="wasteTrendOption" />
        </el-card>
      </el-tab-pane>

      <el-tab-pane label="评价分析" name="reviews">
        <el-row :gutter="12" style="margin-bottom: 12px">
          <el-col :span="12">
            <el-card>评价数：{{ reviews?.summary.count.toLocaleString() }}</el-card>
          </el-col>
          <el-col :span="12">
            <el-card>平均评分：{{ reviews?.summary.avg_rating ?? '-' }}</el-card>
          </el-col>
        </el-row>
        <el-row :gutter="12" style="margin-bottom: 12px">
          <el-col :span="8">
            <el-card><div class="chart-title">评分分布</div><ChartPanel :option="ratingDistOption" /></el-card>
          </el-col>
          <el-col :span="8">
            <el-card><div class="chart-title">情感构成</div><ChartPanel :option="sentimentOption" /></el-card>
          </el-col>
          <el-col :span="8">
            <el-card><div class="chart-title">标签 Top 10</div><ChartPanel :option="tagOption" /></el-card>
          </el-col>
        </el-row>
        <el-card>
          <div class="chart-title">最新负面评价</div>
          <el-table :data="reviews?.negative_recent ?? []" size="small">
            <el-table-column prop="dish_name" label="菜品" width="130" />
            <el-table-column prop="rating" label="评分" width="70" />
            <el-table-column prop="content" label="内容" />
            <el-table-column prop="created_at" label="时间" width="170" />
          </el-table>
        </el-card>
      </el-tab-pane>

      <el-tab-pane label="营养结构" name="nutrition">
        <el-row :gutter="12" style="margin-bottom: 12px">
          <el-col :span="6">
            <el-card>平均热量：{{ nutrition?.summary.avg_calories ?? '-' }} kcal</el-card>
          </el-col>
          <el-col :span="6">
            <el-card>蛋白质：{{ nutrition?.summary.avg_protein_g ?? '-' }} g</el-card>
          </el-col>
          <el-col :span="6">
            <el-card>脂肪：{{ nutrition?.summary.avg_fat_g ?? '-' }} g</el-card>
          </el-col>
          <el-col :span="6">
            <el-card>碳水：{{ nutrition?.summary.avg_carbs_g ?? '-' }} g</el-card>
          </el-col>
        </el-row>
        <el-row :gutter="12">
          <el-col :span="12">
            <el-card>
              <div class="chart-title">品类营收构成</div>
              <ChartPanel :option="categoryOption" />
            </el-card>
          </el-col>
          <el-col :span="12">
            <el-card>
              <div class="chart-title">轻食营收占比</div>
              <el-progress
                :percentage="+(((nutrition?.light_share ?? 0) * 100).toFixed(1))"
                :stroke-width="18"
                style="margin: 24px 0"
              />
              <p style="color: #909399; font-size: 12px">
                营养数值为按食材估算的模拟值，按销量加权；轻食占比反映健康餐品的经营比重。
              </p>
            </el-card>
          </el-col>
        </el-row>
      </el-tab-pane>
    </el-tabs>

    <DishDrawer
      v-model="drawerVisible"
      :dish-id="drawerDishId"
      :start="range?.[0] ?? ''"
      :end="range?.[1] ?? ''"
    />
  </div>
</template>

<style scoped>
.chart-title {
  font-weight: 600;
  margin-bottom: 8px;
}
</style>