import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useTrucks } from '../hooks/useTrucks'
import type { RiskLevel } from '../types'

const RISK_ORDER: Record<RiskLevel, number> = { CRITICAL: 0, HIGH: 1, MEDIUM: 2, LOW: 3 }

const RISK_COL: Record<RiskLevel, string> = {
  LOW: 'var(--color-risk-low)',
  MEDIUM: 'var(--color-risk-medium)',
  HIGH: 'var(--color-risk-high)',
  CRITICAL: 'var(--color-risk-critical)',
}

const FILTERS: (RiskLevel | 'ALL')[] = ['ALL', 'CRITICAL', 'HIGH', 'MEDIUM', 'LOW']

export function Fleet() {
  const navigate = useNavigate()
  const { data: trucks = [] } = useTrucks()
  const [filter, setFilter] = useState<RiskLevel | 'ALL'>('ALL')

  const visible = trucks
    .filter((t) => filter === 'ALL' || t.riskLevel === filter)
    .sort((a, b) => RISK_ORDER[a.riskLevel] - RISK_ORDER[b.riskLevel])

  const cols = [
    { key: 'id',      label: 'TRUCK',    w: '80px' },
    { key: 'product', label: 'PRODUCT',  w: '1fr' },
    { key: 'temp',    label: 'TEMP',     w: '80px' },
    { key: 'hum',     label: 'HUMIDITY', w: '80px' },
    { key: 'speed',   label: 'SPEED',    w: '80px' },
    { key: 'door',    label: 'DOOR',     w: '70px' },
    { key: 'refrig',  label: 'REFRIG',   w: '70px' },
    { key: 'risk',    label: 'RISK',     w: '100px' },
    { key: 'inc',     label: 'INCIDENT', w: '80px' },
  ]
  const gridCols = cols.map(c => c.w).join(' ')

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden' }}>
      {/* Header */}
      <header style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '0 20px', height: 44, flexShrink: 0,
        background: 'var(--color-base)', borderBottom: '1px solid var(--color-border)',
      }}>
        <span style={{ fontSize: 11, fontWeight: 600, letterSpacing: '0.12em', textTransform: 'uppercase', color: 'var(--color-text-secondary)' }}>
          Fleet Overview · {visible.length} trucks
        </span>
        <div style={{ display: 'flex', gap: 4 }}>
          {FILTERS.map((lvl) => (
            <button
              key={lvl}
              onClick={() => setFilter(lvl)}
              style={{
                padding: '4px 10px', borderRadius: 2, fontSize: 11,
                letterSpacing: '0.04em', fontWeight: 500, cursor: 'pointer',
                border: 'none', transition: 'all 0.15s',
                background: filter === lvl ? 'var(--color-primary)' : 'var(--color-elevated)',
                color: filter === lvl ? '#0c1825' : lvl === 'ALL' ? 'var(--color-text-secondary)' : RISK_COL[lvl as RiskLevel] ?? 'var(--color-text-secondary)',
              }}
            >
              {lvl}
              {lvl !== 'ALL' && (
                <span style={{ marginLeft: 4, opacity: 0.7 }}>
                  ({trucks.filter(t => t.riskLevel === lvl).length})
                </span>
              )}
            </button>
          ))}
        </div>
      </header>

      {/* Table header */}
      <div style={{
        display: 'grid', gridTemplateColumns: gridCols,
        padding: '8px 20px', gap: 8, flexShrink: 0,
        borderBottom: '1px solid var(--color-border)',
        background: 'var(--color-base)',
      }}>
        {cols.map(c => (
          <span key={c.key} style={{ fontSize: 10, letterSpacing: '0.08em', textTransform: 'uppercase', color: 'var(--color-text-secondary)', fontWeight: 500 }}>
            {c.label}
          </span>
        ))}
      </div>

      {/* Table rows */}
      <div style={{ flex: 1, overflowY: 'auto' }}>
        {visible.map((truck, i) => (
          <div
            key={truck.id}
            onClick={() => navigate(`/trucks/${truck.id}`)}
            style={{
              display: 'grid', gridTemplateColumns: gridCols,
              padding: '0 20px', gap: 8, alignItems: 'center',
              height: 52, cursor: 'pointer',
              borderBottom: '1px solid color-mix(in srgb, var(--color-border) 50%, transparent)',
              transition: 'background 0.12s',
              animation: `slide-in-up 0.25s ease-out ${i * 40}ms both`,
            }}
            onMouseEnter={(e) => (e.currentTarget.style.background = 'var(--color-elevated)')}
            onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
          >
            {/* Truck ID */}
            <span style={{ fontFamily: 'var(--font-mono)', fontSize: 13, fontWeight: 700, color: 'var(--color-text-primary)' }}>
              {truck.id}
            </span>
            {/* Product / name */}
            <span style={{ fontSize: 12, color: 'var(--color-text-secondary)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {truck.name}
            </span>
            {/* Temp */}
            <span style={{ fontFamily: 'var(--font-mono)', fontSize: 13, color: RISK_COL[truck.riskLevel], fontWeight: 600 }}>
              {truck.temperatureC.toFixed(1)}°C
            </span>
            {/* Humidity */}
            <span style={{ fontFamily: 'var(--font-mono)', fontSize: 12, color: 'var(--color-text-secondary)' }}>
              {truck.humidityPct}%
            </span>
            {/* Speed */}
            <span style={{ fontFamily: 'var(--font-mono)', fontSize: 12, color: 'var(--color-text-secondary)' }}>
              {truck.speedKmh} km/h
            </span>
            {/* Door */}
            <span style={{ fontSize: 11, fontWeight: 600, color: truck.doorOpen ? 'var(--color-risk-critical)' : 'var(--color-risk-low)' }}>
              {truck.doorOpen ? 'OPEN' : 'CLOSED'}
            </span>
            {/* Refrig */}
            <span style={{ fontSize: 11, fontWeight: 600, color: truck.refrigerationOn ? 'var(--color-risk-low)' : 'var(--color-risk-critical)' }}>
              {truck.refrigerationOn ? 'ON' : 'OFF'}
            </span>
            {/* Risk badge */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <span style={{
                display: 'inline-flex', alignItems: 'center', gap: 4,
                padding: '2px 8px', borderRadius: 2,
                fontSize: 10, fontWeight: 600, letterSpacing: '0.06em',
                background: 'var(--color-elevated)',
                color: RISK_COL[truck.riskLevel],
              }}>
                <span style={{ width: 5, height: 5, borderRadius: '50%', background: RISK_COL[truck.riskLevel], flexShrink: 0 }} />
                {truck.riskLevel} {truck.riskScore}
              </span>
            </div>
            {/* Incident */}
            <span style={{ fontSize: 11, fontWeight: 700, color: 'var(--color-risk-critical)', ...(truck.activeIncident ? { animation: 'pulse 2s infinite' } : { color: 'var(--color-text-secondary)', opacity: 0.3 }) }}>
              {truck.activeIncident ? '● ACTIVE' : '—'}
            </span>
          </div>
        ))}

        {visible.length === 0 && (
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: 160, color: 'var(--color-text-secondary)', fontSize: 12, letterSpacing: '0.06em', textTransform: 'uppercase' }}>
            No trucks match filter
          </div>
        )}
      </div>
    </div>
  )
}
