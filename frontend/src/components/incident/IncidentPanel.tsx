import type { Incident } from '../../types'
import { IncidentCard } from './IncidentCard'

const SEVERITY_ORDER = { CRITICAL: 0, HIGH: 1, MEDIUM: 2, LOW: 3 }

interface Props {
  incidents: Incident[]
}

export function IncidentPanel({ incidents }: Props) {
  const open = incidents
    .filter((i) => i.status === 'OPEN')
    .sort((a, b) => SEVERITY_ORDER[a.severity] - SEVERITY_ORDER[b.severity])

  if (open.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-32 text-text-secondary">
        <span className="text-2xl mb-2 opacity-30">◎</span>
        <span className="text-[12px] tracking-[0.06em] uppercase">No Active Incidents</span>
      </div>
    )
  }

  return (
    <div className="space-y-2">
      {open.map((inc) => (
        <IncidentCard key={inc.id} incident={inc} />
      ))}
    </div>
  )
}
