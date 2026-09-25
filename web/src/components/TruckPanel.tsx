// One shipment in detail: live chart, freshness countdown and what the store
// will say when it arrives.
import { useEffect, useState } from 'react'
import { api } from '../api'
import { RISK_COLOUR, fmt } from '../theme'
import type { Strings } from '../i18n'
import type { HistoryPoint, Truck } from '../types'
import { Sparkline } from './Sparkline'

interface Props {
  truck: Truck
  s: Strings
  demoSpeed: number
  mapSpeed: number
}

export function TruckPanel({ truck, s, demoSpeed, mapSpeed }: Props) {
  const [points, setPoints] = useState<HistoryPoint[]>([])

  useEffect(() => {
    let alive = true
    const pull = () =>
      api.history(truck.truck_id)
        .then((h) => { if (alive) setPoints(h.points) })
        .catch(() => undefined)
    pull()
    const tick = window.setInterval(pull, 2000)
    return () => { alive = false; window.clearInterval(tick) }
  }, [truck.truck_id])

  const accepted = truck.life_on_arrival_days >= truck.min_life_on_arrival_days
  return (
    <div className="panel truck">
      <div className="truck-head">
        <div>
          <h2>
            {truck.truck_id}
            {truck.live_sensor && <span className="tag live">{s.liveSensor}</span>}
          </h2>
          <div className="muted">
            {truck.product} &middot; {Math.round(truck.qty_kg)} kg &middot; {truck.route_name}
          </div>
        </div>
        <div className="clocks">
          <span className="tag">{s.demoClock} &times;{Math.round(demoSpeed)}</span>
          <span className="tag">{s.mapClock} &times;{Math.round(mapSpeed)}</span>
        </div>
      </div>

      <div className="readouts">
        <div className="readout">
          <div className="readout-v">{fmt(truck.air_c)}&deg;C</div>
          <div className="readout-k">{s.air}</div>
        </div>
        <div className="readout">
          <div className="readout-v">{fmt(truck.product_c)}&deg;C</div>
          <div className="readout-k">{s.cargo}</div>
        </div>
        <div className="readout">
          <div className="readout-v">&times;{fmt(truck.aging_speed)}</div>
          <div className="readout-k">{s.ageing}</div>
        </div>
        <div className="readout">
          <div className="readout-v" style={{ color: RISK_COLOUR[truck.risk] }}>
            {fmt(truck.life_on_arrival_days)}
          </div>
          <div className="readout-k">{s.onArrival}</div>
        </div>
      </div>

      <Sparkline points={points} limit={truck.alert_limit_c} ideal={truck.ideal_temp_c} />
      <div className="legend">
        <span><i className="k-air" />{s.air}</span>
        <span><i className="k-product" />{s.cargo}</span>
        <span><i className="k-limit" />{s.limit} {truck.alert_limit_c}&deg;C</span>
      </div>

      <div className="bar big">
        <span style={{ width: `${truck.freshness_pct}%`, background: RISK_COLOUR[truck.risk] }} />
      </div>
      <div className="truck-foot">
        <span>{fmt(truck.life_left_days)} {s.daysLeft}</span>
        <span>{s.storeNeeds} {truck.min_life_on_arrival_days}d</span>
        <span className={accepted ? 'ok' : 'bad'}>
          {accepted ? s.accepted : s.rejected}
        </span>
      </div>
      {!truck.sensor_ok && <div className="warn">{s.sensor}</div>}
    </div>
  )
}
