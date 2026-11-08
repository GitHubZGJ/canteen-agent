import { get, post } from './http'
import type { ReportDetail, ReportInfo } from './types'

export const fetchReports = (limit = 20) => get<ReportInfo[]>('/api/reports', { limit })
export const fetchReport = (id: number) => get<ReportDetail>(`/api/reports/${id}`)
export const generateWeekly = (body: { days: number }) =>
  post<ReportDetail>('/api/reports/weekly', body)