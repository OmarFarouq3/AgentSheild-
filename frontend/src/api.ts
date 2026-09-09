export type Health = {
  status: string
  qdrant: boolean
  postgres: boolean
  agent: boolean
  version: string
}

export type ChatResponse = {
  answer: string
  sources: string[]
  tool_calls_made: string[]
  latency_ms: number
}

export type AttackCase = {
  case_id: string
  category: string
  prompt: string
}

export type AttackResult = {
  case_id: string
  category: string
  prompt: string
  outcome: string
  rationale: string
  answer: string
  tool_calls_made: string[]
  latency_ms: number
  transcript: unknown[]
}

export type SuiteReport = {
  mode: string
  total_attacks: number
  succeeded: number
  partial: number
  blocked: number
  attack_success_rate_percent: number
  residual_risk_score_percent: number
  by_category: Record<string, unknown>
  cases: AttackResult[]
  max_tool_calls: number
  success_rate_drop_percentage_points?: number
  residual_risk_drop_percentage_points?: number
  residual_gap_note?: string
  artifacts?: Record<string, unknown>
}

export type SuiteResponse = {
  normal: SuiteReport
  defended: SuiteReport
  residual_risk_drop_percentage_points?: number
  residual_gap_note?: string
}

const apiRoot = (import.meta.env.VITE_API_URL || '/api').replace(/\/$/, '')

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${apiRoot}${path}`, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...init?.headers },
  })
  if (!response.ok) {
    let detail = `Request failed (${response.status})`
    try {
      const body = await response.json()
      detail = body.detail || detail
    } catch {
      // Keep the HTTP status when the server did not return JSON.
    }
    throw new Error(detail)
  }
  return response.json() as Promise<T>
}

export const api = {
  health: () => request<Health>('/health'),
  attackCases: () => request<{ attack_cases: AttackCase[] }>('/security/attack-cases'),
  chat: (query: string, sessionId: string, maxToolCalls: number) =>
    request<ChatResponse>('/chat', {
      method: 'POST',
      body: JSON.stringify({ query, session_id: sessionId, max_tool_calls: maxToolCalls }),
    }),
  attackSuite: (maxToolCalls: number) =>
    request<SuiteResponse>('/security/attack-suite', {
      method: 'POST',
      body: JSON.stringify({ max_tool_calls: maxToolCalls }),
    }),
}
