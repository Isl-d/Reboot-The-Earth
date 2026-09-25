import 'leaflet/dist/leaflet.css'
import L from 'leaflet'
import { MapContainer, Marker, Popup, TileLayer, Tooltip, useMap } from 'react-leaflet'
import { useEffect } from 'react'
import type { TruckSummary } from '../../types'
import { HYPERMARKETS, MAP_CENTER, MAP_ZOOM, RISK_COLORS, SUPERMARKETS, WAREHOUSES } from './mapConfig'

delete (L.Icon.Default.prototype as unknown as Record<string, unknown>)._getIconUrl
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png',
  iconUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png',
  shadowUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png',
})

/* ── Truck icon (side-view box truck SVG) ──────────────────── */
function createTruckIcon(riskLevel: string, isActive: boolean) {
  const color = RISK_COLORS[riskLevel] ?? '#8fa8c8'
  const dark = '#0c1825'

  const pulse = isActive
    ? `<circle cx="20" cy="12" r="18" fill="${color}" opacity="0">
         <animate attributeName="r" values="14;22;14" dur="2s" repeatCount="indefinite"/>
         <animate attributeName="opacity" values="0.4;0;0.4" dur="2s" repeatCount="indefinite"/>
       </circle>`
    : ''

  // Side-view box truck: cargo box + cab + wheels
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="36" height="24" viewBox="0 0 48 32">
    ${pulse}
    <rect x="2" y="5" width="26" height="16" rx="1" fill="${color}" stroke="${dark}" stroke-width="1.5"/>
    <rect x="28" y="9" width="14" height="12" rx="1" fill="${color}" stroke="${dark}" stroke-width="1.5"/>
    <rect x="30" y="10.5" width="8" height="6" rx="0.5" fill="${dark}" opacity="0.55"/>
    <rect x="2" y="20" width="40" height="3" rx="1" fill="${color}" stroke="${dark}" stroke-width="1"/>
    <circle cx="10" cy="25" r="5" fill="${dark}" stroke="${color}" stroke-width="2"/>
    <circle cx="10" cy="25" r="2" fill="${color}"/>
    <circle cx="36" cy="25" r="5" fill="${dark}" stroke="${color}" stroke-width="2"/>
    <circle cx="36" cy="25" r="2" fill="${color}"/>
    <circle cx="42" cy="5" r="3.5" fill="${color}" stroke="${dark}" stroke-width="1.5"/>
  </svg>`

  return L.divIcon({
    html: svg,
    className: '',
    iconSize: [36, 24],
    iconAnchor: [18, 22],
    popupAnchor: [0, -22],
  })
}

/* ── Location icons ────────────────────────────────────────── */
function createWarehouseIcon() {
  const c = '#8fa8c8'
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="34" height="34" viewBox="0 0 34 34">
    <polygon points="17,3 32,14 32,31 2,31 2,14" fill="${c}" opacity="0.9" stroke="#0c1825" stroke-width="1.5"/>
    <rect x="13" y="20" width="8" height="11" fill="#0c1825" opacity="0.6"/>
    <text x="17" y="17" text-anchor="middle" font-size="9" font-weight="600" fill="#0c1825" font-family="sans-serif">WH</text>
    <!-- Snowflake -->
    <line x1="17" y1="22" x2="17" y2="30" stroke="${c}" stroke-width="1" opacity="0.8"/>
    <line x1="13" y1="26" x2="21" y2="26" stroke="${c}" stroke-width="1" opacity="0.8"/>
  </svg>`
  return L.divIcon({ html: svg, className: '', iconSize: [34, 34], iconAnchor: [17, 34], popupAnchor: [0, -34] })
}

function createHypermarketIcon() {
  const c = '#22d4b0'
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="30" height="30" viewBox="0 0 30 30">
    <circle cx="15" cy="15" r="13" fill="${c}" opacity="0.9" stroke="#0c1825" stroke-width="1.5"/>
    <!-- Cart body -->
    <rect x="9" y="11" width="12" height="8" rx="1" fill="#0c1825" opacity="0.7"/>
    <line x1="7" y1="11" x2="9" y2="11" stroke="#0c1825" stroke-width="1.5"/>
    <!-- Wheels -->
    <circle cx="11" cy="21" r="1.5" fill="#0c1825" opacity="0.7"/>
    <circle cx="18" cy="21" r="1.5" fill="#0c1825" opacity="0.7"/>
    <text x="15" y="11" text-anchor="middle" font-size="6" font-weight="700" fill="#0c1825" font-family="sans-serif">H</text>
  </svg>`
  return L.divIcon({ html: svg, className: '', iconSize: [30, 30], iconAnchor: [15, 30], popupAnchor: [0, -30] })
}

function createSupermarketIcon() {
  const c = '#fbbf24'
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="26" height="26" viewBox="0 0 26 26">
    <circle cx="13" cy="13" r="11" fill="${c}" opacity="0.9" stroke="#0c1825" stroke-width="1.5"/>
    <!-- Bag -->
    <rect x="8" y="11" width="10" height="9" rx="1" fill="#0c1825" opacity="0.7"/>
    <path d="M10 11 Q10 8 13 8 Q16 8 16 11" fill="none" stroke="#0c1825" stroke-width="1.5"/>
    <text x="13" y="11" text-anchor="middle" font-size="5.5" font-weight="700" fill="#0c1825" font-family="sans-serif">S</text>
  </svg>`
  return L.divIcon({ html: svg, className: '', iconSize: [26, 26], iconAnchor: [13, 26], popupAnchor: [0, -26] })
}

