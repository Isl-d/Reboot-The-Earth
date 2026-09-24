// Shared colours, so the map, the list and the charts always agree.
export const RISK_COLOUR: Record<string, string> = {
  green: '#2fbf71',
  amber: '#f0a92b',
  red: '#e2564b',
  unknown: '#93a4bd',
}

export const PLACE_COLOUR: Record<string, string> = {
  port: '#7aa2f7',
  border: '#9d7cd8',
  warehouse: '#4fa8ff',
  cold_store: '#3ec9d6',
  store: '#e8eef7',
  food_bank: '#f7a8c4',
}

export function heatColour(risk: number): string {
  // 0 = comfortable, 100 = a Gulf afternoon.
  const t = Math.max(0, Math.min(100, risk)) / 100
  const r = Math.round(60 + t * 195)
  const g = Math.round(120 - t * 60)
  const b = Math.round(200 - t * 150)
  return `rgb(${r},${g},${b})`
}

export function fmt(n: number | null | undefined, digits = 1): string {
  if (n === null || n === undefined || Number.isNaN(n)) return '--'
  return n.toFixed(digits)
}
