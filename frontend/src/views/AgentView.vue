<script setup lang="ts">
import { computed, nextTick, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import {
  createAgentSession,
  fetchAgentMessages,
  fetchAgentSessions,
  streamAgentMessage,
} from '../api/agent'
import type { AgentEvent, AgentSessionInfo, ToolCallInfo } from '../api/types'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()

interface UiMessage {
  role: 'user' | 'assistant'
  content: string
  toolCalls: ToolCallInfo[]
  streaming?: boolean
  fallback?: string
}

const sessions = ref<AgentSessionInfo[]>([])
const current = ref<AgentSessionInfo | null>(null)
const messages = ref<UiMessage[]>([])
const input = ref('')
const sending = ref(false)
const chatBox = ref<HTMLDivElement>()

const modeLabel = computed(() => {
  if (!current.value) return ''
  return current.value.mode === 'llm' ? '大模型模式' : '规则模式'
})

const examples = [
  '看看最近 30 天的经营指标',
  '分析菜品结构，有哪些滞销菜',
  '评价和浪费情况怎么样',
  '帮我创建建议',
  '生成上周经营周报',
]

async function loadSessions() {
  sessions.value = await fetchAgentSessions()
}

async function openSession(session: AgentSessionInfo) {
  if (sending.value) return
  current.value = session
  const data = await fetchAgentMessages(session.id)
  messages.value = data.messages
    .filter((m) => m.role !== 'tool')
    .map((m) => ({ role: m.role as 'user' | 'assistant', content: m.content, toolCalls: m.tool_calls || [] }))
  scrollDown()
}

async function newSession() {
  const session = await createAgentSession({ mode: 'auto' })
  await loadSessions()
  await openSession(session)
}

async function send() {
  const text = input.value.trim()
  if (!text || !current.value || sending.value) return
  input.value = ''
  sending.value = true
  messages.value.push({ role: 'user', content: text, toolCalls: [] })
  const assistant: UiMessage = { role: 'assistant', content: '', toolCalls: [], streaming: true }
  messages.value.push(assistant)
  scrollDown()
  try {
    await streamAgentMessage(current.value.id, text, (event: AgentEvent) => {
      if (event.type === 'mode') {
        if (current.value) current.value.mode = event.mode
      } else if (event.type === 'tool_call') {
        assistant.toolCalls.push({
          tool: event.tool, args: event.args, status: 'running', latency_ms: 0, summary: '',
        })
      } else if (event.type === 'tool_result') {
        const target = [...assistant.toolCalls]
          .reverse()
          .find((t) => t.tool === event.tool && t.status === 'running')
        if (target) {
          target.status = event.status
          target.latency_ms = event.latency_ms
          target.summary = event.summary
        }
      } else if (event.type === 'message') {
        assistant.content = event.content
      } else if (event.type === 'fallback') {
        assistant.fallback = event.reason
      } else if (event.type === 'error') {
        assistant.content = event.message
      }
      scrollDown()
    })
  } catch (err) {
    ElMessage.error((err as Error).message)
    assistant.content = assistant.content || '对话失败，请重试。'
  } finally {
    assistant.streaming = false
    sending.value = false
    scrollDown()
  }
}

function scrollDown() {
  nextTick(() => {
    if (chatBox.value) chatBox.value.scrollTop = chatBox.value.scrollHeight
  })
}

function useExample(text: string) {
  input.value = text
}

onMounted(async () => {
  await loadSessions()
  if (sessions.value.length) await openSession(sessions.value[0])
})
</script>

<template>
  <div style="display: flex; gap: 12px; height: calc(100vh - 120px)">
    <el-card style="width: 240px; flex-shrink: 0" body-style="padding: 0">
      <div style="padding: 12px">
        <el-button type="primary" style="width: 100%" @click="newSession">新建会话</el-button>
      </div>
      <div style="overflow-y: auto; max-height: calc(100vh - 220px)">
        <div
          v-for="s in sessions"
          :key="s.id"
          :style="{
            padding: '10px 12px',
            cursor: 'pointer',
            background: current?.id === s.id ? '#ecf5ff' : 'transparent',
            borderLeft: current?.id === s.id ? '3px solid #409eff' : '3px solid transparent',
          }"
          @click="openSession(s)"
        >
          <div style="font-size: 13px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap">
            {{ s.title }}
          </div>
          <div style="font-size: 11px; color: #909399; margin-top: 2px">
            {{ s.mode === 'llm' ? '大模型' : '规则' }} · {{ s.created_at.slice(0, 16) }}
          </div>
        </div>
      </div>
    </el-card>

    <el-card style="flex: 1; display: flex; flex-direction: column" body-style="padding: 0; display: flex; flex-direction: column; height: 100%">
      <div style="padding: 10px 16px; border-bottom: 1px solid #eee; display: flex; justify-content: space-between; align-items: center">
        <span style="font-weight: 600">智能助手</span>
        <span>
          <el-tag v-if="auth.user?.role === 'viewer'" type="info" size="small" style="margin-right: 8px">
            只读角色：可查询，不能创建建议
          </el-tag>
          <el-tag :type="current?.mode === 'llm' ? 'success' : 'info'" size="small">{{ modeLabel }}</el-tag>
        </span>
      </div>

      <div ref="chatBox" style="flex: 1; overflow-y: auto; padding: 16px; background: #fafafa">
        <el-empty v-if="!messages.length" description="向智能体提问，或用下方示例开始" />
        <div v-for="(m, idx) in messages" :key="idx" style="margin-bottom: 14px">
          <div v-if="m.role === 'user'" style="text-align: right">
            <span style="display: inline-block; background: #409eff; color: #fff; padding: 8px 12px; border-radius: 8px; max-width: 70%; text-align: left">
              {{ m.content }}
            </span>
          </div>
          <div v-else>
            <div v-if="m.fallback" style="margin-bottom: 6px">
              <el-tag type="warning" size="small">{{ m.fallback }}</el-tag>
            </div>
            <div v-for="(t, ti) in m.toolCalls" :key="ti" class="tool-card" data-testid="agent-tool">
              <div style="display: flex; justify-content: space-between; align-items: center">
                <span>
                  <el-tag :type="t.status === 'ok' ? 'success' : t.status === 'running' ? 'info' : 'danger'" size="small">
                    {{ t.status === 'running' ? '调用中' : t.status === 'ok' ? '成功' : '失败' }}
                  </el-tag>
                  <span style="font-weight: 600; margin-left: 8px; font-size: 13px">{{ t.tool }}</span>
                </span>
                <span style="color: #909399; font-size: 12px">{{ t.latency_ms }} ms</span>
              </div>
              <div style="color: #909399; font-size: 12px; margin-top: 4px; word-break: break-all">
                参数：{{ JSON.stringify(t.args) }}
              </div>
              <div v-if="t.summary" style="color: #606266; font-size: 12px; margin-top: 2px; word-break: break-all">
                结果：{{ t.summary.slice(0, 160) }}{{ t.summary.length > 160 ? '…' : '' }}
              </div>
            </div>
            <div
              v-if="m.content || m.streaming"
              data-testid="agent-answer"
              style="background: #fff; border: 1px solid #ebeef5; padding: 10px 12px; border-radius: 8px; white-space: pre-wrap; line-height: 1.7"
            >
              {{ m.content }}<span v-if="m.streaming" style="color: #909399">▍</span>
            </div>
          </div>
        </div>
      </div>

      <div style="border-top: 1px solid #eee; padding: 12px 16px">
        <div style="margin-bottom: 8px; display: flex; gap: 6px; flex-wrap: wrap">
          <el-tag
            v-for="ex in examples"
            :key="ex"
            size="small"
            style="cursor: pointer"
            @click="useExample(ex)"
          >
            {{ ex }}
          </el-tag>
        </div>
        <div style="display: flex; gap: 8px">
          <el-input
            v-model="input"
            type="textarea"
            :rows="2"
            maxlength="2000"
            placeholder="输入问题，如：最近经营情况怎么样？"
            @keyup.ctrl.enter="send"
          />
          <el-button type="primary" :loading="sending" :disabled="!current" style="height: auto" @click="send">
            发送
          </el-button>
        </div>
        <div style="color: #c0c4cc; font-size: 11px; margin-top: 6px">
          Ctrl + Enter 发送。智能体只能创建建议草稿，审批与执行由人工完成。
        </div>
      </div>
    </el-card>
  </div>
</template>

<style scoped>
.tool-card {
  background: #fff;
  border: 1px dashed #dcdfe6;
  border-radius: 6px;
  padding: 8px 10px;
  margin-bottom: 8px;
  max-width: 82%;
}
</style>