<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { marked } from 'marked'
import { fetchReport, fetchReports, generateWeekly } from '../api/reports'
import type { ReportDetail, ReportInfo } from '../api/types'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const canManage = computed(() => ['admin', 'manager'].includes(auth.user?.role || ''))

const reports = ref<ReportInfo[]>([])
const detail = ref<ReportDetail | null>(null)
const days = ref(7)
const loading = ref(false)
const generating = ref(false)

const html = computed(() =>
  detail.value ? (marked.parse(detail.value.content_md, { async: false }) as string) : '',
)

async function loadList() {
  reports.value = await fetchReports()
}

async function openReport(report: ReportInfo) {
  detail.value = await fetchReport(report.id)
}

async function generate() {
  generating.value = true
  try {
    const report = await generateWeekly({ days: days.value })
    detail.value = report
    await loadList()
    ElMessage.success('周报已生成')
  } catch {
    // 错误提示由 http 拦截器统一处理
  } finally {
    generating.value = false
  }
}

function exportMarkdown() {
  if (!detail.value) return
  const blob = new Blob([detail.value.content_md], { type: 'text/markdown;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = `食堂经营周报-${detail.value.period}.md`
  link.click()
  URL.revokeObjectURL(url)
}

onMounted(async () => {
  loading.value = true
  try {
    await loadList()
    if (reports.value.length) await openReport(reports.value[0])
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div v-loading="loading" style="display: flex; gap: 12px; align-items: flex-start">
    <el-card style="width: 260px; flex-shrink: 0" body-style="padding: 0">
      <div style="padding: 12px; border-bottom: 1px solid #eee">
        <div style="display: flex; gap: 8px">
          <el-select v-model="days" style="width: 110px">
            <el-option v-for="d in [7, 14, 30]" :key="d" :label="`近 ${d} 天`" :value="d" />
          </el-select>
          <el-button type="primary" :loading="generating" :disabled="!canManage" @click="generate">
            生成周报
          </el-button>
        </div>
        <div v-if="!canManage" style="color: #909399; font-size: 12px; margin-top: 8px">
          只读角色不能生成报告
        </div>
      </div>
      <div style="max-height: calc(100vh - 240px); overflow-y: auto">
        <div
          v-for="r in reports"
          :key="r.id"
          :style="{
            padding: '10px 12px',
            cursor: 'pointer',
            background: detail?.id === r.id ? '#ecf5ff' : 'transparent',
            borderLeft: detail?.id === r.id ? '3px solid #409eff' : '3px solid transparent',
          }"
          @click="openReport(r)"
        >
          <div style="font-size: 13px; font-weight: 600">#{{ r.id }} {{ r.period }}</div>
          <div style="font-size: 11px; color: #909399; margin-top: 2px">{{ r.created_at.slice(0, 16) }}</div>
        </div>
        <div v-if="!reports.length" style="color: #c0c4cc; font-size: 12px; text-align: center; padding: 20px 0">
          暂无报告，点击上方生成
        </div>
      </div>
    </el-card>

    <el-card style="flex: 1; min-width: 0">
      <template v-if="detail">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px">
          <div>
            <span style="font-weight: 600">周报 #{{ detail.id }}</span>
            <span style="color: #909399; font-size: 12px; margin-left: 8px">{{ detail.period }}</span>
          </div>
          <el-button size="small" @click="exportMarkdown">导出 Markdown</el-button>
        </div>
        <div class="markdown-body" data-testid="report-content" v-html="html" />
      </template>
      <el-empty v-else description="选择或生成一份周报" />
    </el-card>
  </div>
</template>

<style scoped>
.markdown-body {
  line-height: 1.8;
  font-size: 14px;
  color: #303133;
}
.markdown-body :deep(h1) {
  font-size: 22px;
  border-bottom: 1px solid #eee;
  padding-bottom: 8px;
}
.markdown-body :deep(h2) {
  font-size: 17px;
  margin-top: 20px;
}
.markdown-body :deep(table) {
  border-collapse: collapse;
  width: 100%;
  margin: 8px 0;
}
.markdown-body :deep(th),
.markdown-body :deep(td) {
  border: 1px solid #ebeef5;
  padding: 6px 10px;
  text-align: left;
}
.markdown-body :deep(th) {
  background: #f5f7fa;
}
.markdown-body :deep(blockquote) {
  margin: 12px 0;
  padding: 8px 12px;
  background: #f5f7fa;
  border-left: 3px solid #dcdfe6;
  color: #909399;
}
</style>