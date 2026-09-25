import { useQueryClient } from '@tanstack/react-query'
import { useCallback, useEffect, useRef, useState } from 'react'
import type { TruckSummary, WsEvent } from '../types'

export function useWebSocket() {
  const queryClient = useQueryClient()
  const [connected, setConnected] = useState(false)
  const [lastEventTime, setLastEventTime] = useState<string | null>(null)
  const wsRef = useRef<WebSocket | null>(null)
  const retriesRef = useRef(0)
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return

    const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:'
    const ws = new WebSocket(`${protocol}//${location.host}/ws/live`)
    wsRef.current = ws

    ws.onopen = () => {
      setConnected(true)
      retriesRef.current = 0
    }

    ws.onclose = () => {
      setConnected(false)
      const delay = Math.min(1000 * 2 ** retriesRef.current, 30_000)
      retriesRef.current += 1
      if (retriesRef.current <= 5) {
        timeoutRef.current = setTimeout(connect, delay)
      }
    }

    ws.onerror = () => ws.close()

    ws.onmessage = (e) => {
      try {
        const event: WsEvent = JSON.parse(e.data)
        setLastEventTime(event.timestamp)

        if (event.event === 'TRUCK_STATE_UPDATED' && event.truckId) {
          queryClient.setQueryData<TruckSummary[]>(['trucks'], (prev) => {
            if (!prev) return prev
            return prev.map((t) =>
              t.id === event.truckId
                ? {
                    ...t,
                    temperatureC: event.temperatureC ?? t.temperatureC,
                    humidityPct: event.humidityPct ?? t.humidityPct,
                    latitude: event.latitude ?? t.latitude,
                    longitude: event.longitude ?? t.longitude,
                    riskScore: event.riskScore ?? t.riskScore,
                    riskLevel: event.riskLevel ?? t.riskLevel,
                    speedKmh: event.speedKmh ?? t.speedKmh,
                  }
                : t,
            )
          })
          queryClient.invalidateQueries({ queryKey: ['truck', event.truckId] })
        }

        if (event.event === 'INCIDENT_CREATED' || event.event === 'INCIDENT_UPDATED') {
          queryClient.invalidateQueries({ queryKey: ['incidents'] })
        }

        if (event.event === 'FOOD_LOSS_UPDATED') {
          queryClient.invalidateQueries({ queryKey: ['stats'] })
        }
      } catch {
        // ignore malformed messages
      }
    }
  }, [queryClient])

  useEffect(() => {
    connect()
    return () => {
      if (timeoutRef.current) clearTimeout(timeoutRef.current)
      wsRef.current?.close()
    }
  }, [connect])

  return { connected, lastEventTime }
}
