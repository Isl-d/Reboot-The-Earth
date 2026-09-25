import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { RiskBadge } from '../components/common/RiskBadge'
import { GpsTrajectoryChart } from '../components/charts/GpsTrajectoryChart'
import { HumidityChart } from '../components/charts/HumidityChart'
import { ThermalExposureChart } from '../components/charts/ThermalExposureChart'
import { TemperatureChart } from '../components/charts/TemperatureChart'
import { useTelemetry } from '../hooks/useTelemetry'
import { useTruckDetail } from '../hooks/useTruckDetail'

const S = {
  panel: {
    background: 'var(--color-surface)',
    border: '1px solid var(--color-border)',
    borderRadius: 4,
    overflow: 'hidden',
    display: 'flex',
    flexDirection: 'column' as const,
  },
  panelHead: {
    padding: '6px 12px',
    borderBottom: '1px solid var(--color-border)',
    flexShrink: 0,
    fontSize: 10,
    letterSpacing: '0.08em',
    textTransform: 'uppercase' as const,
    fontWeight: 500,
    color: 'var(--color-text-secondary)',
  },
  row: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'baseline',
    padding: '5px 0',
    borderBottom: '1px solid color-mix(in srgb, var(--color-border) 40%, transparent)',
    fontSize: 11,
  },
  label: { letterSpacing: '0.06em', textTransform: 'uppercase' as const, color: 'var(--color-text-secondary)', fontSize: 10 },
  val:   { fontFamily: 'var(--font-mono)', color: 'var(--color-text-primary)', fontSize: 12 },
}

function Row({ label, value, danger }: { label: string; value: string; danger?: boolean }) {
  return (
    <div style={S.row}>
      <span style={S.label}>{label}</span>
      <span style={{ ...S.val, ...(danger ? { color: 'var(--color-risk-critical)', fontWeight: 600 } : {}) }}>{value}</span>
    </div>
  )
}

