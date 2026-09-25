import { CartesianGrid, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import type { TelemetryPoint } from '../../types'

function fmt(ts: string) {
  return new Date(ts).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

interface Props {
  data: TelemetryPoint[]
  safeMinTempC?: number
  safeMaxTempC?: number
  fill?: boolean
}

export function TemperatureChart({ data, safeMinTempC = 0, safeMaxTempC = 4, fill }: Props) {
  const chartData = data.map((p) => ({ time: fmt(p.timestamp), temp: p.temperatureC }))
  return (
    <ResponsiveContainer width="100%" height={fill ? '100%' : 180}>
      <LineChart data={chartData} margin={{ top: 8, right: 16, left: -12, bottom: 0 }}>
        <CartesianGrid strokeDasharray="2 4" stroke="var(--color-border)" vertical={false} />
        <XAxis dataKey="time" tick={{ fill: 'var(--color-text-secondary)', fontSize: 9, fontFamily: 'IBM Plex Mono' }} tickLine={false} axisLine={{ stroke: 'var(--color-border)' }} interval="preserveStartEnd" />
        <YAxis tick={{ fill: 'var(--color-text-secondary)', fontSize: 9, fontFamily: 'IBM Plex Mono' }} tickLine={false} axisLine={false} unit="°C" width={36} />
        <Tooltip contentStyle={{ background: 'var(--color-elevated)', border: '1px solid var(--color-border)', borderRadius: 4, fontSize: 11, fontFamily: 'IBM Plex Mono', color: 'var(--color-text-primary)' }} formatter={(v) => [`${Number(v).toFixed(1)}°C`, 'Temp']} labelStyle={{ color: 'var(--color-text-secondary)' }} />
        <ReferenceLine y={safeMaxTempC} stroke="var(--color-risk-critical)" strokeDasharray="4 3" strokeWidth={1.5} label={{ value: `MAX ${safeMaxTempC}°C`, fill: 'var(--color-risk-critical)', fontSize: 9 }} />
        <ReferenceLine y={safeMinTempC} stroke="var(--color-risk-low)" strokeDasharray="4 3" strokeWidth={1.5} label={{ value: `MIN ${safeMinTempC}°C`, fill: 'var(--color-risk-low)', fontSize: 9 }} />
        <Line type="monotone" dataKey="temp" stroke="var(--color-primary)" strokeWidth={2.5} dot={false} activeDot={{ r: 5, fill: 'var(--color-primary)', stroke: 'var(--color-base)', strokeWidth: 2 }} isAnimationActive animationDuration={1400} animationEasing="ease-out" />
      </LineChart>
    </ResponsiveContainer>
  )
}
