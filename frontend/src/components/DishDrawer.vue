<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { EChartsOption } from 'echarts'
import { fetchDishDetail } from '../api/analysis'
import type { DishDetail } from '../api/types'
import ChartPanel from './ChartPanel.vue'

const props = defineProps<{
  modelValue: boolean
  dishId: number | null
  start: string
  end: string
}>()
const emit = defineEmits<{ (e: 'update:modelValue', v: boolean): void }>()

const visible = computed({
  get: () => props.modelValue,
  set: (v) => emit('update:modelValue', v),
})
const detail = ref<DishDetail | null>(null)
const loading = ref(false)

watch(
  () => [props.modelValue, props.dishId],
  async ([open, id]) => {
    if (open && id) {
      loading.value = true
      try {
        detail.value = await fetchDishDetail(Number(id), { start: props.start, end: props.end })
      } finally {
        loading.value = false
      }
    }
  },
)

const trendOption = computed<EChartsOption>(() => ({
  tooltip: { trigger: 'axis' },
  legend: { data: ['销量', '营收'] },
  xAxis: { type: 'category', data: detail.value?.trend.map((t) => t.date) ?? [] },
  yAxis: [
    { type: 'value', name: '销量' },
    { type: 'value', name: '营收（元）' },
  ],
  series: [
    { name: '销量', type: 'bar', data: detail.value?.trend.map((t) => t.quantity) ?? [] },
    {
      name: '营收',
      type: 'line',
      yAxisIndex: 1,
      data: detail.value?.trend.map((t) => t.revenue) ?? [],
    },
  ],
}))
</script>

<template>
  <el-drawer v-model="visible" size="55%" :title="detail?.dish.name || '菜品分析'">
    <div v-loading="loading">
      <template v-if="detail">
        <el-descriptions :column="3" border style="margin-bottom: 16px">
          <el-descriptions-item label="档口">{{ detail.dish.stall_name }}</el-descriptions-item>
          <el-descriptions-item label="品类">{{ detail.dish.category }}</el-descriptions-item>
          <el-descriptions-item label="单价">¥{{ detail.dish.price }}</el-descriptions-item>
        </el-descriptions>
        <h4>销售趋势</h4>
        <ChartPanel :option="trendOption" height="260px" />
        <h4>评价（{{ detail.reviews.summary.count }} 条，均分 {{ detail.reviews.summary.avg_rating ?? '-' }}）</h4>
        <el-table :data="detail.reviews.recent" size="small" style="margin-bottom: 16px">
          <el-table-column prop="rating" label="评分" width="70" />
          <el-table-column prop="content" label="内容" />
          <el-table-column prop="created_at" label="时间" width="170" />
        </el-table>
        <h4>浪费</h4>
        <el-descriptions :column="3" border>
          <el-descriptions-item label="备餐量">{{ detail.waste.prepared }}</el-descriptions-item>
          <el-descriptions-item label="浪费量">{{ detail.waste.wasted }}</el-descriptions-item>
          <el-descriptions-item label="浪费率">
            {{ (detail.waste.rate * 100).toFixed(1) }}%
          </el-descriptions-item>
        </el-descriptions>
      </template>
    </div>
  </el-drawer>
</template>