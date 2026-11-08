<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import type { EChartsOption } from 'echarts'
import { ElMessage } from 'element-plus'
import ChartPanel from '../components/ChartPanel.vue'
import {
  createForecastRun,
  fetchDishOptions,
  fetchForecastDetail,
  fetchForecastRuns,
} from '../api/runs'
import type {
  DishOption,
  ForecastCreateResult,
  ForecastRunDetail,
  ForecastRunListItem,
} from '../api/types'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const canRun = computed(() => ['admin', 'manager'].includes(auth.user?.role || ''))

const dishOptions = ref<DishOption[]>([])
const dishId = ref<number | null>(null)
const horizon = ref(14)
const safety = ref(1.1)
const running = ref(false)
const result = ref<ForecastCreateResult | null>(null)
const detail = ref<ForecastRunDetail | null>(null)
const history = ref<ForecastRunListItem[]>([])
const seriesKey = ref('')

const SLOT_LABELS: Record<string, string> = { breakfast: '早餐', lunch: '午餐', dinner: '晚餐' }

const seriesOptions = computed(() =>
  (detail.value?.series ?? []).map((s) => ({
    value: `${s.dish_id}-${s.slot}`,
    label: `${s.dish_name} · ${SLOT_LABELS[s.slot] ?? s.slot}`,
  })),
)

const currentSeries = computed(() => {
  if (!detail.value?.series.length) return null
  if (!seriesKey.value) return detail.value.series[0]
  const [d, s] = seriesKey.value.split('-')
  return detail.value.series.find((x) => x.dish_id === Number(d) && x.slot === s) ?? null
})

async function loadHistory() {
  history.value = await fetchForecastRuns()
}

async function loadDetail(id: number) {
  detail.value = await fetchForecastDetail(id)
  seriesKey.value = detail.value.series.length
    ? `${detail.value.series[0].dish_id}-${detail.value.series[0].slot}`
    : ''
}

async function runNow() {
  running.value = true
  try {
    const body: Record<string, unknown> = { horizon: horizon.value, safety_factor: safety.value }
    if (dishId.value) body.dish_id = dishId.value
    const r = await createForecastRun(body)
    result.value = r
    await loadDetail(r.run_id)
    await loadHistory()
    ElMessage.success('回测完成')
  } catch {
    // 错误提示由 http 拦截器统一处理
  } finally {
    running.value = false
  }
}

async function openRun(row: ForecastRunListItem) {
  result.value = null
  await loadDetail(row.id)
}

onMounted(async () => {
  dishOptions.value = await fetchDishOptions()
  await loadHistory()
  if (history.value.length) await loadDetail(history.value[0].id)
})

const pct = (v: number | null | undefined) => (v == null ? '-' : `${(v * 100).toFixed(1)}%`)

const comparison = computed(() => {
  const p = detail.value?.params
  const hw = p?.holt_winters
  const nv = p?.seasonal_naive_same_subset
  if (!hw || !nv || hw.mae == null || nv.mae == null) return null
  return {
    hw,
    nv,
    improveMae: (nv.mae - hw.mae) / nv.mae,
    improveMape:
      hw.mape != null && nv.mape != null ? (nv.mape - hw.mape) / nv.mape : null,
  }
})

const prepRows = computed(() => {
  const rows = result.value?.prep_suggestions ?? detail.value?.params.prep_suggestions ?? []
  return rows.slice().sort((a, b) => b.estimated_saving - a.estimated_saving).slice(0, 15)
})

const chartOption = computed<EChartsOption>(() => {
  const s = currentSeries.value
  return {
    tooltip: { trigger: 'axis' },
    legend: { data: ['实际', '预测', '上界', '下界'] },
    xAxis: { type: 'category', data: s?.points.map((p) => p.date) ?? [] },
    yAxis: { type: 'value', name: '销量（份）' },
    series: [
      { name: '实际', type: 'line', data: s?.points.map((p) => p.actual) ?? [] },
      {
        name: '预测',
        type: 'line',
        lineStyle: { type: 'dashed' },
        data: s?.points.map((p) => p.predicted) ?? [],
      },
      {
        name: '上界',
        type: 'line',
        symbol: 'none',
        lineStyle: { type: 'dotted', color: '#c0c4cc' },
        data: s?.points.map((p) => p.upper) ?? [],
      },
      {
        name: '下界',
        type: 'line',
        symbol: 'none',
        lineStyle: { type: 'dotted', color: '#c0c4cc' },
        data: s?.points.map((p) => p.lower) ?? [],
      },
    ],
  }
})
</script>

