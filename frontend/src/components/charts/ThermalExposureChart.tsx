import { Area, AreaChart, CartesianGrid, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import type { TelemetryPoint } from '../../types'

function fmt(ts: string) {
  return new Date(ts).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

export function ThermalExposureChart({ data, safeMaxTempC = 4, fill }: { data: TelemetryPoint[]; safeMaxTempC?: number; fill?: boolean }) {
  let cumulative = 0
  const chartData = data.map((p) => {
    cumulative += Math.max(0, p.temperatureC - safeMaxTempC) / 12
    return { time: fmt(p.timestamp), exposure: parseFloat(cumulative.toFixed(2)) }
  })
  return (
    <ResponsiveContainer width="100%" height={fill ? '100%' : 180}>
      <AreaChart data={chartData} margin={{ top: 8, right: 16, left: -12, bottom: 0 }}>
        <defs>
          <linearGradient id="expGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor="var(--color-risk-high)" stopOpacity={0.5} />
            <stop offset="95%" stopColor="var(--color-risk-high)" stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="2 4" stroke="var(--color-border)" vertical={false} />
        <XAxis dataKey="time" tick={{ fill: 'var(--color-text-secondary)', fontSize: 9, fontFamily: 'IBM Plex Mono' }} tickLine={false} axisLine={{ stroke: 'var(--color-border)' }} interval="preserveStartEnd" />
        <YAxis tick={{ fill: 'var(--color-text-secondary)', fontSize: 9, fontFamily: 'IBM Plex Mono' }} tickLine={false} axisLine={false} width={32} />
        <Tooltip contentStyle={{ background: 'var(--color-elevated)', border: '1px solid var(--color-border)', borderRadius: 4, fontSize: 11, fontFamily: 'IBM Plex Mono', color: 'var(--color-text-primary)' }} formatter={(v) => [Number(v).toFixed(2), 'Exposure']} labelStyle={{ color: 'var(--color-text-secondary)' }} />
        <ReferenceLine y={35} stroke="var(--color-risk-critical)" strokeDasharray="4 3" strokeWidth={1.5} label={{ value: 'THRESHOLD', fill: 'var(--color-risk-critical)', fontSize: 8, position: 'right' }} />
        <Area type="monotone" dataKey="exposure" stroke="var(--color-risk-high)" strokeWidth={2.5} fill="url(#expGrad)" dot={false} isAnimationActive animationDuration={1600} animationEasing="ease-out" />
      </AreaChart>
    </ResponsiveContainer>
  )
}
