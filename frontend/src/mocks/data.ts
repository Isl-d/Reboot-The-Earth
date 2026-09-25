import type { Incident, TelemetryPoint, TruckDetail, TruckSummary } from '../types'

export const MOCK_TRUCKS: TruckSummary[] = [
  {
    id: 'T101',
    name: 'Truck T101',
    latitude: 25.2854,
    longitude: 51.531,
    speedKmh: 55,
    temperatureC: 3.1,
    humidityPct: 68,
    doorOpen: false,
    refrigerationOn: true,
    riskScore: 12,
    riskLevel: 'LOW',
    activeIncident: false,
  },
  {
    id: 'T102',
    name: 'Truck T102',
    latitude: 25.2710,
    longitude: 51.5480,
    speedKmh: 42,
    temperatureC: 7.2,
    humidityPct: 74,
    doorOpen: false,
    refrigerationOn: true,
    riskScore: 78,
    riskLevel: 'HIGH',
    activeIncident: true,
  },
  {
    id: 'T103',
    name: 'Truck T103',
    latitude: 25.2990,
    longitude: 51.5100,
    speedKmh: 0,
    temperatureC: 9.4,
    humidityPct: 81,
    doorOpen: true,
    refrigerationOn: false,
    riskScore: 95,
    riskLevel: 'CRITICAL',
    activeIncident: true,
  },
  {
    id: 'T104',
    name: 'Truck T104',
    latitude: 25.2620,
    longitude: 51.5220,
    speedKmh: 38,
    temperatureC: 5.1,
    humidityPct: 72,
    doorOpen: false,
    refrigerationOn: true,
    riskScore: 44,
    riskLevel: 'MEDIUM',
    activeIncident: false,
  },
  {
    id: 'T105',
    name: 'Truck T105',
    latitude: 25.3080,
    longitude: 51.5400,
    speedKmh: 61,
    temperatureC: 2.8,
    humidityPct: 65,
    doorOpen: false,
    refrigerationOn: true,
    riskScore: 8,
    riskLevel: 'LOW',
    activeIncident: false,
  },
]

export const MOCK_TRUCK_DETAIL: TruckDetail = {
  truck: {
    id: 'T102',
    productBatchId: 'CHK-1029',
    latitude: 25.271,
    longitude: 51.548,
    temperatureC: 7.2,
    humidityPct: 74,
    speedKmh: 42,
    gForce: 0.2,
    doorOpen: false,
    refrigerationOn: true,
  },
  batch: {
    id: 'CHK-1029',
    product: 'Fresh Chicken',
    quantityKg: 500,
    safeMinTempC: 0,
    safeMaxTempC: 4,
    initialShelfLifeHours: 72,
  },
  prediction: {
    thermalExposure: 42.8,
    remainingShelfLifeHours: 38,
    spoilageProbability: 0.73,
    confidence: 0.91,
    riskScore: 78,
    riskLevel: 'HIGH',
  },
  recommendation: {
    action: 'DIVERT',
    destinationId: 'WH01',
    etaMinutes: 18,
    expectedLossPercent: 4.1,
    foodSavedKg: 82,
    reasoning:
      'Current temperature (7.2°C) exceeds the safe maximum (4°C) by 3.2°C. Thermal exposure index is 42.8 — above the 35.0 diversion threshold. Estimated remaining safe window is 38 minutes. Nearest compliant storage WH01 is 18 minutes away, leaving a 20-minute safety buffer. Diverting now preserves approximately 82 kg (16.4%) of the batch.',
  },
}

function generateTelemetry(hours = 6): TelemetryPoint[] {
  const now = Date.now()
  const points: TelemetryPoint[] = []
  for (let i = hours * 12; i >= 0; i--) {
    const t = now - i * 5 * 60 * 1000
    const progress = 1 - i / (hours * 12)
    points.push({
      timestamp: new Date(t).toISOString(),
      temperatureC: parseFloat((3.0 + progress * 4.5 + Math.sin(i * 0.4) * 0.3).toFixed(1)),
      humidityPct: Math.round(68 + progress * 8 + Math.sin(i * 0.3) * 2),
      latitude: 25.268 + progress * 0.008,
      longitude: 51.534 + progress * 0.016,
      speedKmh: Math.round(38 + Math.sin(i * 0.5) * 15),
      gForce: parseFloat((0.1 + Math.abs(Math.sin(i * 0.8)) * 0.3).toFixed(2)),
      doorOpen: false,
    })
  }
  return points
}

export const MOCK_TELEMETRY: TelemetryPoint[] = generateTelemetry()

export const MOCK_INCIDENTS: Incident[] = [
  {
    id: 'INC-4921',
    truckId: 'T102',
    batchId: 'CHK-1029',
    severity: 'HIGH',
    type: 'TEMPERATURE_EXCURSION',
    message: 'Temperature has remained above safe range (4°C) for 18 minutes.',
    createdAt: new Date(Date.now() - 18 * 60 * 1000).toISOString(),
    status: 'OPEN',
  },
  {
    id: 'INC-4922',
    truckId: 'T103',
    batchId: 'VEG-0044',
    severity: 'CRITICAL',
    type: 'REFRIGERATION_FAILURE',
    message: 'Refrigeration unit offline. Door sensor reports open. Temperature rising rapidly.',
    createdAt: new Date(Date.now() - 6 * 60 * 1000).toISOString(),
    status: 'OPEN',
  },
  {
    id: 'INC-4910',
    truckId: 'T101',
    batchId: 'MSH-0088',
    severity: 'LOW',
    type: 'TRAFFIC_DELAY',
    message: 'Route delay detected. Estimated 25 minutes behind schedule.',
    createdAt: new Date(Date.now() - 90 * 60 * 1000).toISOString(),
    status: 'RESOLVED',
  },
]

export const MOCK_STATS = {
  activeTrucks: 5,
  trucksAtRisk: 2,
  foodSavedKg: 428,
  lossPrevented: 8420,
}
