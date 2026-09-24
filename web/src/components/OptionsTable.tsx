// Every option with its numbers, so a judge can check the recommendation
// instead of trusting it. Pick any row, not just the recommended one.
import { fmt } from '../theme'
import type { Strings } from '../i18n'
import type { Decision, Option } from '../types'

interface Props {
  decision: Decision
  chosen: string
  onChoose: (key: string) => void
  s: Strings
  lang: 'en' | 'ar'
}

export function OptionsTable({ decision, chosen, onChoose, s, lang }: Props) {
  const min = Number(decision.facts.store_minimum_days ?? 0)
  return (
    <table className="options">
      <thead>
        <tr>
          <th />
          <th>{s.action}</th>
          <th>{s.arrival}</th>
          <th>{s.kgSaved}</th>
          <th>{s.extraKm}</th>
          <th>{s.value}</th>
        </tr>
      </thead>
      <tbody>
        {decision.options.map((o: Option) => (
          <tr
            key={o.key}
            className={[
              o.key === chosen ? 'is-chosen' : '',
              o.key === decision.recommended ? 'is-recommended' : '',
              o.feasible ? '' : 'is-infeasible',
            ].join(' ')}
            onClick={() => onChoose(o.key)}
          >
            <td>
              <input type="radio" readOnly checked={o.key === chosen} />
              <span className="okey">{o.key}</span>
            </td>
            <td>
              <span className={`verb verb-${o.action}`}>{s.verbs[o.action]}</span>
              <div className="otitle">{lang === 'ar' ? o.title_ar : o.title_en}</div>
              <div className="owhy">{o.why}</div>
            </td>
            <td className={o.feasible ? 'ok' : 'bad'}>
              {fmt(o.life_on_arrival_days)}d
              <div className="muted tiny">{s.storeNeeds} {min}d</div>
            </td>
            <td>{o.kg_saved.toLocaleString()}</td>
            <td>{o.extra_km > 0 ? `+${fmt(o.extra_km, 0)}` : fmt(o.extra_km, 0)}</td>
            <td>{o.score.toLocaleString()} QAR</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}