<template>
  <div>
    <el-card style="margin-bottom: 16px">
      <div style="display: flex; gap: 12px; align-items: center; flex-wrap: wrap">
        <el-select
          v-model="dishId"
          placeholder="全部菜品（默认）"
          clearable
          filterable
          style="width: 220px"
        >
          <el-option
            v-for="d in dishOptions"
            :key="d.id"
            :label="`${d.name}（${d.stall_name}）`"
            :value="d.id"
          />
        </el-select>
        <el-select v-model="horizon" style="width: 110px">
          <el-option v-for="h in [7, 14, 21, 28]" :key="h" :label="`${h} 天`" :value="h" />
        </el-select>
        <span>安全系数</span>
        <el-input-number v-model="safety" :min="1.0" :max="1.5" :step="0.05" style="width: 110px" />
        <el-button type="primary" :loading="running" :disabled="!canRun" @click="runNow">
          发起回测预测
        </el-button>
        <span v-if="!canRun" style="color: #909399; font-size: 12px">当前角色无发起权限</span>
      </div>
    </el-card>

    <el-row v-if="comparison" :gutter="12" style="margin-bottom: 16px">
      <el-col :span="5">
        <el-card>
          <div class="kpi-label">Holt-Winters MAE</div>
          <div class="kpi-value">{{ comparison.hw.mae }}</div>
        </el-card>
      </el-col>
      <el-col :span="5">
        <el-card>
          <div class="kpi-label">季节朴素基线 MAE</div>
          <div class="kpi-value">{{ comparison.nv.mae }}</div>
        </el-card>
      </el-col>
      <el-col :span="5">
        <el-card>
          <div class="kpi-label">MAE 改进</div>
          <div class="kpi-value" style="color: #67c23a">
            {{ comparison.improveMae >= 0 ? '+' : '' }}{{ pct(comparison.improveMae) }}
          </div>
        </el-card>
      </el-col>
      <el-col :span="5">
        <el-card>
          <div class="kpi-label">MAPE 对比（HW / 基线）</div>
          <div class="kpi-value">{{ pct(comparison.hw.mape) }} / {{ pct(comparison.nv.mape) }}</div>
        </el-card>
      </el-col>
      <el-col :span="4">
        <el-card>
          <div class="kpi-label">预计日节约</div>
          <div class="kpi-value" style="color: #409eff">
            {{ result?.total_estimated_saving ?? detail?.params.total_estimated_saving ?? '-' }} 份
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-card v-if="detail" style="margin-bottom: 16px">
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px">
        <span style="font-weight: 600">
          回测区间 {{ detail.target_start }} ～ {{ detail.target_end }}（虚线为预测，点线为 95% 区间）
        </span>
        <el-select v-model="seriesKey" filterable style="width: 260px" placeholder="选择菜品与时段">
          <el-option
            v-for="opt in seriesOptions"
            :key="opt.value"
            :label="opt.label"
            :value="opt.value"
          />
        </el-select>
      </div>
      <ChartPanel :option="chartOption" height="340px" />
    </el-card>

    <el-row :gutter="12">
      <el-col :span="12">
        <el-card>
          <div class="card-title">备餐建议（按预计节约排序）</div>
          <el-table v-if="prepRows.length" :data="prepRows" size="small" max-height="360">
            <el-table-column label="菜品" width="120">
              <template #default="{ row }">
                {{ dishOptions.find((d) => d.id === row.dish_id)?.name ?? row.dish_id }}
              </template>
            </el-table-column>
            <el-table-column prop="avg_daily_forecast" label="日均预测" width="90" />
            <el-table-column prop="suggested_prep" label="建议备餐" width="90" />
            <el-table-column prop="hist_avg_wasted" label="历史均浪费" width="100" />
            <el-table-column prop="estimated_saving" label="预计节约" width="90" />
          </el-table>
          <p v-else style="color: #909399">发起一次预测后生成。</p>
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card>
          <div class="card-title">运行历史</div>
          <el-table :data="history" size="small" max-height="360" @row-click="openRun">
            <el-table-column prop="id" label="#" width="60" />
            <el-table-column label="范围" width="100">
              <template #default="{ row }">{{ row.dish_id ? `菜品 ${row.dish_id}` : '全部' }}</template>
            </el-table-column>
            <el-table-column prop="mae" label="MAE" width="80" />
            <el-table-column label="MAPE" width="90">
              <template #default="{ row }">{{ pct(row.mape) }}</template>
            </el-table-column>
            <el-table-column prop="target_end" label="回测截止" width="110" />
            <el-table-column prop="created_at" label="创建时间" />
          </el-table>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<style scoped>
.kpi-label {
  color: #909399;
  font-size: 13px;
}
.kpi-value {
  font-size: 22px;
  font-weight: 600;
  margin-top: 6px;
}
.card-title {
  font-weight: 600;
  margin-bottom: 8px;
}
</style>