<script setup lang="ts">
import { computed, ref } from 'vue'
import { ElMessage, type UploadFile } from 'element-plus'
import { downloadTemplate, generateData, importDataFile } from '../api/data'
import type { GenerateResult, ImportResult } from '../api/types'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const canManage = computed(() => ['admin', 'manager'].includes(auth.user?.role || ''))

const KIND_LABELS: Record<string, string> = {
  dishes: '菜品（主数据）',
  orders: '订单（每行一笔单菜品订单）',
  reviews: '评价',
}

const days = ref(180)
const seed = ref(42)
const endDate = ref('')
const reset = ref(false)
const generating = ref(false)
const generateResult = ref<GenerateResult | null>(null)

const kind = ref('dishes')
const file = ref<File | null>(null)
const importing = ref(false)
const importResult = ref<ImportResult | null>(null)

async function onGenerate() {
  generating.value = true
  try {
    generateResult.value = await generateData({
      days: days.value,
      seed: seed.value,
      end_date: endDate.value || null,
      reset: reset.value,
    })
    ElMessage.success('模拟数据生成完成')
  } catch (err) {
    ElMessage.error((err as Error).message)
  } finally {
    generating.value = false
  }
}

function onFileChange(uploadFile: UploadFile) {
  file.value = (uploadFile.raw as File) || null
  importResult.value = null
}

async function onImport() {
  if (!file.value) {
    ElMessage.warning('请先选择 CSV 文件')
    return
  }
  importing.value = true
  try {
    importResult.value = await importDataFile(kind.value, file.value)
    if (importResult.value.error_count) {
      ElMessage.warning(`导入完成：成功 ${importResult.value.imported} 行，失败 ${importResult.value.error_count} 行`)
    } else {
      ElMessage.success(`导入成功 ${importResult.value.imported} 行`)
    }
  } catch (err) {
    ElMessage.error((err as Error).message)
  } finally {
    importing.value = false
  }
}

async function onDownloadTemplate() {
  try {
    await downloadTemplate(kind.value)
  } catch (err) {
    ElMessage.error((err as Error).message)
  }
}
</script>

<template>
  <div>
    <el-row :gutter="12">
      <el-col :span="12">
        <el-card>
          <div class="card-title">生成模拟经营数据</div>
          <p style="color: #909399; font-size: 12px">
            固定种子可复现；180 天约 26 万单，耗时约 15～30 秒。已有数据时必须勾选重置，重置会清空经营数据（保留用户）。
          </p>
          <el-form label-width="90px">
            <el-form-item label="天数">
              <el-input-number v-model="days" :min="30" :max="365" />
            </el-form-item>
            <el-form-item label="随机种子">
              <el-input-number v-model="seed" :min="0" :max="999999" />
            </el-form-item>
            <el-form-item label="截止日期">
              <el-date-picker v-model="endDate" type="date" value-format="YYYY-MM-DD" placeholder="默认今天" />
            </el-form-item>
            <el-form-item label="清空重建">
              <el-switch v-model="reset" />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" :loading="generating" :disabled="!canManage" @click="onGenerate">
                生成数据
              </el-button>
            </el-form-item>
          </el-form>
          <el-alert
            v-if="generateResult"
            type="success"
            :closable="false"
            :title="`生成完成：${generateResult.orders.toLocaleString()} 单订单，${generateResult.order_item.toLocaleString()} 条明细，${generateResult.review.toLocaleString()} 条评价`"
          >
            <div style="font-size: 12px">
              区间 {{ generateResult.start }} ～ {{ generateResult.end }}，浪费记录
              {{ generateResult.waste_record.toLocaleString() }} 条。
            </div>
          </el-alert>
        </el-card>
      </el-col>

      <el-col :span="12">
        <el-card>
          <div class="card-title">导入 CSV</div>
          <p style="color: #909399; font-size: 12px">
            逐行校验：合法行入库，错误行附带行号与原因返回；支持 UTF-8 与 GB18030 编码，单次最多 5000 行。
          </p>
          <el-form label-width="90px">
            <el-form-item label="导入类型">
              <el-select v-model="kind" style="width: 100%">
                <el-option v-for="(label, key) in KIND_LABELS" :key="key" :label="label" :value="key" />
              </el-select>
            </el-form-item>
            <el-form-item label="模板">
              <el-button @click="onDownloadTemplate">下载 {{ kind }} 模板</el-button>
            </el-form-item>
            <el-form-item label="文件">
              <el-upload
                :auto-upload="false"
                :limit="1"
                accept=".csv"
                :on-change="onFileChange"
                :on-remove="() => (file = null)"
              >
                <el-button>选择 CSV 文件</el-button>
              </el-upload>
            </el-form-item>
            <el-form-item>
              <el-button type="primary" :loading="importing" :disabled="!canManage" @click="onImport">
                开始导入
              </el-button>
            </el-form-item>
          </el-form>

          <template v-if="importResult">
            <el-alert
              :type="importResult.error_count ? 'warning' : 'success'"
              :closable="false"
              :title="`共 ${importResult.total} 行：成功 ${importResult.imported} 行，失败 ${importResult.error_count} 行`"
              style="margin-bottom: 8px"
            />
            <el-table v-if="importResult.errors.length" :data="importResult.errors" size="small" max-height="220">
              <el-table-column prop="row" label="行号" width="80" />
              <el-table-column prop="msg" label="失败原因" />
            </el-table>
          </template>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<style scoped>
.card-title {
  font-weight: 600;
  margin-bottom: 8px;
}
</style>