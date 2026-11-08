<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  createSuggestion,
  evaluateSuggestion,
  executeSuggestion,
  fetchSuggestionDetail,
  fetchSuggestions,
  reviewSuggestion,
} from '../api/suggestions'
import type { SuggestionDetail, SuggestionInfo } from '../api/types'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const canManage = computed(() => ['admin', 'manager'].includes(auth.user?.role || ''))

const COLUMNS = [
  { status: 'draft', label: '待审批', color: '#909399' },
  { status: 'approved', label: '已采纳', color: '#409eff' },
  { status: 'in_progress', label: '执行中', color: '#e6a23c' },
  { status: 'closed', label: '已闭环', color: '#67c23a' },
  { status: 'rejected', label: '已驳回', color: '#f56c6c' },
]
const TYPE_LABELS: Record<string, string> = {
  menu_change: '菜单调整',
  forecast_adjust: '备餐调整',
  promotion: '推广活动',
  other: '其他',
}
const METRIC_LABELS: Record<string, string> = {
  revenue: '营收',
  orders: '订单数',
  avg_value: '客单价',
  gross_margin: '毛利率',
  waste_rate: '浪费率',
  satisfaction: '满意度',
}
const PCT_METRICS = new Set(['gross_margin', 'waste_rate'])
const MONEY_METRICS = new Set(['revenue', 'avg_value'])

const items = ref<SuggestionInfo[]>([])
const loading = ref(false)
const drawer = ref(false)
const detail = ref<SuggestionDetail | null>(null)
const createDialog = ref(false)
const creating = ref(false)
const form = reactive({ type: 'menu_change', title: '', note: '' })

const grouped = computed(() =>
  COLUMNS.map((col) => ({
    ...col,
    items: items.value.filter((s) => s.status === col.status),
  })),
)

function fmtMetric(metric: string, value: number) {
  if (PCT_METRICS.has(metric)) return `${(value * 100).toFixed(1)}%`
  if (MONEY_METRICS.has(metric)) return `¥${value.toLocaleString('zh-CN', { maximumFractionDigits: 2 })}`
  return value.toFixed(2)
}

function fmtDelta(metric: string, delta: number) {
  if (PCT_METRICS.has(metric)) return `${delta >= 0 ? '+' : ''}${(delta * 100).toFixed(1)} 个百分点`
  return `${delta >= 0 ? '+' : ''}${delta.toFixed(2)}`
}

async function load() {
  loading.value = true
  try {
    const data = await fetchSuggestions({ page: 1, page_size: 100 })
    items.value = data.items
  } finally {
    loading.value = false
  }
}

async function openDetail(item: SuggestionInfo) {
  detail.value = await fetchSuggestionDetail(item.id)
  drawer.value = true
}

async function refresh() {
  await load()
  if (detail.value) detail.value = await fetchSuggestionDetail(detail.value.id)
}

async function onReview(approve: boolean) {
  if (!detail.value) return
  const { value } = await ElMessageBox.prompt(
    approve ? '填写采纳说明（可留空）' : '填写驳回原因（可留空）',
    approve ? '采纳建议' : '驳回建议',
    { inputValue: '', confirmButtonText: approve ? '采纳' : '驳回', cancelButtonText: '取消' },
  ).catch(() => ({ value: null }))
  if (value === null) return
  await reviewSuggestion(detail.value.id, approve, value)
  ElMessage.success(approve ? '已采纳' : '已驳回')
  await refresh()
}

async function onExecute() {
  if (!detail.value) return
  const { value } = await ElMessageBox.prompt('填写执行说明（可留空）', '执行登记', {
    inputValue: '',
    confirmButtonText: '登记',
    cancelButtonText: '取消',
  }).catch(() => ({ value: null }))
  if (value === null) return
  await executeSuggestion(detail.value.id, value)
  ElMessage.success('已登记执行')
  await refresh()
}

async function onEvaluate() {
  if (!detail.value) return
  const { value } = await ElMessageBox.prompt(
    '填写复盘说明（可留空）。评估基于执行前后等长窗口的前后对比，非严格因果。',
    '效果评估',
    { inputValue: '', confirmButtonText: '评估并归档', cancelButtonText: '取消' },
  ).catch(() => ({ value: null }))
  if (value === null) return
  await evaluateSuggestion(detail.value.id, value)
  ElMessage.success('评估完成，工单已闭环')
  await refresh()
}

async function onCreate() {
  if (!form.title.trim()) {
    ElMessage.warning('请填写标题')
    return
  }
  creating.value = true
  try {
    await createSuggestion({ type: form.type, title: form.title.trim(), content: { note: form.note } })
    ElMessage.success('已创建草稿工单')
    createDialog.value = false
    form.title = ''
    form.note = ''
    await load()
  } finally {
    creating.value = false
  }
}

onMounted(load)
</script>

