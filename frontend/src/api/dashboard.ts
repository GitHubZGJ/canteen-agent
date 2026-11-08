import { get } from './http'
import type { Heatmap, Overview, RankItem, TrendItem } from './types'

export const fetchOverview = (params?: object) => get<Overview>('/api/dashboard/overview', params)
export const fetchTrend = (params?: object) =>
  get<{ range: unknown; items: TrendItem[] }>('/api/dashboard/trend', params)
export const fetchRanking = (params?: object) =>
  get<{ items: RankItem[] }>('/api/dashboard/ranking', params)
export const fetchHeatmap = (params?: object) => get<Heatmap>('/api/dashboard/heatmap', params)