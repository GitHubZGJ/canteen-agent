import { post } from './http'
import type { GenerateResult, ImportResult } from './types'

export const generateData = (body: object) => post<GenerateResult>('/api/data/generate', body)

export async function importDataFile(kind: string, file: File): Promise<ImportResult> {
  const token = localStorage.getItem('token') || ''
  const form = new FormData()
  form.append('kind', kind)
  form.append('file', file)
  const resp = await fetch('/api/data/import', {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}` },
    body: form,
  })
  const body = await resp.json().catch(() => null)
  if (!body) throw new Error(`导入失败（HTTP ${resp.status}）`)
  if (!resp.ok || body.code !== 0) throw new Error(body.msg || `导入失败（HTTP ${resp.status}）`)
  return body.data as ImportResult
}

export async function downloadTemplate(kind: string): Promise<void> {
  const token = localStorage.getItem('token') || ''
  const resp = await fetch(`/api/data/templates/${kind}`, {
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!resp.ok) throw new Error(`模板下载失败（HTTP ${resp.status}）`)
  const blob = await resp.blob()
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = `${kind}-template.csv`
  link.click()
  URL.revokeObjectURL(url)
}