export function TruckDetail() {
  const { id = '' } = useParams<{ id: string }>()
  const { data } = useTruckDetail(id)
  const { data: telemetry = [] } = useTelemetry(id)
  const [showReasoning, setShowReasoning] = useState(false)

  if (!data) return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: 'var(--color-text-secondary)', fontSize: 12 }}>
      Loading…
    </div>
  )

  const { truck, batch, prediction, recommendation } = data
  const riskCol =
    prediction.riskLevel === 'CRITICAL' ? 'var(--color-risk-critical)' :
    prediction.riskLevel === 'HIGH'     ? 'var(--color-risk-high)' :
    prediction.riskLevel === 'MEDIUM'   ? 'var(--color-risk-medium)' : 'var(--color-risk-low)'

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden', width: '100%' }}>

      {/* Header */}
      <header style={{
        display: 'flex', alignItems: 'center', gap: 12,
        padding: '0 16px', height: 44, flexShrink: 0,
        background: 'var(--color-base)', borderBottom: '1px solid var(--color-border)',
      }}>
        <Link to="/fleet" style={{ fontSize: 11, color: 'var(--color-text-secondary)', textDecoration: 'none', letterSpacing: '0.04em' }}>← FLEET</Link>
        <span style={{ color: 'var(--color-border)' }}>|</span>
        <span style={{ fontFamily: 'var(--font-mono)', fontSize: 13, fontWeight: 700, color: 'var(--color-text-primary)' }}>{truck.id}</span>
        <RiskBadge level={prediction.riskLevel} score={prediction.riskScore} />
        {truck.doorOpen      && <span style={{ fontSize: 10, fontWeight: 700, color: 'var(--color-risk-critical)', letterSpacing: '0.04em' }}>● DOOR OPEN</span>}
        {!truck.refrigerationOn && <span style={{ fontSize: 10, fontWeight: 700, color: 'var(--color-risk-critical)', letterSpacing: '0.04em' }}>● REFRIG OFF</span>}
      </header>

      {/* Body — full-width grid, NO outer scroll */}
      <div style={{
        flex: 1, minHeight: 0, width: '100%',
        display: 'grid',
        gridTemplateColumns: '260px minmax(0,1fr)',
        gap: 8, padding: '8px 16px 8px 16px',
        overflow: 'hidden',
      }}>

        {/* ── Left column (scrollable internally) */}
        <div style={{ overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 8, paddingRight: 2 }}>

          {/* Product */}
          <div style={S.panel}>
            <div style={S.panelHead}>Product</div>
            <div style={{ padding: '10px 12px' }}>
              <div style={{ fontSize: 15, fontWeight: 700, color: 'var(--color-text-primary)', marginBottom: 4 }}>{batch.product}</div>
              <div style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--color-text-secondary)' }}>{batch.id} · {batch.quantityKg} kg</div>
            </div>
          </div>

          {/* Hero temp */}
          <div style={S.panel}>
            <div style={S.panelHead}>Live Temperature</div>
            <div style={{ padding: '10px 12px' }}>
              <div style={{ fontFamily: 'var(--font-mono)', fontSize: 42, fontWeight: 700, lineHeight: 1, color: riskCol, animation: 'count-up 0.6s ease-out both' }}>
                {truck.temperatureC.toFixed(1)}°C
              </div>
              <div style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--color-text-secondary)', marginTop: 6 }}>
                Safe: {batch.safeMinTempC}°C – {batch.safeMaxTempC}°C
              </div>
              {truck.temperatureC > batch.safeMaxTempC && (
                <div style={{ marginTop: 4, fontSize: 10, fontWeight: 700, color: 'var(--color-risk-critical)', letterSpacing: '0.04em' }}>
                  +{(truck.temperatureC - batch.safeMaxTempC).toFixed(1)}°C ABOVE SAFE MAX
                </div>
              )}
              {/* Thermometer bar */}
              <div style={{ marginTop: 8, height: 4, background: 'var(--color-elevated)', borderRadius: 2, overflow: 'hidden' }}>
                <div style={{
                  height: '100%', borderRadius: 2, transition: 'width 1s ease',
                  width: `${Math.min(100, (truck.temperatureC / 12) * 100)}%`,
                  background: riskCol,
                }} />
              </div>
            </div>
          </div>

          {/* Readings */}
          <div style={S.panel}>
            <div style={S.panelHead}>Sensor Readings</div>
            <div style={{ padding: '4px 12px 8px' }}>
              <Row label="Humidity"         value={`${truck.humidityPct}% RH`} />
              <Row label="Speed"            value={`${truck.speedKmh} km/h`} />
              <Row label="G-Force"          value={`${truck.gForce.toFixed(2)} g`} />
              <Row label="Door"             value={truck.doorOpen ? 'OPEN' : 'CLOSED'}    danger={truck.doorOpen} />
              <Row label="Refrigeration"    value={truck.refrigerationOn ? 'ON' : 'OFF'}  danger={!truck.refrigerationOn} />
              <Row label="Spoilage Prob."   value={`${(prediction.spoilageProbability * 100).toFixed(0)}%`} />
              <Row label="Remaining Safe"   value={`${prediction.remainingShelfLifeHours}h`} />
              <Row label="Thermal Exposure" value={prediction.thermalExposure.toFixed(1)} />
              {/* AI confidence bar */}
              <div style={{ marginTop: 8 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                  <span style={S.label}>AI Confidence</span>
                  <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--color-primary)' }}>{(prediction.confidence * 100).toFixed(0)}%</span>
                </div>
                <div style={{ height: 4, background: 'var(--color-elevated)', borderRadius: 2, overflow: 'hidden' }}>
                  <div style={{ height: '100%', width: `${prediction.confidence * 100}%`, background: 'var(--color-primary)', borderRadius: 2, transition: 'width 1.2s ease' }} />
                </div>
              </div>
            </div>
          </div>

          {/* Recommendation */}
          <div style={{
            ...S.panel,
            borderColor: prediction.riskLevel === 'CRITICAL' ? 'var(--color-risk-critical)' :
                          prediction.riskLevel === 'HIGH' ? 'var(--color-risk-high)' : 'var(--color-border)',
            animation: prediction.riskLevel === 'CRITICAL' ? 'glow-critical 2s ease-in-out infinite' : undefined,
          }}>
            <div style={S.panelHead}>Recommended Action</div>
            <div style={{ padding: '10px 12px' }}>
              <div style={{ fontSize: 22, fontWeight: 700, color: 'var(--color-text-primary)', marginBottom: 6 }}>{recommendation.action}</div>
              {recommendation.destinationId && (
                <div style={{ fontFamily: 'var(--font-mono)', fontSize: 12, color: 'var(--color-primary)', marginBottom: 8 }}>→ {recommendation.destinationId}</div>
              )}
              {recommendation.etaMinutes && (
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, marginBottom: 4 }}>
                  <span style={{ color: 'var(--color-text-secondary)' }}>ETA</span>
                  <span style={{ fontFamily: 'var(--font-mono)' }}>{recommendation.etaMinutes} min</span>
                </div>
              )}
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, marginBottom: 4 }}>
                <span style={{ color: 'var(--color-text-secondary)' }}>Food Saved</span>
                <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--color-risk-low)' }}>{recommendation.foodSavedKg} kg</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, marginBottom: 10 }}>
                <span style={{ color: 'var(--color-text-secondary)' }}>Expected Loss</span>
                <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--color-risk-medium)' }}>{recommendation.expectedLossPercent}%</span>
              </div>
              <button
                onClick={() => setShowReasoning(v => !v)}
                style={{ fontSize: 10, color: 'var(--color-primary)', background: 'none', border: 'none', cursor: 'pointer', letterSpacing: '0.04em', padding: 0, display: 'flex', alignItems: 'center', gap: 4 }}
              >
                {showReasoning ? '▾' : '▸'} VIEW REASONING
              </button>
              <div style={{ overflow: 'hidden', maxHeight: showReasoning ? 300 : 0, transition: 'max-height 0.35s ease' }}>
                <div style={{ marginTop: 8, background: 'var(--color-elevated)', borderRadius: 2, padding: '10px 12px', border: '1px solid var(--color-border)' }}>
                  <div style={{ fontSize: 9, letterSpacing: '0.08em', textTransform: 'uppercase', color: 'var(--color-text-secondary)', marginBottom: 6 }}>AI REASONING</div>
                  <p style={{ fontSize: 11, color: 'var(--color-text-primary)', lineHeight: 1.6, margin: 0 }}>{recommendation.reasoning}</p>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* ── Right column: charts fill all space ── */}
        <div style={{
          display: 'grid',
          gridTemplateRows: 'minmax(0,1fr) minmax(0,1fr) minmax(0,1fr)',
          gap: 8,
          minHeight: 0,
          width: '100%',
        }}>
          {/* Row 1: Temperature */}
          <div style={{ ...S.panel, animation: 'slide-in-up 0.35s ease-out both' }}>
            <div style={S.panelHead}>Temperature Over Time (°C)</div>
            <div style={{ flex: 1, minHeight: 0, padding: '4px 0' }}>
              <TemperatureChart data={telemetry} safeMinTempC={batch.safeMinTempC} safeMaxTempC={batch.safeMaxTempC} fill />
            </div>
          </div>

          {/* Row 2: Humidity */}
          <div style={{ ...S.panel, animation: 'slide-in-up 0.45s ease-out both' }}>
            <div style={S.panelHead}>Humidity Over Time (%)</div>
            <div style={{ flex: 1, minHeight: 0, padding: '4px 0' }}>
              <HumidityChart data={telemetry} fill />
            </div>
          </div>

          {/* Row 3: GPS + Thermal side by side */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, minHeight: 0 }}>
            <div style={{ ...S.panel, animation: 'slide-in-up 0.55s ease-out both' }}>
              <div style={S.panelHead}>GPS Trajectory</div>
              <div style={{ flex: 1, minHeight: 0, padding: '4px 0' }}>
                <GpsTrajectoryChart data={telemetry} fill />
              </div>
            </div>
            <div style={{ ...S.panel, animation: 'slide-in-up 0.65s ease-out both' }}>
              <div style={S.panelHead}>Thermal Exposure Index</div>
              <div style={{ flex: 1, minHeight: 0, padding: '4px 0' }}>
                <ThermalExposureChart data={telemetry} safeMaxTempC={batch.safeMaxTempC} fill />
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