<template>
  <div v-loading="loading">
    <el-card style="margin-bottom: 12px">
      <div style="display: flex; justify-content: space-between; align-items: center">
        <div>
          <span style="font-weight: 600">建议工单 · 决策闭环</span>
          <span style="color: #909399; font-size: 12px; margin-left: 8px">
            草稿 → 人工审批 → 执行登记 → 效果评估 → 归档
          </span>
        </div>
        <el-button type="primary" :disabled="!canManage" @click="createDialog = true">新建建议</el-button>
      </div>
    </el-card>

    <div style="display: flex; gap: 12px; align-items: flex-start">
      <div
        v-for="col in grouped"
        :key="col.status"
        style="flex: 1 1 0; min-width: 0; background: #f0f2f5; border-radius: 8px; padding: 8px"
      >
        <div style="display: flex; justify-content: space-between; padding: 4px 6px 8px">
          <span :style="{ color: col.color, fontWeight: 600, fontSize: '13px' }">{{ col.label }}</span>
          <span style="color: #909399; font-size: 12px">{{ col.items.length }}</span>
        </div>
        <el-card
          v-for="item in col.items"
          :key="item.id"
          shadow="hover"
          style="margin-bottom: 8px; cursor: pointer"
          body-style="padding: 10px"
          @click="openDetail(item)"
        >
          <div style="font-size: 13px; font-weight: 600; line-height: 1.4">
            #{{ item.id }} {{ item.title }}
          </div>
          <div style="margin-top: 6px; display: flex; justify-content: space-between; align-items: center">
            <el-tag size="small" type="info">{{ TYPE_LABELS[item.type] ?? item.type }}</el-tag>
            <span style="color: #909399; font-size: 11px">{{ item.created_by_name }}</span>
          </div>
          <div style="color: #c0c4cc; font-size: 11px; margin-top: 4px">
            {{ item.created_at.slice(0, 16) }}
          </div>
        </el-card>
        <div v-if="!col.items.length" style="color: #c0c4cc; font-size: 12px; text-align: center; padding: 16px 0">
          暂无
        </div>
      </div>
    </div>

    <el-drawer v-model="drawer" size="48%" :title="detail ? `#${detail.id} ${detail.title}` : '工单详情'">
      <template v-if="detail">
        <el-descriptions :column="3" border style="margin-bottom: 12px">
          <el-descriptions-item label="状态">{{ detail.status_label }}</el-descriptions-item>
          <el-descriptions-item label="类型">{{ TYPE_LABELS[detail.type] ?? detail.type }}</el-descriptions-item>
          <el-descriptions-item label="创建人">{{ detail.created_by_name }}</el-descriptions-item>
          <el-descriptions-item label="审批人">{{ detail.reviewed_by_name || '-' }}</el-descriptions-item>
          <el-descriptions-item label="执行时间">{{ detail.executed_at?.slice(0, 19) || '-' }}</el-descriptions-item>
          <el-descriptions-item label="评估窗口">{{ detail.evaluate_after_days }} 天</el-descriptions-item>
        </el-descriptions>

        <div v-if="canManage" style="margin-bottom: 12px; display: flex; gap: 8px">
          <template v-if="detail.status === 'draft'">
            <el-button type="success" size="small" @click="onReview(true)">采纳</el-button>
            <el-button type="danger" size="small" @click="onReview(false)">驳回</el-button>
          </template>
          <el-button v-if="detail.status === 'approved'" type="primary" size="small" @click="onExecute">
            执行登记
          </el-button>
          <el-button v-if="detail.status === 'in_progress'" type="warning" size="small" @click="onEvaluate">
            效果评估并闭环
          </el-button>
        </div>

        <h4>建议内容</h4>
        <pre style="background: #f5f7fa; padding: 10px; border-radius: 6px; font-size: 12px; white-space: pre-wrap">{{ JSON.stringify(detail.content, null, 2) }}</pre>

        <h4>状态流转</h4>
        <el-timeline>
          <el-timeline-item
            v-for="(e, i) in detail.events"
            :key="i"
            :timestamp="e.created_at"
            :type="e.to === 'closed' ? 'success' : e.to === 'rejected' ? 'danger' : 'primary'"
          >
            {{ e.from_label }} → {{ e.to_label }}（{{ e.operator_name }}）{{ e.note ? `：${e.note}` : '' }}
          </el-timeline-item>
        </el-timeline>

        <template v-if="detail.effects.length">
          <h4>效果归因（前后对比，非严格因果）</h4>
          <el-table :data="detail.effects" size="small">
            <el-table-column label="指标" width="90">
              <template #default="{ row }">{{ METRIC_LABELS[row.metric] ?? row.metric }}</template>
            </el-table-column>
            <el-table-column label="执行前">
              <template #default="{ row }">{{ fmtMetric(row.metric, row.before) }}</template>
            </el-table-column>
            <el-table-column label="执行后">
              <template #default="{ row }">{{ fmtMetric(row.metric, row.after) }}</template>
            </el-table-column>
            <el-table-column label="变化">
              <template #default="{ row }">
                <span :style="{ color: row.delta >= 0 ? '#67c23a' : '#f56c6c' }">
                  {{ fmtDelta(row.metric, row.delta) }}
                </span>
              </template>
            </el-table-column>
          </el-table>
        </template>
      </template>
    </el-drawer>

    <el-dialog v-model="createDialog" title="新建建议" width="480px">
      <el-form label-width="70px">
        <el-form-item label="类型">
          <el-select v-model="form.type" style="width: 100%">
            <el-option v-for="(label, key) in TYPE_LABELS" :key="key" :label="label" :value="key" />
          </el-select>
        </el-form-item>
        <el-form-item label="标题">
          <el-input v-model="form.title" maxlength="120" placeholder="如：汰换滞销菜品干炒牛河" />
        </el-form-item>
        <el-form-item label="说明">
          <el-input v-model="form.note" type="textarea" :rows="3" placeholder="依据与动作（可留空）" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createDialog = false">取消</el-button>
        <el-button type="primary" :loading="creating" @click="onCreate">创建草稿</el-button>
      </template>
    </el-dialog>
  </div>
</template>