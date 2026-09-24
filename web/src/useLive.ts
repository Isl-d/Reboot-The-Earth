// One WebSocket, one copy of the fleet. Everything on screen reads from here.
import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from './api'
import type { Decision, Totals, Truck, TruckEvent, WsMessage } from './types'

export interface Live {
  trucks: Truck[]
  byId: Record<string, Truck>
  events: TruckEvent[]
  decisions: Decision[]
  totals: Totals | null
  demoSpeed: number
  mapSpeed: number
  realTruck: string
  connected: boolean
  refresh: () => void
}

export function useLive(): Live {
  const [trucks, setTrucks] = useState<Record<string, Truck>>({})
  const [events, setEvents] = useState<TruckEvent[]>([])
  const [decisions, setDecisions] = useState<Decision[]>([])
  const [totals, setTotals] = useState<Totals | null>(null)
  const [demoSpeed, setDemoSpeed] = useState(120)
  const [mapSpeed, setMapSpeed] = useState(10)
  const [realTruck, setRealTruck] = useState('TRK-07')
  const [connected, setConnected] = useState(false)
  const socket = useRef<WebSocket | null>(null)

  const refresh = useCallback(() => {
    api.fleet().then((f) => {
      setTrucks(Object.fromEntries(f.trucks.map((t) => [t.truck_id, t])))
      setTotals(f.totals)
      setDemoSpeed(f.demo_speed)
      setMapSpeed(f.map_speed)
      setRealTruck(f.real_truck)
    }).catch(() => undefined)
    api.events().then((e) => setEvents(e.events)).catch(() => undefined)
    api.decisions().then((d) => setDecisions(d.decisions)).catch(() => undefined)
  }, [])

  useEffect(() => {
    refresh()
    let closed = false
    let retry: number | undefined

    const connect = () => {
      if (closed) return
      const ws = new WebSocket(api.wsUrl())
      socket.current = ws
      ws.onopen = () => setConnected(true)
      ws.onclose = () => {
        setConnected(false)
        // The broker or the backend may restart mid-demo. Come back quietly.
        retry = window.setTimeout(connect, 1500)
      }
      ws.onerror = () => ws.close()
      ws.onmessage = (raw) => {
        const msg: WsMessage = JSON.parse(raw.data)
        switch (msg.type) {
          case 'hello':
            setDemoSpeed(msg.payload.demo_speed)
            setMapSpeed(msg.payload.map_speed)
            setRealTruck(msg.payload.real_truck)
            setTrucks(Object.fromEntries(msg.payload.trucks.map((t: Truck) => [t.truck_id, t])))
            break
          case 'reading':
            setTrucks((prev) => ({ ...prev, [msg.payload.truck_id]: msg.payload }))
            break
          case 'event':
            setEvents((prev) => [msg.payload, ...prev].slice(0, 200))
            break
          case 'decision':
            setDecisions((prev) => {
              const rest = prev.filter((d) => d.decision_id !== msg.payload.decision_id)
              return [msg.payload, ...rest]
            })
            break
          case 'reset':
            setEvents([])
            setDecisions([])
            refresh()
            break
        }
      }
    }

    connect()
    // Totals are cheap and not pushed, so poll them slowly as a backstop.
    const tick = window.setInterval(() => {
      api.fleet().then((f) => setTotals(f.totals)).catch(() => undefined)
    }, 4000)

    return () => {
      closed = true
      window.clearTimeout(retry)
      window.clearInterval(tick)
      socket.current?.close()
    }
  }, [refresh])

  const list = Object.values(trucks).sort((a, b) => a.truck_id.localeCompare(b.truck_id))
  return { trucks: list, byId: trucks, events, decisions, totals, demoSpeed, mapSpeed, realTruck, connected, refresh }
}
