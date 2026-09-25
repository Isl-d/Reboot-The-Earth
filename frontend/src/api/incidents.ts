import type { Incident } from '../types'
import { apiClient } from './client'

export async function getIncidents(): Promise<Incident[]> {
  const { data } = await apiClient.get<Incident[]>('/incidents')
  return data
}
