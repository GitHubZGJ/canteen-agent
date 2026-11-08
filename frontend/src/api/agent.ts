import { get, post } from './http'
import type { AgentEvent, AgentMessages, AgentSessionInfo } from './types'

export const fetchAgentSessions = () => get<AgentSessionInfo[]>('/api/agent/sessions')
export const createAgentSession = (body: object = { mode: 'auto' }) =>
  post<AgentSessionInfo>('/api/agent/sessions', body)
export const fetchAgentMessages = (id: number) =>
  get<AgentMessages>(`/api/agent/sessions/${id}/messages`)

// SSE 流：EventSource 无法带 Authorization 头，改用 fetch 读流
export async function streamAgentMessage(
  sessionId: number,
  content: string,
  onEvent: (event: AgentEvent) => void,
): Promise<void> {
  const token = localStorage.getItem('token') || ''
  const resp = await fetch(`/api/agent/sessions/${sessionId}/messages`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
    body: JSON.stringify({ content }),
  })
  if (!resp.ok || !resp.body) {
    const body = await resp.json().catch(() => null)
    throw new Error(body?.msg || `请求失败（HTTP ${resp.status}）`)
  }
  const reader = resp.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  for (;;) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    const blocks = buffer.split('\n\n')
    buffer = blocks.pop() || ''
    for (const block of blocks) {
      for (const line of block.split('\n')) {
        if (line.startsWith('data: ')) {
          try {
            onEvent(JSON.parse(line.slice(6)) as AgentEvent)
          } catch {
            // 忽略不完整片段
          }
        }
      }
    }
  }
}