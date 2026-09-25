import { useQuery } from '@tanstack/react-query'
import { getTelemetry } from '../api/trucks'
import { MOCK_TELEMETRY } from '../mocks/data'

export function useTelemetry(id: string) {
  const to = new Date().toISOString()
  const from = new Date(Date.now() - 6 * 60 * 60 * 1000).toISOString()

  return useQuery({
    queryKey: ['telemetry', id],
    queryFn: async () => {
      try {
        return await getTelemetry(id, from, to)
      } catch {
        return MOCK_TELEMETRY
      }
    },
    refetchInterval: 30_000,
    initialData: MOCK_TELEMETRY,
    enabled: !!id,
  })
}
