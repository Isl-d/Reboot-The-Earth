import { useState } from 'react'
import type { Incident } from '../../types'

const severityStyles: Record<string, { border: string; text: string; glow: string }> = {
  CRITICAL: { border: 'border-risk-critical', text: 'text-risk-critical', glow: '[animation:glow-critical_2s_ease-in-out_infinite]' },
  HIGH:     { border: 'border-risk-high',     text: 'text-risk-high',     glow: '' },
  MEDIUM:   { border: 'border-risk-medium',   text: 'text-risk-medium',   glow: '' },
  LOW:      { border: 'border-risk-low',      text: 'text-risk-low',      glow: '' },
}

function timeAgo(ts: string) {
  const m = Math.floor((Date.now() - new Date(ts).getTime()) / 60000)
  if (m < 1) return 'just now'
  if (m < 60) return `${m}m ago`
  return `${Math.floor(m / 60)}h ${m % 60}m ago`
}

interface Props { incident: Incident; reasoning?: string }

export function IncidentCard({ incident, reasoning }: Props) {
  const [expanded, setExpanded] = useState(false)
  const s = severityStyles[incident.severity] ?? severityStyles.LOW

  return (
    <div
      className={`border-l-2 ${s.border} bg-surface rounded-r-md p-2.5 space-y-1.5 [animation:slide-in-up_0.3s_ease-out_both] ${s.glow}`}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className={`text-[10px] font-semibold tracking-[0.08em] uppercase ${s.text}`}>
              {incident.severity}
            </span>
            <span className="text-[10px] text-text-secondary font-mono">{incident.id}</span>
          </div>
          <div className="text-[12px] font-semibold mt-0.5 text-text-primary">Truck {incident.truckId}</div>
          <div className="text-[10px] text-text-secondary tracking-[0.04em] uppercase mt-0.5">
            {incident.type.replace(/_/g, ' ')}
          </div>
        </div>
        <span className="text-[10px] font-mono text-text-secondary shrink-0">{timeAgo(incident.createdAt)}</span>
      </div>

      <p className="text-[11px] text-text-secondary leading-relaxed">{incident.message}</p>

      {reasoning && (
        <button
          onClick={() => setExpanded(!expanded)}
          className="text-[10px] text-primary tracking-[0.04em] hover:underline flex items-center gap-1 transition-colors"
        >
          {expanded ? '▾' : '▸'} VIEW REASONING
        </button>
      )}

      <div
        className="overflow-hidden transition-all duration-300 ease-in-out"
        style={{ maxHeight: expanded && reasoning ? 200 : 0 }}
      >
        {reasoning && (
          <div className="bg-elevated rounded-sm p-2.5 border border-border mt-1">
            <div className="text-[9px] tracking-[0.08em] uppercase text-text-secondary mb-1.5">AI REASONING</div>
            <p className="text-[11px] text-text-primary leading-relaxed">{reasoning}</p>
          </div>
        )}
      </div>
    </div>
  )
}
