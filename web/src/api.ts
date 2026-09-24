// Every call the dashboard makes. One place, so the contract is easy to check.
import type {
  Decision, DispatchRow, HeatRow, HistoryPoint, Place, Totals, Truck, TruckEvent,
} from './types'

const BASE = import.meta.env.VITE_API_BASE ?? ''

async function get<T>(path: string): Promise<T> {
  const r = await fetch(`${BASE}${path}`)
  if (!r.ok) throw new Error(`${path} -> ${r.status}`)
  return r.json() as Promise<T>
}

async function post<T>(path: string, body: unknown = {}): Promise<T> {
  const r = await fetch(`${BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!r.ok) throw new Error(`${path} -> ${r.status}`)
  return r.json() as Promise<T>
}

export const api = {
  fleet: () => get<{ demo_speed: number; map_speed: number; real_truck: string; trucks: Truck[]; totals: Totals }>('/api/fleet'),
  history: (id: string) => get<{ points: HistoryPoint[]; events: TruckEvent[]; alert_limit_c: number; ideal_temp_c: number }>(`/api/trucks/${id}/history`),
  places: () => get<{ places: Place[] }>('/api/places'),
  routes: () => get<GeoJSON.FeatureCollection>('/api/routes'),
  heat: () => get<{ rows: HeatRow[]; current: HeatRow[]; source: string }>('/api/heat'),
  dispatch: () => get<{ suggestions: DispatchRow[] }>('/api/dispatch'),
  events: () => get<{ events: TruckEvent[] }>('/api/events'),
  decisions: () => get<{ decisions: Decision[] }>('/api/decisions'),
  impact: () => get<any>('/api/impact'),
  audit: () => get<{ records: any[]; chain_ok: boolean; broken_at: number | null }>('/api/audit'),

  approve: (id: string, chosen: string, by = 'dispatcher') =>
    post<{ ok: boolean; decision: Decision; truck: Truck }>(`/api/decisions/${id}/approve`, { chosen, approved_by: by }),
  fault: (truck_id: string, fault: string, on: boolean) =>
    post<{ ok: boolean }>('/api/demo/fault', { truck_id, fault, on }),
  backup: (on: boolean) => post<{ ok: boolean }>('/api/demo/backup', { on }),
  reset: () => post<{ ok: boolean }>('/api/demo/reset'),

  wsUrl: () => {
    const base = BASE || window.location.origin
    return base.replace(/^http/, 'ws') + '/ws'
  },
  trackUrl: (id: string) => `${BASE || window.location.origin}/track/${id}`,
}
