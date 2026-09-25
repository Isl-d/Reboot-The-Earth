import { useQuery } from '@tanstack/react-query'
import { getTrucks } from '../api/trucks'
import { MOCK_TRUCKS } from '../mocks/data'

export function useTrucks() {
  return useQuery({
    queryKey: ['trucks'],
    queryFn: async () => {
      try {
        return await getTrucks()
      } catch {
        return MOCK_TRUCKS
      }
    },
    refetchInterval: 10_000,
    initialData: MOCK_TRUCKS,
  })
}
