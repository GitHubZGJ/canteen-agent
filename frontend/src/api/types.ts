export interface UserInfo {
  id: number
  username: string
  role: string
}

export interface DateRange {
  start: string
  end: string
}

export interface KpiValue {
  value: number | null
  prev: number | null
  delta: number | null
}

export interface SlotItem {
  slot: string
  label: string
  orders: number
  revenue: number
}

export interface Overview {
  range: DateRange
  kpis: Record<string, KpiValue>
  slots: SlotItem[]
}

export interface TrendItem {
  date: string
  revenue: number
  orders: number
  avg_value: number
}

export interface RankItem {
  id: number
  name: string
  revenue: number
  quantity: number
}

export interface Heatmap {
  range: DateRange
  days: string[]
  hours: number[]
  data: number[][]
}

export interface DishStat {
  dish_id: number
  name: string
  category: string
  price: number
  stall_id: number
  stall_name: string
  quantity: number
  revenue: number
  margin_rate: number
  avg_rating: number | null
  review_count: number
  prepared: number
  wasted: number
  waste_rate: number
  quadrant: string
  abc: string
  revenue_share: number
}

export interface SlowMover {
  dish_id: number
  name: string
  stall_name: string
  avg_daily_qty: number
  threshold_qty: number
}

export interface Portfolio {
  range: DateRange
  thresholds: { qty_median: number; margin_median: number }
  dishes: DishStat[]
  slow_movers: SlowMover[]
}

export interface WasteDish {
  dish_id: number
  name: string
  stall_name: string
  prepared: number
  wasted: number
  waste_rate: number
}

export interface WasteAnalysis {
  range: DateRange
  totals: { prepared: number; wasted: number; rate: number }
  top_dishes: WasteDish[]
  alerts: WasteDish[]
  by_reason: { reason: string; wasted: number }[]
  trend: { date: string; prepared: number; wasted: number; rate: number }[]
}

export interface ReviewSummary {
  count: number
  avg_rating: number | null
  rating_dist: Record<string, number>
  sentiment_dist: Record<string, number>
  tag_counts: Record<string, number>
}

export interface ReviewsAnalysis {
  range: DateRange
  summary: ReviewSummary
  negative_recent: { dish_name: string; rating: number; content: string; created_at: string }[]
}

export interface NutritionAnalysis {
  range: DateRange
  summary: {
    sold_qty: number
    avg_calories: number | null
    avg_protein_g: number | null
    avg_fat_g: number | null
    avg_carbs_g: number | null
  }
  category_share: { category: string; revenue: number; share: number }[]
  light_share: number
}

export interface DishDetail {
  range: DateRange
  dish: { id: number; name: string; category: string; price: number; stall_name: string }
  trend: { date: string; quantity: number; revenue: number }[]
  reviews: {
    summary: ReviewSummary
    recent: { rating: number; content: string; created_at: string }[]
  }
  waste: { prepared: number; wasted: number; rate: number }
}

export interface DishPage {
  range: DateRange
  total: number
  items: DishStat[]
}

export interface DishOption {
  id: number
  name: string
  stall_name: string
}

export interface ForecastMetrics {
  mae: number | null
  mape: number | null
}

export interface ForecastCreateResult {
  run_id: number
  metrics: {
    chosen: ForecastMetrics
    seasonal_naive: ForecastMetrics
    holt_winters: ForecastMetrics
    seasonal_naive_same_subset: ForecastMetrics
    holt_winters_pairs: number
  }
  fallback_count: number
  total_estimated_saving: number
  prep_suggestions: {
    dish_id: number
    avg_daily_forecast: number
    suggested_prep: number
    hist_avg_wasted: number
    estimated_saving: number
  }[]
}

export interface ForecastPoint {
  date: string
  predicted: number
  lower: number
  upper: number
  actual: number
}

export interface ForecastSeries {
  dish_id: number
  dish_name: string
  slot: string
  points: ForecastPoint[]
}

export interface ForecastRunDetail {
  id: number
  dish_id: number | null
  model: string
  mae: number | null
  mape: number | null
  params: {
    horizon?: number
    safety_factor?: number
    fallback_count?: number
    holt_winters?: ForecastMetrics
    seasonal_naive_same_subset?: ForecastMetrics
    holt_winters_pairs?: number
    total_estimated_saving?: number
    prep_suggestions?: {
      dish_id: number
      avg_daily_forecast: number
      suggested_prep: number
      hist_avg_wasted: number
      estimated_saving: number
    }[]
  }
  target_start: string
  target_end: string
  created_at: string
  series: ForecastSeries[]
}

export interface ForecastRunListItem {
  id: number
  dish_id: number | null
  model: string
  mae: number | null
  mape: number | null
  target_start: string
  target_end: string
  created_at: string
}

export interface OptimizationDish {
  dish_id: number
  name: string
  stall_name: string
  score: number
  n_margin: number
  n_satisfaction: number
  n_nutrition: number
  n_waste: number
  action: string
}

export interface OptimizationRunResult {
  run_id: number
  period: DateRange
  counts: Record<string, number>
  protected: number[]
  dishes: OptimizationDish[]
}

export interface OptimizationRunListItem {
  id: number
  scope: string
  weights: Record<string, number>
  counts: Record<string, number>
  created_at: string
}

export interface AgentSessionInfo {
  id: number
  title: string
  mode: string
  created_at: string
}

export interface ToolCallInfo {
  tool: string
  args: Record<string, unknown>
  status: string
  latency_ms: number
  summary: string
}

export interface AgentHistoryMessage {
  id: number
  role: string
  content: string
  created_at: string
  tool_calls: ToolCallInfo[]
}

export interface AgentMessages {
  mode: string
  title: string
  messages: AgentHistoryMessage[]
}

export type AgentEvent =
  | { type: 'mode'; mode: string }
  | { type: 'tool_call'; tool: string; args: Record<string, unknown> }
  | { type: 'tool_result'; tool: string; status: string; latency_ms: number; summary: string }
  | { type: 'fallback'; reason: string }
  | { type: 'message'; content: string }
  | { type: 'done'; message_id: number; mode: string }
  | { type: 'error'; message: string }

export interface SuggestionInfo {
  id: number
  type: string
  title: string
  content: Record<string, unknown>
  status: string
  status_label: string
  created_by: number
  created_by_name: string
  reviewed_by: number | null
  reviewed_by_name: string
  reviewed_at: string | null
  executed_at: string | null
  evaluate_after_days: number
  created_at: string
}

export interface SuggestionDetail extends SuggestionInfo {
  events: {
    from: string
    to: string
    from_label: string
    to_label: string
    operator: number
    operator_name: string
    note: string
    created_at: string
  }[]
  effects: {
    metric: string
    before: number
    after: number
    delta: number
    evaluated_at: string
  }[]
}

export interface SuggestionPage {
  total: number
  items: SuggestionInfo[]
}

export interface ReportInfo {
  id: number
  type: string
  period: string
  created_at: string
}

export interface ReportDetail extends ReportInfo {
  content_md: string
}

export interface GenerateResult {
  canteen: number
  stall: number
  dish: number
  orders: number
  order_item: number
  review: number
  waste_record: number
  start: string
  end: string
}

export interface ImportResult {
  total: number
  imported: number
  error_count: number
  errors: { row: number; msg: string }[]
}