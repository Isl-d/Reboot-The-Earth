import { useEffect, useMemo, useState } from 'react'
import { STRINGS, type Lang } from './i18n'
import { useLive } from './useLive'
import { FleetMap } from './components/Map'
import { FleetList } from './components/FleetList'
import { TruckPanel } from './components/TruckPanel'
import { AlertCard } from './components/AlertCard'
import { EventLog } from './components/EventLog'
import { DemoPanel } from './components/DemoPanel'
import { ComparisonScreen } from './components/ComparisonScreen'
import { DispatchCard } from './components/DispatchCard'

export default function App() {
  const live = useLive()
  const [lang, setLang] = useState<Lang>('en')
  const [selected, setSelected] = useState<string | null>(null)
  const [showHeat, setShowHeat] = useState(true)
  const [approvals, setApprovals] = useState(0)
  const s = STRINGS[lang]

  useEffect(() => {
    document.documentElement.dir = lang === 'ar' ? 'rtl' : 'ltr'
    document.documentElement.lang = lang
  }, [lang])

  // Follow the real sensor until someone clicks another truck.
  useEffect(() => {
    if (!selected && live.trucks.length) setSelected(live.realTruck)
  }, [live.trucks.length, live.realTruck, selected])

  const truck = selected ? live.byId[selected] : undefined
  const open = useMemo(
    () => live.decisions.filter((d) => !d.approved_at),
    [live.decisions],
  )
  const latest = open[0] ?? live.decisions[0]

  return (
    <div className="app">
      <header>
        <div className="brand">
          <h1>{s.title}</h1>
          <span className="muted">{s.tagline}</span>
        </div>
        <div className="totals">
          {live.totals && (
            <>
              <Stat k={s.monitored} v={`${live.totals.kg_monitored.toLocaleString()} kg`} />
              <Stat k={s.atRisk} v={`${live.totals.kg_at_risk.toLocaleString()} kg`} tone={live.totals.kg_at_risk ? 'bad' : undefined} />
              <Stat k={s.saved} v={`${live.totals.kg_saved.toLocaleString()} kg`} tone={live.totals.kg_saved ? 'ok' : undefined} />
              <Stat k={s.co2} v={`${live.totals.co2e_saved_kg.toLocaleString()} kg`} />
            </>
          )}
        </div>
        <div className="controls">
          <span className={`pill ${live.connected ? 'ok' : 'bad'}`}>
            {live.connected ? s.connected : s.offline}
          </span>
          <span className="pill">{s.demoClock} &times;{Math.round(live.demoSpeed)}</span>
          <label className="switch small">
            <input type="checkbox" checked={showHeat} onChange={(e) => setShowHeat(e.target.checked)} />
            <span>heat</span>
          </label>
          <button className="ghost" onClick={() => setLang(lang === 'en' ? 'ar' : 'en')}>
            {lang === 'en' ? 'العربية' : 'English'}
          </button>
        </div>
      </header>

      <main>
        <section className="left">
          <FleetMap trucks={live.trucks} selected={selected} onSelect={setSelected} showHeat={showHeat} />
          <FleetList trucks={live.trucks} selected={selected} onSelect={setSelected} s={s} />
        </section>

        <section className="right">
          {truck && (
            <TruckPanel truck={truck} s={s} demoSpeed={live.demoSpeed} mapSpeed={live.mapSpeed} />
          )}
          {latest && (
            <AlertCard
              decision={latest}
              s={s}
              lang={lang}
              onApproved={() => { live.refresh(); setApprovals((n) => n + 1) }}
            />
          )}
          <ComparisonScreen s={s} refreshKey={approvals} />
          <EventLog events={live.events} s={s} onSelect={setSelected} />
          <DispatchCard s={s} />
        </section>
      </main>

      <DemoPanel trucks={live.trucks} realTruck={live.realTruck} s={s} onReset={live.refresh} />
    </div>
  )
}

function Stat({ k, v, tone }: { k: string; v: string; tone?: 'ok' | 'bad' }) {
  return (
    <div className="stat">
      <div className={`stat-v ${tone ?? ''}`}>{v}</div>
      <div className="stat-k">{k}</div>
    </div>
  )
}
