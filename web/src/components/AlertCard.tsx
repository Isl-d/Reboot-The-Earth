// The moment that matters: a shipment is in trouble, here is what to do, and
// nothing happens until a person presses a button.
//
// Two modes. Normally the system recommends one option and the dispatcher
// approves it. When the planner has escalated, there is no recommendation:
// the four verbs are offered and a person chooses.
import { useState } from 'react'
import { api } from '../api'
import type { Strings } from '../i18n'
import type { Decision, Verb } from '../types'
import { OptionsTable } from './OptionsTable'

const VERB_ORDER: Verb[] = ['reroute', 'sell', 'donate', 'hold', 'continue']

interface Props {
  decision: Decision
  s: Strings
  lang: 'en' | 'ar'
  onApproved: () => void
}

export function AlertCard({ decision, s, lang, onApproved }: Props) {
  const [chosen, setChosen] = useState(decision.recommended)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const approved = Boolean(decision.approved_at)
  const review = decision.needs_human_review && !approved

  const approve = async () => {
    setBusy(true)
    setError(null)
    try {
      await api.approve(decision.decision_id, chosen)
      onApproved()
    } catch (e) {
      setError(String(e))
    } finally {
      setBusy(false)
    }
  }

  const pickVerb = (verb: Verb) => {
    // Several options can share a verb (two ways to reroute). Offer the best.
    const keys = decision.verbs?.[verb] ?? []
    const best = decision.options
      .filter((o) => keys.includes(o.key))
      .sort((a, b) => b.score - a.score)[0]
    if (best) setChosen(best.key)
  }

  return (
    <div className={`panel alert ${review ? 'is-review' : ''} ${approved ? 'is-approved' : ''}`}>
      <div className="alert-head">
        <h2>{approved ? s.approved : review ? s.needsHuman : s.decision}</h2>
        <span className="muted">{decision.truck_id} &middot; {decision.decision_id}</span>
      </div>

      {review && (
        <ul className="reasons">
          {decision.review_reasons.map((r) => <li key={r}>{r}</li>)}
        </ul>
      )}

      <p className="agent-text" dir={lang === 'ar' ? 'rtl' : 'ltr'}>
        {lang === 'ar' ? decision.text_ar : decision.text_en}
      </p>
      <div className="agent-source">
        {s.sourceNote} &middot; {decision.text_source}
        {decision.text_note ? ` (${decision.text_note})` : ''}
      </div>

      {review && (
        <div className="verbs">
          {VERB_ORDER.filter((v) => decision.verbs?.[v]?.length).map((v) => (
            <button
              key={v}
              className={`verb-btn verb-${v} ${decision.verbs[v].includes(chosen) ? 'is-on' : ''}`}
              onClick={() => pickVerb(v)}
            >
              {s.verbs[v]}
            </button>
          ))}
        </div>
      )}

      <OptionsTable decision={decision} chosen={chosen} onChoose={setChosen} s={s} lang={lang} />

      {approved ? (
        <div className="approved-note">
          {s.approved}: {decision.chosen} &middot; {decision.approved_by}
          <code>{decision.hash.slice(0, 12)}</code>
        </div>
      ) : (
        <div className="alert-actions">
          <button className="primary" onClick={approve} disabled={busy}>
            {s.approve} {chosen}
          </button>
          {!review && <span className="muted">{s.recommended}: {decision.recommended}</span>}
        </div>
      )}
      {error && <div className="warn">{error}</div>}
    </div>
  )
}
