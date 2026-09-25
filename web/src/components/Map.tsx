// The fleet on a map of Qatar: routes from OSRM, places from OpenStreetMap,
// trucks coloured by risk, and a heat-risk layer from the Open-Meteo forecast.
//
// The basemap is off by default because the demo runs with no internet. Set
// VITE_MAP_TILES to a raster tile URL to turn it on when there is a connection.
import { useEffect, useRef, useState } from 'react'
import maplibregl, { Map as MlMap } from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'
import { api } from '../api'
import { PLACE_COLOUR, RISK_COLOUR, heatColour } from '../theme'
import type { HeatRow, Place, Truck } from '../types'

const TILES = import.meta.env.VITE_MAP_TILES as string | undefined
const DOHA: [number, number] = [51.42, 25.27]

interface Props {
  trucks: Truck[]
  selected: string | null
  onSelect: (id: string) => void
  showHeat: boolean
}

function emptyFc(): GeoJSON.FeatureCollection {
  return { type: 'FeatureCollection', features: [] }
}

export function FleetMap({ trucks, selected, onSelect, showHeat }: Props) {
  const box = useRef<HTMLDivElement>(null)
  const map = useRef<MlMap | null>(null)
  const [ready, setReady] = useState(false)
  const [heat, setHeat] = useState<Record<string, number>>({})

  // --- create the map once ------------------------------------------------
  useEffect(() => {
    if (!box.current || map.current) return
    const sources: any = {}
    const layers: any[] = [
      { id: 'bg', type: 'background', paint: { 'background-color': '#0b1220' } },
    ]
    if (TILES) {
      sources.osm = { type: 'raster', tiles: [TILES], tileSize: 256,
        attribution: '(c) OpenStreetMap contributors' }
      layers.push({ id: 'osm', type: 'raster', source: 'osm', paint: { 'raster-opacity': 0.55 } })
    }

    const m = new maplibregl.Map({
      container: box.current,
      // No `glyphs`: the offline style has no text layers, and MapLibre
      // rejects the style outright if the key is present but empty.
      style: { version: 8, sources, layers } as any,
      center: DOHA,
      zoom: 8.4,
      attributionControl: false,
    })
    m.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'top-right')
    map.current = m

    m.on('load', async () => {
      const [routes, places] = await Promise.all([api.routes(), api.places()])

      m.addSource('routes', { type: 'geojson', data: routes })

      // Frame the whole road network rather than guessing a zoom level.
      const bounds = new maplibregl.LngLatBounds()
      for (const f of routes.features) {
        const g = f.geometry as GeoJSON.LineString
        for (const c of g.coordinates) bounds.extend(c as [number, number])
      }
      if (!bounds.isEmpty()) m.fitBounds(bounds, { padding: 48, duration: 0 })
      m.addLayer({
        id: 'routes-line', type: 'line', source: 'routes',
        paint: {
          'line-color': ['case', ['boolean', ['feature-state', 'hot'], false], '#e2564b', '#2a3c58'],
          'line-width': 3,
        },
        layout: { 'line-cap': 'round', 'line-join': 'round' },
      })

      m.addSource('reroute', { type: 'geojson', data: emptyFc() })
      m.addLayer({
        id: 'reroute-line', type: 'line', source: 'reroute',
        paint: { 'line-color': '#2fbf71', 'line-width': 3.5, 'line-dasharray': [2, 1.5] },
      })

      m.addSource('places', {
        type: 'geojson',
        data: {
          type: 'FeatureCollection',
          features: (places.places as Place[]).map((p) => ({
            type: 'Feature',
            properties: { ...p, colour: PLACE_COLOUR[p.type] ?? '#93a4bd' },
            geometry: { type: 'Point', coordinates: [p.lon, p.lat] },
          })),
        } as GeoJSON.FeatureCollection,
      })
      m.addLayer({
        id: 'places-dot', type: 'circle', source: 'places',
        paint: {
          'circle-radius': ['case', ['get', 'has_cold_room'], 6, 4],
          'circle-color': ['get', 'colour'],
          'circle-opacity': 0.9,
          'circle-stroke-width': 1,
          'circle-stroke-color': '#0b1220',
        },
      })

      m.addSource('trucks', { type: 'geojson', data: emptyFc() })
      m.addLayer({
        id: 'trucks-halo', type: 'circle', source: 'trucks',
        filter: ['get', 'live'],
        paint: { 'circle-radius': 16, 'circle-color': '#4fa8ff', 'circle-opacity': 0.18 },
      })
      m.addLayer({
        id: 'trucks-dot', type: 'circle', source: 'trucks',
        paint: {
          'circle-radius': ['case', ['boolean', ['get', 'selected'], false], 11, 8],
          'circle-color': ['get', 'colour'],
          'circle-stroke-width': ['case', ['get', 'live'], 3, 1.5],
          'circle-stroke-color': ['case', ['get', 'live'], '#4fa8ff', '#0b1220'],
        },
      })

      m.on('click', 'trucks-dot', (e) => {
        const id = e.features?.[0]?.properties?.truck_id
        if (id) onSelect(String(id))
      })
      m.on('mouseenter', 'trucks-dot', () => { m.getCanvas().style.cursor = 'pointer' })
      m.on('mouseleave', 'trucks-dot', () => { m.getCanvas().style.cursor = '' })

      // Places and trucks carry their own labels only when the style has
      // glyphs; offline we rely on the fleet list beside the map instead.
      setReady(true)
    })

    return () => { m.remove(); map.current = null }
  }, [onSelect])

  // --- heat layer ---------------------------------------------------------
  useEffect(() => {
    api.heat().then((h) => {
      const now: Record<string, number> = {}
      for (const row of h.current as HeatRow[]) now[row.route_id] = Number(row.heat_risk_0_100)
      setHeat(now)
    }).catch(() => undefined)
  }, [])

  useEffect(() => {
    const m = map.current
    if (!m || !ready || !m.getLayer('routes-line')) return
    m.setPaintProperty('routes-line', 'line-color',
      showHeat
        ? ['match', ['get', 'route_id'],
            ...Object.entries(heat).flatMap(([id, risk]) => [id, heatColour(risk)]),
            '#2a3c58']
        : '#2a3c58')
    m.setPaintProperty('routes-line', 'line-width', showHeat ? 5 : 3)
  }, [showHeat, heat, ready])

  // --- trucks move on every reading ---------------------------------------
  useEffect(() => {
    const m = map.current
    if (!m || !ready) return
    const src = m.getSource('trucks') as maplibregl.GeoJSONSource | undefined
    if (!src) return
    src.setData({
      type: 'FeatureCollection',
      features: trucks.map((t) => ({
        type: 'Feature',
        properties: {
          truck_id: t.truck_id,
          colour: RISK_COLOUR[t.risk] ?? RISK_COLOUR.unknown,
          live: t.live_sensor,
          selected: t.truck_id === selected,
        },
        geometry: { type: 'Point', coordinates: [t.lon, t.lat] },
      })),
    } as GeoJSON.FeatureCollection)

    const reroutes = trucks.filter((t) => t.reroute_geometry)
    ;(m.getSource('reroute') as maplibregl.GeoJSONSource | undefined)?.setData({
      type: 'FeatureCollection',
      features: reroutes.map((t) => ({
        type: 'Feature',
        properties: { truck_id: t.truck_id },
        geometry: { type: 'LineString', coordinates: t.reroute_geometry! },
      })),
    } as GeoJSON.FeatureCollection)
  }, [trucks, selected, ready])

  return (
    <div className="map-wrap">
      <div ref={box} className="map" />
      {!TILES && (
        <div className="map-note">
          Offline map: roads from OSRM, places from OpenStreetMap, drawn without tiles.
        </div>
      )}
    </div>
  )
}