function createLabelIcon(text: string, color: string) {
  return L.divIcon({
    html: `<div style="color:${color};font-size:9px;font-weight:600;letter-spacing:0.04em;white-space:nowrap;text-shadow:0 1px 3px rgba(0,0,0,0.9),0 0 8px rgba(0,0,0,0.7);pointer-events:none;">${text}</div>`,
    className: '',
    iconSize: [80, 12],
    iconAnchor: [40, 0],
  })
}

/* ── MapUpdater: fit bounds once on first load ─────────────── */
function MapUpdater({ trucks }: { trucks: TruckSummary[] }) {
  const map = useMap()
  useEffect(() => {
    if (trucks.length > 0) {
      const bounds = L.latLngBounds(trucks.map((t) => [t.latitude, t.longitude]))
      map.fitBounds(bounds, { padding: [80, 80], maxZoom: 13 })
    }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps
  return null
}

/* ── Popup content helpers ─────────────────────────────────── */
function LocationPopup({ name, type, color }: { name: string; type: string; color: string }) {
  return (
    <div style={{ minWidth: 130 }}>
      <div style={{ fontWeight: 600, fontSize: 12, marginBottom: 2 }}>{name}</div>
      <div style={{ fontSize: 10, letterSpacing: '0.06em', color, fontWeight: 500 }}>{type}</div>
    </div>
  )
}

interface Props {
  trucks: TruckSummary[]
  onTruckClick: (id: string) => void
}

export function LiveMap({ trucks, onTruckClick }: Props) {
  return (
    <MapContainer center={MAP_CENTER} zoom={MAP_ZOOM} className="h-full w-full" zoomControl={false}>
      <TileLayer
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        attribution='&copy; <a href="https://openstreetmap.org">OpenStreetMap</a>'
        maxZoom={19}
        keepBuffer={4}
        updateWhenZooming={false}
      />
      <MapUpdater trucks={trucks} />

      {/* ── Warehouses ──────────────────────────────────────── */}
      {WAREHOUSES.map((wh) => (
        <Marker key={wh.id} position={[wh.lat, wh.lon]} icon={createWarehouseIcon()}>
          <Tooltip direction="top" offset={[0, -34]} opacity={0.95}>
            <LocationPopup name={wh.name} type="COLD STORAGE" color="#8fa8c8" />
          </Tooltip>
          <Popup><LocationPopup name={wh.name} type="COLD STORAGE WAREHOUSE" color="#8fa8c8" /></Popup>
        </Marker>
      ))}
      {WAREHOUSES.map((wh) => (
        <Marker key={`${wh.id}-label`} position={[wh.lat - 0.003, wh.lon]} icon={createLabelIcon(wh.id, '#8fa8c8')} interactive={false} />
      ))}

      {/* ── Hypermarkets ────────────────────────────────────── */}
      {HYPERMARKETS.map((h) => (
        <Marker key={h.id} position={[h.lat, h.lon]} icon={createHypermarketIcon()}>
          <Tooltip direction="top" offset={[0, -30]} opacity={0.95}>
            <LocationPopup name={h.name} type="HYPERMARKET" color="#22d4b0" />
          </Tooltip>
          <Popup><LocationPopup name={h.name} type="HYPERMARKET" color="#22d4b0" /></Popup>
        </Marker>
      ))}
      {HYPERMARKETS.map((h) => (
        <Marker key={`${h.id}-label`} position={[h.lat - 0.0025, h.lon]} icon={createLabelIcon(h.name.split(' ')[0], '#22d4b0')} interactive={false} />
      ))}

      {/* ── Supermarkets ────────────────────────────────────── */}
      {SUPERMARKETS.map((s) => (
        <Marker key={s.id} position={[s.lat, s.lon]} icon={createSupermarketIcon()}>
          <Tooltip direction="top" offset={[0, -26]} opacity={0.95}>
            <LocationPopup name={s.name} type="SUPERMARKET" color="#fbbf24" />
          </Tooltip>
          <Popup><LocationPopup name={s.name} type="SUPERMARKET" color="#fbbf24" /></Popup>
        </Marker>
      ))}
      {SUPERMARKETS.map((s) => (
        <Marker key={`${s.id}-label`} position={[s.lat - 0.002, s.lon]} icon={createLabelIcon(s.name.split(' ')[0], '#fbbf24')} interactive={false} />
      ))}

      {/* ── Trucks ──────────────────────────────────────────── */}
      {trucks.map((truck) => (
        <Marker
          key={truck.id}
          position={[truck.latitude, truck.longitude]}
          icon={createTruckIcon(truck.riskLevel, truck.activeIncident)}
          eventHandlers={{ click: () => onTruckClick(truck.id) }}
        >
          <Popup>
            <div style={{ minWidth: 140 }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 4 }}>
                <span style={{ fontWeight: 700, fontSize: 13 }}>{truck.id}</span>
                <span style={{ fontSize: 10, letterSpacing: '0.06em', fontWeight: 600, color: RISK_COLORS[truck.riskLevel] }}>
                  {truck.riskLevel}
                </span>
              </div>
              <div style={{ fontFamily: 'monospace', fontSize: 12, marginBottom: 2 }}>
                {truck.temperatureC.toFixed(1)}°C · {truck.humidityPct}% RH
              </div>
              <div style={{ fontFamily: 'monospace', fontSize: 11, opacity: 0.7 }}>
                {truck.speedKmh} km/h · Score {truck.riskScore}
              </div>
              <button
                onClick={() => onTruckClick(truck.id)}
                style={{ marginTop: 8, fontSize: 11, color: '#00c8e0', letterSpacing: '0.04em', background: 'none', border: 'none', cursor: 'pointer', padding: 0 }}
              >
                VIEW DETAILS →
              </button>
            </div>
          </Popup>
        </Marker>
      ))}
    </MapContainer>
  )
}
