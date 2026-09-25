import type { ScatterPointItem } from 'recharts/types/cartesian/Scatter'
import { ResponsiveContainer, Scatter, ScatterChart, Tooltip, XAxis, YAxis } from 'recharts'
import type { TelemetryPoint } from '../../types'

interface ChartPoint {
  lon: number
  lat: number
  idx: number
}

function TruckDot(props: ScatterPointItem & { idx?: number; payload?: ChartPoint; totalPoints?: number }) {
  const { cx = 0, cy = 0, payload, totalPoints = 1 } = props
  const idx = payload?.idx ?? 0
  const isLast = idx === totalPoints - 1
  return (
    <circle
      cx={cx}
      cy={cy}
      r={isLast ? 5 : 2.5}
      fill={isLast ? '#f87171' : '#00c8e0'}
      opacity={isLast ? 1 : 0.5 + (idx / totalPoints) * 0.5}
    />
  )
}

export function GpsTrajectoryChart({ data, fill }: { data: TelemetryPoint[]; fill?: boolean }) {
  const chartData: ChartPoint[] = data.map((p, i) => ({
    lon: parseFloat(p.longitude.toFixed(4)),
    lat: parseFloat(p.latitude.toFixed(4)),
    idx: i,
  }))

  return (
    <ResponsiveContainer width="100%" height={fill ? '100%' : 180}>
      <ScatterChart margin={{ top: 8, right: 12, left: -12, bottom: 0 }}>
        <XAxis
          dataKey="lon"
          type="number"
          name="Longitude"
          domain={['auto', 'auto']}
          tick={{ fill: '#8fa8c8', fontSize: 9, fontFamily: 'IBM Plex Mono' }}
          tickLine={false}
          axisLine={{ stroke: '#2d4160' }}
          tickFormatter={(v: number) => v.toFixed(3)}
          label={{ value: 'LON', fill: '#8fa8c8', fontSize: 9, position: 'insideBottomRight', offset: -4 }}
        />
        <YAxis
          dataKey="lat"
          type="number"
          name="Latitude"
          domain={['auto', 'auto']}
          tick={{ fill: '#8fa8c8', fontSize: 9, fontFamily: 'IBM Plex Mono' }}
          tickLine={false}
          axisLine={false}
          tickFormatter={(v: number) => v.toFixed(3)}
          width={48}
          label={{ value: 'LAT', fill: '#8fa8c8', fontSize: 9, angle: -90, position: 'insideLeft' }}
        />
        <Tooltip
          contentStyle={{
            background: '#1e3048',
            border: '1px solid #2d4160',
            borderRadius: '4px',
            fontSize: 11,
            fontFamily: 'IBM Plex Mono',
            color: '#c9d6e8',
          }}
          cursor={{ stroke: '#2d4160' }}
          formatter={(v) => [Number(v).toFixed(4), '']}
        />
        <Scatter
          data={chartData}
          fill="#00c8e0"
          opacity={0.7}
          shape={(props) => (
            <TruckDot
              {...(props as ScatterPointItem & { payload?: ChartPoint })}
              totalPoints={chartData.length}
            />
          )}
        />
      </ScatterChart>
    </ResponsiveContainer>
  )
}
