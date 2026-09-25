import { useEffect, useRef, useState } from 'react'
import type { Incident } from '../../types'

function timeAgo(ts: string) {
  const m = Math.floor((Date.now() - new Date(ts).getTime()) / 60000)
  if (m < 1) return 'just now'
  if (m < 60) return `${m}m ago`
  return `${Math.floor(m / 60)}h ago`
}

const severityColor: Record<string, string> = {
  CRITICAL: 'text-risk-critical',
  HIGH: 'text-risk-high',
  MEDIUM: 'text-risk-medium',
  LOW: 'text-risk-low',
}

interface Props {
  incidents: Incident[]
}

export function NotificationBell({ incidents }: Props) {
  const open = incidents.filter((i) => i.status === 'OPEN')
  const hasCritical = open.some((i) => i.severity === 'CRITICAL')
  const [showPanel, setShowPanel] = useState(false)
  const [ringing, setRinging] = useState(false)
  const prevCount = useRef(open.length)
  const panelRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (open.length > prevCount.current) {
      setRinging(true)
      setTimeout(() => setRinging(false), 700)
    }
    prevCount.current = open.length
  }, [open.length])

  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (panelRef.current && !panelRef.current.contains(e.target as Node)) {
        setShowPanel(false)
      }
    }
    document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [])

  return (
    <div className="relative" ref={panelRef}>
      <button
        onClick={() => setShowPanel((v) => !v)}
        className="relative flex items-center justify-center w-8 h-8 rounded-sm hover:bg-elevated transition-colors"
        title="Notifications"
      >
        <svg
          viewBox="0 0 20 20"
          fill="currentColor"
          className={`w-5 h-5 text-text-secondary ${ringing ? '[animation:ring_0.6s_ease-in-out]' : ''}`}
        >
          <path d="M10 2a6 6 0 00-6 6v3.586l-.707.707A1 1 0 004 14h12a1 1 0 00.707-1.707L16 11.586V8a6 6 0 00-6-6zM10 18a3 3 0 01-2.83-2h5.66A3 3 0 0110 18z" />
        </svg>

        {open.length > 0 && (
          <span
            className={`absolute -top-0.5 -right-0.5 min-w-[16px] h-4 flex items-center justify-center rounded-full text-[9px] font-bold px-0.5 text-[#0c1825] ${
              hasCritical ? 'bg-risk-critical animate-pulse' : 'bg-risk-medium'
            }`}
          >
            {open.length}
          </span>
        )}
      </button>

      {showPanel && (
        <div className="absolute right-0 top-10 w-80 bg-elevated border border-border rounded-md shadow-2xl z-50 [animation:slide-in-up_0.2s_ease-out_both] overflow-hidden">
          <div className="px-3 py-2 border-b border-border flex items-center justify-between">
            <span className="text-[11px] tracking-[0.06em] uppercase font-medium text-text-secondary">
              Active Incidents
            </span>
            <span className={`text-[11px] font-mono ${hasCritical ? 'text-risk-critical animate-pulse' : 'text-text-secondary'}`}>
              {open.length} OPEN
            </span>
          </div>

          {open.length === 0 ? (
            <div className="p-4 text-center text-[12px] text-text-secondary">
              No active incidents
            </div>
          ) : (
            <div className="max-h-72 overflow-auto">
              {open.map((inc) => (
                <div
                  key={inc.id}
                  className="px-3 py-2.5 border-b border-border/50 last:border-0 hover:bg-surface transition-colors"
                >
                  <div className="flex items-center justify-between gap-2 mb-0.5">
                    <div className="flex items-center gap-1.5">
                      <span className={`text-[10px] font-medium tracking-[0.06em] uppercase ${severityColor[inc.severity]}`}>
                        {inc.severity}
                      </span>
                      <span className="text-[11px] font-mono text-text-primary font-medium">
                        {inc.truckId}
                      </span>
                    </div>
                    <span className="text-[10px] font-mono text-text-secondary">
                      {timeAgo(inc.createdAt)}
                    </span>
                  </div>
                  <p className="text-[11px] text-text-secondary leading-snug line-clamp-2">
                    {inc.message}
                  </p>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
