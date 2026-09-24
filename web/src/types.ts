// Mirrors the backend's JSON. Keep this file and CLAUDE.md section 6 in step.

export type Risk = 'green' | 'amber' | 'red' | 'unknown'
export type Verb = 'continue' | 'reroute' | 'sell' | 'donate' | 'hold'

export interface Truck {
  truck_id: string
  route_id: string
  route_name: string
  product: string
  qty_kg: number
  lat: number
  lon: number
  frac: number
  air_c: number | null
  product_c: number | null
  hum_pct: number | null
  door_open: boolean
  src: string
  live_sensor: boolean
  last_ts: number | null
  online: boolean
  alert_limit_c: number
  ideal_temp_c: number
  life_left_h: number
  life_left_days: number
  freshness_pct: number
  aging_speed: number
  hours_to_spoil: number
  remaining_trip_h: number
  life_on_arrival_h: number
  life_on_arrival_days: number
  min_life_on_arrival_days: number
  at_risk: boolean
  risk: Risk
  status: string
  destination_id: string
  destination_name: string
  reroute_geometry: [number, number][] | null
  sensor_ok: boolean
  in_failure: boolean
  decision_id: string | null
}

export interface TruckEvent {
  truck_id: string
  type: 'door' | 'defrost' | 'sensor_fault' | 'failure'
  started_at: number
  ended_at: number | null
  peak_c: number | null
  note: string
  alert: boolean
  seq: number
  duration_s: number | null
}

export interface Option {
  key: string
  action: Verb
  title_en: string
  title_ar: string
  destination_id: string
  destination_name: string
  extra_km: number
  warm_drive_h: number
  remaining_trip_h: number
  life_on_arrival_h: number
  life_on_arrival_days: number
  feasible: boolean
  kg_saved: number
  revenue_qar: number
  extra_cost_qar: number
  markdown_loss_qar: number
  score: number
  co2e_saved_kg: number
  why: string
}

export interface Decision {
  decision_id: string
  truck_id: string
  product: string
  qty_kg: number
  created_at: number
  options: Option[]
  recommended: string
  needs_human_review: boolean
  review_reasons: string[]
  verbs: Record<Verb, string[]>
  chosen: string | null
  chosen_option: Option
  facts: Record<string, unknown>
  text_en: string
  text_ar: string
  text_source: string
  text_note: string
  approved_by: string | null
  approved_at: number | null
  prev_hash: string
  hash: string
}

export interface Totals {
  trucks: number
  kg_monitored: number
  kg_at_risk: number
  kg_saved: number
  value_saved_qar: number
  co2e_saved_kg: number
  decisions: number
  approved: number
  audit_ok: boolean
  demo_speed: number
}

export interface Place {
  place_id: string
  name: string
  type: string
  lat: number
  lon: number
  has_cold_room: boolean
  source: string
}

export interface HistoryPoint {
  ts: number
  air_c: number | null
  product_c: number | null
  hum_pct: number | null
  life_left_h: number
  life_on_arrival_h: number
}

export interface DispatchRow {
  route_id: string
  route: string
  best_departure: string
  mean_temp_best_c: string
  worst_departure: string
  mean_temp_worst_c: string
  freshness_saved_hours_loading: string
  source: string
}

export interface HeatRow {
  route_id: string
  time: string
  air_temp_c: string
  humidity_pct: string
  heat_risk_0_100: string
  source: string
}

export interface WsMessage {
  type: 'hello' | 'reading' | 'event' | 'alert' | 'decision' | 'reset'
  payload: any
  at: number
}
