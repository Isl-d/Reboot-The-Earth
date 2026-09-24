// The slide at the end: the same shipment, with and without ColdGuard.
import { useEffect, useState } from 'react'
import { api } from '../api'
import type { Strings } from '../i18n'

interface Props { s: Strings; refreshKey: number }

export function ComparisonScreen({ s, refreshKey }: Props) {
  const [data, setData] = useState<any>(null)
  useEffect(() => { api.impact().then(setData).catch(() => undefined) }, [refreshKey])
  if (!data || data.totals.approved === 0) return null

  const without = data.without_coldguard
  const withCg = data.with_coldguard
  return (
    <div className="panel compare">
      <h2>{s.comparison}</h2>
      <div className="compare-grid">
        <div className="compare-col bad-col">
          <div className="compare-title">{s.without}</div>
          <div className="compare-big">{without.kg_rejected.toLocaleString()} kg</div>
          <div className="muted">{without.outcome}</div>
          <div className="compare-sub">-{without.value_lost_qar.toLocaleString()} QAR</div>
        </div>
        <div className="compare-col ok-col">
          <div className="compare-title">{s.with}</div>
          <div className="compare-big">{withCg.kg_accepted.toLocaleString()} kg</div>
          <div className="muted">{withCg.outcome}</div>
          <div className="compare-sub">
            +{withCg.value_kept_qar.toLocaleString()} QAR &middot;
            {' '}{withCg.co2e_saved_kg.toLocaleString()} kg {s.co2}
          </div>
        </div>
      </div>
      <div className={`audit ${data.totals.audit_ok ? 'ok' : 'bad'}`}>
        {data.totals.audit_ok ? s.auditOk : s.auditBroken} &middot;{' '}
        {data.totals.decisions} {data.totals.decisions === 1 ? 'decision' : 'decisions'}
      </div>
    </div>
  )
}
