import { useNavigate } from 'react-router-dom'
import { ConnectionStatus } from '../components/common/ConnectionStatus'
import { NotificationBell } from '../components/common/NotificationBell'
import { StatCard } from '../components/common/StatCard'
import { IncidentPanel } from '../components/incident/IncidentPanel'
import { LiveMap } from '../components/map/LiveMap'
import { SimulationControls } from '../components/simulation/SimulationControls'
import { useIncidents } from '../hooks/useIncidents'
import { useTheme } from '../hooks/useTheme'
import { useTrucks } from '../hooks/useTrucks'
import { useWebSocket } from '../hooks/useWebSocket'
import { MOCK_STATS } from '../mocks/data'

export function CommandCenter() {
  const navigate = useNavigate()
  const { data: trucks = [] } = useTrucks()
  const { data: incidents = [] } = useIncidents()
  const { connected, lastEventTime } = useWebSocket()
  const { theme, toggleTheme } = useTheme()

  const atRisk = trucks.filter((t) => t.riskLevel === 'HIGH' || t.riskLevel === 'CRITICAL').length
  const openIncidents = incidents.filter((i) => i.status === 'OPEN')

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden' }}>

      {/* ── Topbar ──────────────────────────────────────── */}
      <header style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '0 16px', height: 44, background: 'var(--color-base)',
        borderBottom: '1px solid var(--color-border)', flexShrink: 0,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <span style={{ fontSize: 11, fontWeight: 600, letterSpacing: '0.14em', textTransform: 'uppercase', color: 'var(--color-text-primary)' }}>
            Cold Chain Command Center
          </span>
          <span style={{ color: 'var(--color-border)' }}>|</span>
          <span style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--color-text-secondary)' }}>
            {new Date().toLocaleString()}
          </span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <ConnectionStatus connected={connected} lastEventTime={lastEventTime} />
          <button
            onClick={toggleTheme}
            title={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}
            style={{ width: 32, height: 32, display: 'flex', alignItems: 'center', justifyContent: 'center', borderRadius: 2, background: 'transparent', border: 'none', cursor: 'pointer', color: 'var(--color-text-secondary)' }}
          >
            {theme === 'dark' ? '☀' : '🌙'}
          </button>
          <NotificationBell incidents={incidents} />
        </div>
      </header>

      {/* ── Stats row ───────────────────────────────────── */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr 1fr', gap: 8, padding: '8px 16px', flexShrink: 0 }}>
        <StatCard label="Active Trucks" value={trucks.length || MOCK_STATS.activeTrucks} />
        <StatCard label="At Risk" value={atRisk || MOCK_STATS.trucksAtRisk} highlight={atRisk > 0} />
        <StatCard label="Food Saved" value={MOCK_STATS.foodSavedKg} unit="kg" />
        <StatCard label="Loss Prevented" value={`QAR ${MOCK_STATS.lossPrevented.toLocaleString()}`} />
      </div>

      {/* ── Main grid: fills ALL remaining height ────────── */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'minmax(0, 62fr) minmax(0, 38fr)',
        gap: 8,
        padding: '0 16px 8px',
        flex: 1,
        minHeight: 0,
      }}>

        {/* Live Map */}
        <div style={{
          display: 'flex', flexDirection: 'column',
          background: 'var(--color-surface)', border: '1px solid var(--color-border)',
          borderRadius: 4, overflow: 'hidden',
        }}>
          <div style={{
            padding: '6px 12px', borderBottom: '1px solid var(--color-border)',
            display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexShrink: 0,
          }}>
            <span style={{ fontSize: 11, letterSpacing: '0.06em', textTransform: 'uppercase', fontWeight: 500, color: 'var(--color-text-secondary)' }}>
              Live Map
            </span>
            <span style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--color-text-secondary)' }}>
              {trucks.length} trucks · {openIncidents.length} incidents
            </span>
          </div>
          <div style={{ flex: 1, minHeight: 0 }}>
            <LiveMap trucks={trucks} onTruckClick={(id) => navigate(`/trucks/${id}`)} />
          </div>
        </div>

        {/* Right column: incidents + sensor + simulation */}
        <div style={{ display: 'grid', gridTemplateRows: 'minmax(0,1fr) minmax(0,1fr) auto', gap: 8, minHeight: 0 }}>

          {/* Active Incidents */}
          <div style={{
            display: 'flex', flexDirection: 'column', minHeight: 0,
            background: 'var(--color-surface)', border: '1px solid var(--color-border)', borderRadius: 4, overflow: 'hidden',
          }}>
            <div style={{
              padding: '6px 12px', borderBottom: '1px solid var(--color-border)',
              display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexShrink: 0,
            }}>
              <span style={{ fontSize: 11, letterSpacing: '0.06em', textTransform: 'uppercase', fontWeight: 500, color: 'var(--color-text-secondary)' }}>
                Active Incidents
              </span>
              {openIncidents.length > 0 && (
                <span style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--color-risk-critical)', animation: 'pulse 2s infinite' }}>
                  {openIncidents.length} OPEN
                </span>
              )}
            </div>
            <div style={{ flex: 1, overflowY: 'auto', padding: 8 }}>
              <IncidentPanel incidents={incidents} />
            </div>
          </div>

          {/* Sensor Monitoring */}
          <div style={{
            display: 'flex', flexDirection: 'column', minHeight: 0,
            background: 'var(--color-surface)', border: '1px solid var(--color-border)', borderRadius: 4, overflow: 'hidden',
          }}>
            <div style={{ padding: '6px 12px', borderBottom: '1px solid var(--color-border)', flexShrink: 0 }}>
              <span style={{ fontSize: 11, letterSpacing: '0.06em', textTransform: 'uppercase', fontWeight: 500, color: 'var(--color-text-secondary)' }}>
                Sensor Monitoring
              </span>
            </div>
            <div style={{ flex: 1, overflowY: 'auto', padding: '4px 8px' }}>
              {trucks.map((truck) => {
                const tempPct = Math.min(100, Math.max(0, (truck.temperatureC / 12) * 100))
                const riskCol =
                  truck.riskLevel === 'CRITICAL' ? 'var(--color-risk-critical)' :
                  truck.riskLevel === 'HIGH'     ? 'var(--color-risk-high)' :
                  truck.riskLevel === 'MEDIUM'   ? 'var(--color-risk-medium)' : 'var(--color-risk-low)'
                return (
                  <div
                    key={truck.id}
                    onClick={() => navigate(`/trucks/${truck.id}`)}
                    style={{
                      display: 'grid', gridTemplateColumns: '52px 1fr 58px 64px',
                      alignItems: 'center', gap: 8, cursor: 'pointer',
                      padding: '6px 4px', borderRadius: 2,
                    }}
                    onMouseEnter={(e) => (e.currentTarget.style.background = 'var(--color-elevated)')}
                    onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
                  >
                    <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11, fontWeight: 600, color: 'var(--color-text-primary)' }}>
                      {truck.id}
                    </span>
                    <div style={{ height: 6, background: 'var(--color-elevated)', borderRadius: 3, overflow: 'hidden' }}>
                      <div style={{ height: '100%', width: `${tempPct}%`, background: riskCol, borderRadius: 3, transition: 'width 0.7s ease' }} />
                    </div>
                    <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11, textAlign: 'right', color: 'var(--color-text-primary)' }}>
                      {truck.temperatureC.toFixed(1)}°C
                    </span>
                    <span style={{ fontSize: 10, textAlign: 'right', fontWeight: 600, letterSpacing: '0.06em', color: riskCol }}>
                      {truck.riskLevel}
                    </span>
                  </div>
                )
              })}
            </div>
          </div>

          {/* Simulation Controls */}
          <SimulationControls trucks={trucks} />
        </div>
      </div>
    </div>
  )
}
