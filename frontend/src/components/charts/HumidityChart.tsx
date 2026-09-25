import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import type { TelemetryPoint } from '../../types'

function fmt(ts: string) {
  return new Date(ts).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

export function HumidityChart({ data, fill }: { data: TelemetryPoint[]; fill?: boolean }) {
  const chartData = data.map((p) => ({ time: fmt(p.timestamp), humidity: p.humidityPct }))
  return (
    <ResponsiveContainer width="100%" height={fill ? '100%' : 180}>
      <LineChart data={chartData} margin={{ top: 8, right: 16, left: -12, bottom: 0 }}>
        <CartesianGrid strokeDasharray="2 4" stroke="var(--color-border)" vertical={false} />
        <XAxis dataKey="time" tick={{ fill: 'var(--color-text-secondary)', fontSize: 9, fontFamily: 'IBM Plex Mono' }} tickLine={false} axisLine={{ stroke: 'var(--color-border)' }} interval="preserveStartEnd" />
        <YAxis tick={{ fill: 'var(--color-text-secondary)', fontSize: 9, fontFamily: 'IBM Plex Mono' }} tickLine={false} axisLine={false} unit="%" domain={[40, 100]} width={32} />
        <Tooltip contentStyle={{ background: 'var(--color-elevated)', border: '1px solid var(--color-border)', borderRadius: 4, fontSize: 11, fontFamily: 'IBM Plex Mono', color: 'var(--color-text-primary)' }} formatter={(v) => [`${Number(v)}%`, 'Humidity']} labelStyle={{ color: 'var(--color-text-secondary)' }} />
        <Line type="monotone" dataKey="humidity" stroke="var(--color-text-secondary)" strokeWidth={2.5} dot={false} activeDot={{ r: 5, fill: 'var(--color-text-secondary)', stroke: 'var(--color-base)', strokeWidth: 2 }} isAnimationActive animationDuration={1400} animationEasing="ease-out" />
      </LineChart>
    </ResponsiveContainer>
  )
}
