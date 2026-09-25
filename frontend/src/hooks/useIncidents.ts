import { useQuery } from '@tanstack/react-query'
import { getIncidents } from '../api/incidents'
import { MOCK_INCIDENTS } from '../mocks/data'

export function useIncidents() {
  return useQuery({
    queryKey: ['incidents'],
    queryFn: async () => {
      try {
        return await getIncidents()
      } catch {
        return MOCK_INCIDENTS
      }
    },
    refetchInterval: 15_000,
    initialData: MOCK_INCIDENTS,
  })
}
