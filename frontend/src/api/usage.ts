import { requestJson } from './client'

export type UsageCurrency = 'USD'

export interface UsageRecord {
  date: string
  tool_id: string
  model: string | null
  calls: number
  input_tokens: number
  output_tokens: number
  estimated_cost: string | null
  currency: UsageCurrency
  price_known: boolean
}

export interface UsageTotals {
  calls: number
  input_tokens: number
  output_tokens: number
  estimated_cost: string
  currency: UsageCurrency
  unknown_price_calls: number
}

export interface UsageWarning {
  code: string
  message: string
}

export interface UsageResponse {
  days: number
  records: UsageRecord[]
  totals: UsageTotals
  pricing_note: string
  warnings: UsageWarning[]
}

export function getUsage(days: number): Promise<UsageResponse> {
  return requestJson<UsageResponse>('/api/usage?days=' + String(days))
}
