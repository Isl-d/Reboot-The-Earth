// Twelve trucks, worst first. TRK-07 is marked as the one with a real sensor.
import { RISK_COLOUR, fmt } from '../theme'
import type { Strings } from '../i18n'
import type { Truck } from '../types'

interface Props {
  trucks: Truck[]
  selected: string | null
  onSelect: (id: string) => void
  s: Strings
}

const ORDER: Record<string, number> = { red: 0, amber: 1, unknown: 2, green: 3 }

export function FleetList({ trucks, selected, onSelect, s }: Props) {
  const sorted = [...trucks].sort(
    (a, b) => (ORDER[a.risk] ?? 9) - (ORDER[b.risk] ?? 9) || a.life_on_arrival_h - b.life_on_arrival_h,
  )
  return (
    <div className="panel fleet">
      <h2>{s.fleet}</h2>
      <ul className="fleet-list">
        {sorted.map((t) => (
          <li
            key={t.truck_id}
            className={`fleet-row ${t.truck_id === selected ? 'is-selected' : ''}`}
            onClick={() => onSelect(t.truck_id)}
          >
            <span className="dot" style={{ background: RISK_COLOUR[t.risk] }} />
            <div className="fleet-main">
              <div className="fleet-top">
                <strong>{t.truck_id}</strong>
                {t.live_sensor && <span className="tag live">{s.liveSensor}</span>}
                {t.status !== 'rolling' && <span className="tag">{t.status}</span>}
              </div>
              <div className="fleet-sub">
                {t.product} &middot; {Math.round(t.qty_kg)} kg &middot; {t.destination_name}
              </div>
              <div className="bar">
                <span style={{ width: `${t.freshness_pct}%`, background: RISK_COLOUR[t.risk] }} />
              </div>
            </div>
            <div className="fleet-num">
              <div className="temp">{fmt(t.air_c)}&deg;</div>
              <div className="days">{fmt(t.life_on_arrival_days, 1)}d</div>
            </div>
          </li>
        ))}
      </ul>
    </div>
  )
}
