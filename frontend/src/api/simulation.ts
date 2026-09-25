import type { SimulationScenario } from '../types'
import { apiClient } from './client'

export async function startSimulation() {
  const { data } = await apiClient.post('/simulation/start')
  return data
}

export async function stopSimulation() {
  const { data } = await apiClient.post('/simulation/stop')
  return data
}

export async function triggerScenario(truckId: string, scenario: SimulationScenario) {
  const { data } = await apiClient.post('/simulation/scenario', { truckId, scenario })
  return data
}
