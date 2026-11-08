<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import {
  createOptimizationRun,
  fetchDishOptions,
  fetchOptimizationDetail,
  fetchOptimizationRuns,
} from '../api/runs'
import type { DishOption, OptimizationRunListItem, OptimizationRunResult } from '../api/types'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const canRun = computed(() => ['admin', 'manager'].includes(auth.user?.role || ''))

const DEFAULT_WEIGHTS = { margin: 0.4, satisfaction: 0.3, nutrition: 0.15, waste: 0.15 }
const weights = reactive({ ...DEFAULT_WEIGHTS })
const protectedIds = ref<number[]>([])
const periodDays = ref(30)
const running = ref(false)
const result = ref<OptimizationRunResult | null>(null)
const history = ref<OptimizationRunListItem[]>([])
const dishOptions = ref<DishOption[]>([])
const actionFilter = ref('全部')

const ACTION_TYPES: Record<string, string> = {
  推广: 'success',
  保留: 'info',
  汰换: 'danger',
}

const rows = computed(() => {
  const all = result.value?.dishes ?? []
  return actionFilter.value === '全部' ? all : all.filter((d) => d.action === actionFilter.value)
})

function resetWeights() {
  Object.assign(weights, DEFAULT_WEIGHTS)
}

async function loadHistory() {
  history.value = await fetchOptimizationRuns()
}

async function runNow() {
  running.value = true
  try {
    const r = await createOptimizationRun({
      weights: { ...weights },
      protected: protectedIds.value,
      period_days: periodDays.value,
    })
    result.value = r
    await loadHistory()
    ElMessage.success('优化完成')
  } catch {
    // 错误提示由 http 拦截器统一处理
  } finally {
    running.value = false
  }
}

async function openRun(row: OptimizationRunListItem) {
  result.value = await fetchOptimizationDetail(row.id)
}

onMounted(async () => {
  dishOptions.value = await fetchDishOptions()
  await loadHistory()
  if (history.value.length) result.value = await fetchOptimizationDetail(history.value[0].id)
})

const pct = (v: number) => `${(v * 100).toFixed(0)}%`
</script>

<template>
  <div>
    <el-card style="margin-bottom: 16px">
      <div class="card-title">目标权重（系统自动归一，允许只调相对比例）</div>
      <el-row :gutter="24">
        <el-col :span="6">
          <div class="weight-label">毛利权重：{{ weights.margin.toFixed(2) }}</div>
          <el-slider v-model="weights.margin" :min="0" :max="1" :step="0.05" />
        </el-col>
        <el-col :span="6">
          <div class="weight-label">满意度权重：{{ weights.satisfaction.toFixed(2) }}</div>
          <el-slider v-model="weights.satisfaction" :min="0" :max="1" :step="0.05" />
        </el-col>
        <el-col :span="6">
          <div class="weight-label">营养权重：{{ weights.nutrition.toFixed(2) }}</div>
          <el-slider v-model="weights.nutrition" :min="0" :max="1" :step="0.05" />
        </el-col>
        <el-col :span="6">
          <div class="weight-label">低浪费权重：{{ weights.waste.toFixed(2) }}</div>
          <el-slider v-model="weights.waste" :min="0" :max="1" :step="0.05" />
        </el-col>
      </el-row>
      <div style="display: flex; gap: 12px; align-items: center; margin-top: 12px; flex-wrap: wrap">
        <el-select
          v-model="protectedIds"
          multiple
          filterable
          collapse-tags
          placeholder="保底菜品（不会被汰换）"
          style="width: 320px"
        >
          <el-option
            v-for="d in dishOptions"
            :key="d.id"
            :label="`${d.name}（${d.stall_name}）`"
            :value="d.id"
          />
        </el-select>
        <el-select v-model="periodDays" style="width: 130px">
          <el-option v-for="p in [30, 60, 90]" :key="p" :label="`近 ${p} 天`" :value="p" />
        </el-select>
        <el-button type="primary" :loading="running" :disabled="!canRun" @click="runNow">
          发起菜单优化
        </el-button>
        <el-button @click="resetWeights">恢复默认权重</el-button>
        <span v-if="!canRun" style="color: #909399; font-size: 12px">当前角色无发起权限</span>
      </div>
    </el-card>

    <el-row :gutter="12" style="margin-bottom: 16px">
      <el-col :span="4">
        <el-card>
          <div class="kpi-label">推广</div>
          <div class="kpi-value" style="color: #67c23a">{{ result?.counts['推广'] ?? 0 }}</div>
        </el-card>
      </el-col>
      <el-col :span="4">
        <el-card>
          <div class="kpi-label">保留</div>
          <div class="kpi-value">{{ result?.counts['保留'] ?? 0 }}</div>
        </el-card>
      </el-col>
      <el-col :span="4">
        <el-card>
          <div class="kpi-label">汰换</div>
          <div class="kpi-value" style="color: #f56c6c">{{ result?.counts['汰换'] ?? 0 }}</div>
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card>
          <div class="kpi-label">统计区间</div>
          <div class="kpi-value" style="font-size: 16px">
            {{ result ? `${result.period.start} ～ ${result.period.end}` : '-' }}
          </div>
          <div style="color: #909399; font-size: 12px; margin-top: 4px">
            每档口至少保留 10 个菜品；保底菜品不参与汰换
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-card>
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px">
        <span class="card-title">打分结果</span>
        <el-select v-model="actionFilter" style="width: 120px">
          <el-option v-for="a in ['全部', '推广', '保留', '汰换']" :key="a" :label="a" :value="a" />
        </el-select>
      </div>
      <el-table :data="rows" size="small" max-height="520">
        <el-table-column prop="name" label="菜品" width="130" />
        <el-table-column prop="stall_name" label="档口" width="110" />
        <el-table-column prop="score" label="综合得分" width="100" sortable />
        <el-table-column label="毛利分" width="90">
          <template #default="{ row }">{{ pct(row.n_margin) }}</template>
        </el-table-column>
        <el-table-column label="满意度分" width="90">
          <template #default="{ row }">{{ pct(row.n_satisfaction) }}</template>
        </el-table-column>
        <el-table-column label="营养分" width="90">
          <template #default="{ row }">{{ pct(row.n_nutrition) }}</template>
        </el-table-column>
        <el-table-column label="低浪费分" width="90">
          <template #default="{ row }">{{ pct(row.n_waste) }}</template>
        </el-table-column>
        <el-table-column label="动作" width="90">
          <template #default="{ row }">
            <el-tag :type="ACTION_TYPES[row.action] ?? 'info'" size="small">{{ row.action }}</el-tag>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-card style="margin-top: 16px">
      <div class="card-title">运行历史</div>
      <el-table :data="history" size="small" max-height="260" @row-click="openRun">
        <el-table-column prop="id" label="#" width="60" />
        <el-table-column label="权重" width="260">
          <template #default="{ row }">
            毛利 {{ row.weights.margin }} / 满意度 {{ row.weights.satisfaction }} / 营养
            {{ row.weights.nutrition }} / 低浪费 {{ row.weights.waste }}
          </template>
        </el-table-column>
        <el-table-column label="动作计数" width="220">
          <template #default="{ row }">
            推广 {{ row.counts['推广'] ?? 0 }} / 保留 {{ row.counts['保留'] ?? 0 }} / 汰换
            {{ row.counts['汰换'] ?? 0 }}
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" />
      </el-table>
    </el-card>
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
.weight-label {
  color: #606266;
  font-size: 13px;
}
</style>