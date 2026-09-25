export const MAP_CENTER: [number, number] = [25.285, 51.51]
export const MAP_ZOOM = 11

export const WAREHOUSES = [
  { id: 'WH01', name: 'Cold Storage WH01', lat: 25.3180, lon: 51.4280 },
  { id: 'WH02', name: 'Cold Storage WH02', lat: 25.2480, lon: 51.5580 },
]

export const HYPERMARKETS = [
  { id: 'Carrefour', name: 'Carrefour City Center', lat: 25.2868, lon: 51.5330 },
  { id: 'LuluHyper', name: 'Lulu Hypermarket',      lat: 25.2612, lon: 51.4980 },
]

export const SUPERMARKETS = [
  { id: 'Megamart', name: 'Megamart Al Gharafa',  lat: 25.3050, lon: 51.5050 },
  { id: 'Family',   name: 'Family Food Centre',   lat: 25.2750, lon: 51.5200 },
]

export const RISK_COLORS: Record<string, string> = {
  LOW: '#22d4b0',
  MEDIUM: '#fbbf24',
  HIGH: '#fb923c',
  CRITICAL: '#f87171',
}
