import { get, post } from './http'
import type { SuggestionDetail, SuggestionPage } from './types'

export const fetchSuggestions = (params?: object) =>
  get<SuggestionPage>('/api/suggestions', params)
export const fetchSuggestionDetail = (id: number) =>
  get<SuggestionDetail>(`/api/suggestions/${id}`)
export const createSuggestion = (body: object) => post<SuggestionDetail>('/api/suggestions', body)
export const reviewSuggestion = (id: number, approve: boolean, note = '') =>
  post<SuggestionDetail>(`/api/suggestions/${id}/review`, { approve, note })
export const executeSuggestion = (id: number, note = '') =>
  post<SuggestionDetail>(`/api/suggestions/${id}/execute`, { note })
export const evaluateSuggestion = (id: number, note = '') =>
  post<SuggestionDetail>(`/api/suggestions/${id}/evaluate`, { note })