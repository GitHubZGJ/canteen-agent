import { get, post } from './http'
import type {
  DishOption,
  ForecastCreateResult,
  ForecastRunDetail,
  ForecastRunListItem,
  OptimizationRunListItem,
  OptimizationRunResult,
} from './types'

export const fetchDishOptions = () => get<DishOption[]>('/api/dishes/options')

export const createForecastRun = (body: object) =>
  post<ForecastCreateResult>('/api/forecast/runs', body)
export const fetchForecastDetail = (id: number) =>
  get<ForecastRunDetail>(`/api/forecast/runs/${id}`)
export const fetchForecastRuns = (limit = 20) =>
  get<ForecastRunListItem[]>('/api/forecast/runs', { limit })

export const createOptimizationRun = (body: object) =>
  post<OptimizationRunResult>('/api/optimization/runs', body)
export const fetchOptimizationDetail = (id: number) =>
  get<OptimizationRunResult>(`/api/optimization/runs/${id}`)
export const fetchOptimizationRuns = (limit = 20) =>
  get<OptimizationRunListItem[]>('/api/optimization/runs', { limit })