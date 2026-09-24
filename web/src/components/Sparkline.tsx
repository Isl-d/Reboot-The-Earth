// Two lines: what the sensor reads, and what the cargo is actually at. The gap
// between them is the whole point - 2 t of lettuce lags a 2-second air reading.
import type { HistoryPoint } from '../types'

interface Props {
  points: HistoryPoint[]
  limit: number
  ideal: number
  height?: number
}

export function Sparkline({ points, limit, ideal, height = 110 }: Props) {
  if (points.length < 2) return <div className="spark-empty">waiting for readings</div>
  const W = 320
  const values = points.flatMap((p) => [p.air_c, p.product_c]).filter((v): v is number => typeof v === 'number')
  const lo = Math.min(...values, ideal) - 1.5
  const hi = Math.max(...values, limit) + 1.5
  const x = (i: number) => (i / (points.length - 1)) * W
  const y = (v: number) => height - 8 - ((v - lo) / Math.max(hi - lo, 0.1)) * (height - 18)

  const line = (key: 'air_c' | 'product_c') =>
    points
      .map((p, i) => {
        const v = p[key]
        return `${i ? 'L' : 'M'}${x(i).toFixed(1)},${y(typeof v === 'number' ? v : lo).toFixed(1)}`
      })
      .join('')

  return (
    <svg className="spark" viewBox={`0 0 ${W} ${height}`} preserveAspectRatio="none">
      <line x1={0} x2={W} y1={y(limit)} y2={y(limit)} className="spark-limit" />
      <line x1={0} x2={W} y1={y(ideal)} y2={y(ideal)} className="spark-ideal" />
      <path d={line('air_c')} className="spark-air" />
      <path d={line('product_c')} className="spark-product" />
    </svg>
  )
}
