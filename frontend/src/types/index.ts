export type RiskLevel = 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL'
export type IncidentSeverity = 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL'
export type IncidentStatus = 'OPEN' | 'RESOLVED'

export interface TruckSummary {
  id: string
  name: string
  latitude: number
  longitude: number
  speedKmh: number
  temperatureC: number
  humidityPct: number
  doorOpen: boolean
  refrigerationOn: boolean
  riskScore: number
  riskLevel: RiskLevel
  activeIncident: boolean
}

export interface TruckState {
  id: string
  productBatchId: string
  latitude: number
  longitude: number
  temperatureC: number
  humidityPct: number
  speedKmh: number
  gForce: number
  doorOpen: boolean
  refrigerationOn: boolean
}

export interface BatchInfo {
  id: string
  product: string
  quantityKg: number
  safeMinTempC: number
  safeMaxTempC: number
  initialShelfLifeHours: number
}

export interface Prediction {
  thermalExposure: number
  remainingShelfLifeHours: number
  spoilageProbability: number
  confidence: number
  riskScore: number
  riskLevel: RiskLevel
}

export interface Recommendation {
  action: string
  destinationId?: string
  etaMinutes?: number
  expectedLossPercent: number
  foodSavedKg: number
  reasoning: string
}

export interface TruckDetail {
  truck: TruckState
  batch: BatchInfo
  prediction: Prediction
  recommendation: Recommendation
}

export interface TelemetryPoint {
  timestamp: string
  temperatureC: number
  humidityPct: number
  latitude: number
  longitude: number
  speedKmh: number
  gForce: number
  doorOpen: boolean
}

export interface Incident {
  id: string
  truckId: string
  batchId: string
  severity: IncidentSeverity
  type: string
  message: string
  createdAt: string
  status: IncidentStatus
}

export type WsEventType =
  | 'TRUCK_STATE_UPDATED'
  | 'INCIDENT_CREATED'
  | 'INCIDENT_UPDATED'
  | 'RECOMMENDATION_UPDATED'
  | 'FOOD_LOSS_UPDATED'

export interface WsEvent {
  event: WsEventType
  truckId?: string
  timestamp: string
  temperatureC?: number
  humidityPct?: number
  latitude?: number
  longitude?: number
  riskScore?: number
  riskLevel?: RiskLevel
  speedKmh?: number
}

export type SimulationScenario =
  | 'NORMAL'
  | 'TEMPERATURE_EXCURSION'
  | 'DOOR_LEFT_OPEN'
  | 'REFRIGERATION_FAILURE'
  | 'TRAFFIC_DELAY'
  | 'COMBINED_FAILURE'

export interface DashboardStats {
  activeTrucks: number
  trucksAtRisk: number
  foodSavedKg: number
  lossPrevented: number
}
