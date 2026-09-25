import { useQuery } from '@tanstack/react-query'
import { getTruck } from '../api/trucks'
import { MOCK_TRUCK_DETAIL } from '../mocks/data'

export function useTruckDetail(id: string) {
  return useQuery({
    queryKey: ['truck', id],
    queryFn: async () => {
      try {
        return await getTruck(id)
      } catch {
        return MOCK_TRUCK_DETAIL
      }
    },
    refetchInterval: 5_000,
    initialData: MOCK_TRUCK_DETAIL,
    enabled: !!id,
  })
}
