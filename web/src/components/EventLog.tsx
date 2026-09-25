// Every door opening, defrost, sensor fault and failure, newest first. A door
// opening appearing here and doing nothing else is the point of the demo.
import type { Strings } from '../i18n'
import type { TruckEvent } from '../types'

// Plain glyphs rather than emoji: they render the same on every laptop.
const ICON: Record<string, string> = {
  door: '◫', defrost: '❄', sensor_fault: '⚠', failure: '▲',
}

interface Props {
  events: TruckEvent[]
  s: Strings
  onSelect: (id: string) => void
}

export function EventLog({ events, s, onSelect }: Props) {
  const seen = new Set<string>()
  const latest = events.filter((e) => {
    const key = `${e.truck_id}-${e.seq}`
    if (seen.has(key)) return false
    seen.add(key)
    return true
  })
  return (
    <div className="panel log">
      <h2>{s.eventLog}</h2>
      {latest.length === 0 && <div className="muted">{s.noEvents}</div>}
      <ul>
        {latest.slice(0, 40).map((e) => (
          <li key={`${e.truck_id}-${e.seq}`} className={e.alert ? 'is-alert' : ''}
              onClick={() => onSelect(e.truck_id)}>
            <span className="ev-icon">{ICON[e.type] ?? '·'}</span>
            <span className="ev-truck">{e.truck_id}</span>
            <span className="ev-note">{e.note}</span>
            {e.peak_c !== null && <span className="ev-peak">{e.peak_c.toFixed(1)}&deg;</span>}
            {e.ended_at && <span className="ev-done">ended</span>}
          </li>
        ))}
      </ul>
    </div>
  )
}
