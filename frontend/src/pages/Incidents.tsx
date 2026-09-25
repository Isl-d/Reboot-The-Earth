import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useIncidents } from '../hooks/useIncidents'
import type { IncidentStatus } from '../types'

const SEVERITY_ORDER: Record<string, number> = { CRITICAL: 0, HIGH: 1, MEDIUM: 2, LOW: 3 }

const SEVERITY_COLORS: Record<string, { border: string; text: string; bg: string }> = {
  CRITICAL: { border: 'var(--color-risk-critical)', text: 'var(--color-risk-critical)', bg: 'rgba(248,113,113,0.06)' },
  HIGH:     { border: 'var(--color-risk-high)',     text: 'var(--color-risk-high)',     bg: 'rgba(251,146,60,0.06)' },
  MEDIUM:   { border: 'var(--color-risk-medium)',   text: 'var(--color-risk-medium)',   bg: '' },
  LOW:      { border: 'var(--color-risk-low)',      text: 'var(--color-risk-low)',      bg: '' },
}

const TYPE_LABELS: Record<string, string> = {
  TEMPERATURE_EXCURSION: 'Temperature Excursion',
  REFRIGERATION_FAILURE: 'Refrigeration Failure',
  DOOR_LEFT_OPEN: 'Door Left Open',
  TRAFFIC_DELAY: 'Traffic Delay',
  COMBINED_FAILURE: 'Combined Failure',
}

function timeAgo(ts: string) {
  const m = Math.floor((Date.now() - new Date(ts).getTime()) / 60000)
  if (m < 1) return 'just now'
  if (m < 60) return `${m}m ago`
  return `${Math.floor(m / 60)}h ${m % 60}m ago`
}

