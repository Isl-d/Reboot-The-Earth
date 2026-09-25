// Heat-aware dispatch: the cheapest cold chain is the one that never gets hot.
import { useEffect, useState } from 'react'
import { api } from '../api'
import type { Strings } from '../i18n'
import type { DispatchRow } from '../types'

export function DispatchCard({ s }: { s: Strings }) {
  const [rows, setRows] = useState<DispatchRow[]>([])
  useEffect(() => { api.dispatch().then((d) => setRows(d.suggestions)).catch(() => undefined) }, [])
  if (!rows.length) return null
  const best = rows[0]
  return (
    <div className="panel dispatch">
      <h2>{s.dispatch}</h2>
      <div className="dispatch-line">
        <strong>{s.leaveAt} {best.best_departure}</strong> {s.insteadOf} {best.worst_departure} &mdash;{' '}
        {s.saves} {best.freshness_saved_hours_loading} {s.hours}
      </div>
      <table className="mini">
        <tbody>
          {rows.map((r) => (
            <tr key={r.route_id}>
              <td>{r.route_id}</td>
              <td className="muted">{r.route}</td>
              <td className="ok">{r.best_departure} &middot; {r.mean_temp_best_c}&deg;</td>
              <td className="bad">{r.worst_departure} &middot; {r.mean_temp_worst_c}&deg;</td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className="muted tiny">{best.source}</div>
    </div>
  )
}
