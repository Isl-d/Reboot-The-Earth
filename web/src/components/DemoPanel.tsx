// Hidden behind a key press: everything the presenter might need on stage, so
// nobody types a terminal command in front of judges. Press D to show it.
import { useEffect, useState } from 'react'
import { api } from '../api'
import type { Strings } from '../i18n'
import type { Truck } from '../types'

interface Props {
  trucks: Truck[]
  realTruck: string
  s: Strings
  onReset: () => void
}

export function DemoPanel({ trucks, realTruck, s, onReset }: Props) {
  const [open, setOpen] = useState(false)
  const [target, setTarget] = useState('TRK-03')
  const [backup, setBackup] = useState(false)
  const [note, setNote] = useState('')

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key.toLowerCase() === 'd' && !(e.target as HTMLElement)?.closest('input,select,textarea')) {
        setOpen((v) => !v)
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  const say = (text: string) => { setNote(text); window.setTimeout(() => setNote(''), 2500) }
  const fault = async (kind: string, on: boolean) => {
    const r = await api.fault(target, kind, on)
    say(r.ok ? `${target}: ${kind} ${on ? 'on' : 'off'}` : 'no broker - is the simulator running?')
  }

  if (!open) return <button className="demo-tab" onClick={() => setOpen(true)}>D</button>

  return (
    <div className="panel demo">
      <div className="alert-head">
        <h2>{s.demoPanel}</h2>
        <button className="ghost" onClick={() => setOpen(false)}>close</button>
      </div>

      <label className="row">
        <span>truck</span>
        <select value={target} onChange={(e) => setTarget(e.target.value)}>
          {trucks.map((t) => (
            <option key={t.truck_id} value={t.truck_id}>
              {t.truck_id} {t.truck_id === realTruck ? '(real sensor)' : ''}
            </option>
          ))}
        </select>
      </label>

      <div className="demo-buttons">
        <button onClick={() => fault('door', true)}>{s.door}</button>
        <button onClick={() => fault('compressor', true)}>{s.compressor}</button>
        <button onClick={() => fault('compressor', false)}>cooling back</button>
        <button onClick={() => fault('sensor', true)}>{s.sensor}</button>
        <button onClick={() => fault('sensor', false)}>sensor back</button>
      </div>

      <label className="row switch">
        <input
          type="checkbox"
          checked={backup}
          onChange={async (e) => {
            setBackup(e.target.checked)
            const r = await api.backup(e.target.checked)
            say(r.ok ? `${realTruck} backup ${e.target.checked ? 'on' : 'off'}` : 'no broker')
          }}
        />
        <span>{s.backupMode}</span>
      </label>

      <button className="danger" onClick={async () => { await api.reset(); onReset(); say('reset') }}>
        {s.reset}
      </button>

      <div className="demo-links">
        <a href={api.trackUrl(realTruck)} target="_blank" rel="noreferrer">{s.scanBox} &rarr; /track/{realTruck}</a>
      </div>
      {note && <div className="demo-note">{note}</div>}
    </div>
  )
}
