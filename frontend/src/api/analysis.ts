import { get } from './http'
import type {
  DishDetail,
  DishPage,
  NutritionAnalysis,
  Portfolio,
  ReviewsAnalysis,
  WasteAnalysis,
} from './types'

export const fetchPortfolio = (params?: object) => get<Portfolio>('/api/analysis/portfolio', params)
export const fetchWaste = (params?: object) => get<WasteAnalysis>('/api/analysis/waste', params)
export const fetchReviews = (params?: object) => get<ReviewsAnalysis>('/api/analysis/reviews', params)
export const fetchNutrition = (params?: object) =>
  get<NutritionAnalysis>('/api/analysis/nutrition', params)
export const fetchDishes = (params?: object) => get<DishPage>('/api/dishes', params)
export const fetchDishDetail = (id: number, params?: object) =>
  get<DishDetail>(`/api/dishes/${id}/analysis`, params)