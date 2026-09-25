import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter, Route, Routes } from 'react-router-dom'
import { Sidebar } from './components/layout/Sidebar'
import { useTheme } from './hooks/useTheme'
import { CommandCenter } from './pages/CommandCenter'
import { Fleet } from './pages/Fleet'
import { Incidents } from './pages/Incidents'
import { TruckDetail } from './pages/TruckDetail'

const queryClient = new QueryClient({
  defaultOptions: { queries: { staleTime: 5_000, gcTime: 60_000 } },
})

function AppShell() {
  useTheme()
  return (
    <div style={{ display: 'flex', width: '100%', height: '100%', overflow: 'hidden', background: 'var(--color-base)', color: 'var(--color-text-primary)' }}>
      <Sidebar />
      <main style={{ flex: 1, minWidth: 0, height: '100%', overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
        <Routes>
          <Route path="/"          element={<CommandCenter />} />
          <Route path="/fleet"     element={<Fleet />} />
          <Route path="/trucks/:id" element={<TruckDetail />} />
          <Route path="/incidents" element={<Incidents />} />
        </Routes>
      </main>
    </div>
  )
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <AppShell />
      </BrowserRouter>
    </QueryClientProvider>
  )
}