export function Incidents() {
  const navigate = useNavigate()
  const { data: incidents = [] } = useIncidents()
  const [tab, setTab] = useState<IncidentStatus>('OPEN')

  const filtered = incidents
    .filter((i) => i.status === tab)
    .sort((a, b) => SEVERITY_ORDER[a.severity] - SEVERITY_ORDER[b.severity])

  const openCount = incidents.filter((i) => i.status === 'OPEN').length
  const resolvedCount = incidents.filter((i) => i.status === 'RESOLVED').length

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden' }}>
      {/* Header */}
      <header style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '0 20px', height: 44, flexShrink: 0,
        background: 'var(--color-base)', borderBottom: '1px solid var(--color-border)',
      }}>
        <span style={{ fontSize: 11, fontWeight: 600, letterSpacing: '0.12em', textTransform: 'uppercase', color: 'var(--color-text-secondary)' }}>
          Incidents
        </span>
        <div style={{ display: 'flex', gap: 4 }}>
          {(['OPEN', 'RESOLVED'] as const).map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              style={{
                padding: '4px 12px', borderRadius: 2, fontSize: 11,
                letterSpacing: '0.04em', fontWeight: 500, cursor: 'pointer',
                border: 'none', transition: 'all 0.15s',
                background: tab === t
                  ? t === 'OPEN' ? 'rgba(248,113,113,0.15)' : 'rgba(34,212,176,0.15)'
                  : 'var(--color-elevated)',
                color: tab === t
                  ? t === 'OPEN' ? 'var(--color-risk-critical)' : 'var(--color-risk-low)'
                  : 'var(--color-text-secondary)',
              }}
            >
              {t} {t === 'OPEN' && openCount > 0 ? `(${openCount})` : t === 'RESOLVED' && resolvedCount > 0 ? `(${resolvedCount})` : ''}
            </button>
          ))}
        </div>
      </header>

      {/* Content */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '12px 20px' }}>
        {filtered.length === 0 ? (
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: 200, gap: 8, color: 'var(--color-text-secondary)' }}>
            <span style={{ fontSize: 32, opacity: 0.2 }}>◎</span>
            <span style={{ fontSize: 12, letterSpacing: '0.06em', textTransform: 'uppercase' }}>No {tab.toLowerCase()} incidents</span>
          </div>
        ) : (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(420px, 1fr))', gap: 10 }}>
            {filtered.map((inc, i) => {
              const sc = SEVERITY_COLORS[inc.severity] ?? SEVERITY_COLORS.LOW
              return (
                <div
                  key={inc.id}
                  style={{
                    background: sc.bg || 'var(--color-surface)',
                    border: `1px solid var(--color-border)`,
                    borderLeft: `3px solid ${sc.border}`,
                    borderRadius: 4,
                    padding: '14px 16px',
                    animation: `slide-in-up 0.3s ease-out ${i * 60}ms both`,
                    boxShadow: inc.severity === 'CRITICAL' ? '0 0 16px 2px rgba(248,113,113,0.12)' : 'none',
                  }}
                >
                  {/* Top row */}
                  <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 8 }}>
                    <div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
                        <span style={{ fontSize: 10, fontWeight: 700, letterSpacing: '0.08em', textTransform: 'uppercase', color: sc.text }}>
                          {inc.severity}
                        </span>
                        <span style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--color-text-secondary)' }}>
                          {inc.id}
                        </span>
                        {tab === 'OPEN' && (
                          <span style={{ fontSize: 9, background: sc.border, color: '#0c1825', padding: '1px 5px', borderRadius: 2, fontWeight: 700, letterSpacing: '0.06em' }}>
                            OPEN
                          </span>
                        )}
                      </div>
                      <div style={{ fontSize: 15, fontWeight: 700, color: 'var(--color-text-primary)', marginBottom: 2 }}>
                        Truck {inc.truckId}
                      </div>
                      <div style={{ fontSize: 10, letterSpacing: '0.06em', textTransform: 'uppercase', color: 'var(--color-text-secondary)' }}>
                        {TYPE_LABELS[inc.type] ?? inc.type.replace(/_/g, ' ')}
                      </div>
                    </div>
                    <div style={{ textAlign: 'right', flexShrink: 0 }}>
                      <div style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--color-text-secondary)' }}>
                        {timeAgo(inc.createdAt)}
                      </div>
                      <div style={{ fontSize: 9, fontFamily: 'var(--font-mono)', color: 'var(--color-text-secondary)', opacity: 0.6, marginTop: 2 }}>
                        {new Date(inc.createdAt).toLocaleTimeString()}
                      </div>
                    </div>
                  </div>

                  {/* Message */}
                  <p style={{ fontSize: 12, color: 'var(--color-text-secondary)', lineHeight: 1.6, margin: '0 0 12px' }}>
                    {inc.message}
                  </p>

                  {/* Batch info */}
                  <div style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
                    <span style={{ fontSize: 10, fontFamily: 'var(--font-mono)', background: 'var(--color-elevated)', padding: '2px 8px', borderRadius: 2, color: 'var(--color-text-secondary)' }}>
                      Batch: {inc.batchId}
                    </span>
                  </div>

                  {/* Action */}
                  <button
                    onClick={() => navigate(`/trucks/${inc.truckId}`)}
                    style={{
                      fontSize: 10, fontWeight: 600, letterSpacing: '0.06em',
                      color: 'var(--color-primary)', background: 'none',
                      border: '1px solid var(--color-primary)', borderRadius: 2,
                      padding: '4px 12px', cursor: 'pointer',
                      transition: 'all 0.15s',
                    }}
                    onMouseEnter={(e) => { (e.target as HTMLButtonElement).style.background = 'var(--color-primary)'; (e.target as HTMLButtonElement).style.color = '#0c1825' }}
                    onMouseLeave={(e) => { (e.target as HTMLButtonElement).style.background = 'none'; (e.target as HTMLButtonElement).style.color = 'var(--color-primary)' }}
                  >
                    VIEW TRUCK →
                  </button>
                </div>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}
