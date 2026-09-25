import type { TruckDetail, TruckSummary, TelemetryPoint } from '../types'
import { apiClient } from './client'

export async function getTrucks(): Promise<TruckSummary[]> {
  const { data } = await apiClient.get<{ trucks: TruckSummary[] }>('/trucks')
  return data.trucks
}

export async function getTruck(id: string): Promise<TruckDetail> {
  const { data } = await apiClient.get<TruckDetail>(`/trucks/${id}`)
  return data
}

export async function getTelemetry(
  id: string,
  from: string,
  to: string,
): Promise<TelemetryPoint[]> {
  const { data } = await apiClient.get<TelemetryPoint[]>(
    `/trucks/${id}/telemetry`,
    { params: { from, to } },
  )
  return data
}
