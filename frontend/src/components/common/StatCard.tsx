interface Props {
  label: string
  value: string | number
  unit?: string
  highlight?: boolean
  dim?: boolean
}

export function StatCard({ label, value, unit, highlight, dim }: Props) {
  return (
    <div
      className={`bg-surface border rounded-md p-3 flex flex-col gap-1 [animation:slide-in-up_0.4s_ease-out_both] transition-all duration-300 ${
        highlight
          ? 'border-risk-critical [animation:glow-critical_2s_ease-in-out_infinite]'
          : 'border-border hover:border-primary/40'
      }`}
    >
      <span className="text-[10px] font-medium tracking-[0.08em] uppercase text-text-secondary">
        {label}
      </span>
      <div className="flex items-baseline gap-1.5">
        <span
          className={`font-mono text-[22px] font-semibold leading-none [animation:count-up_0.5s_ease-out_both] ${
            highlight ? 'text-risk-critical' : dim ? 'text-text-secondary' : 'text-text-primary'
          }`}
        >
          {value}
        </span>
        {unit && <span className="text-[11px] text-text-secondary font-mono">{unit}</span>}
      </div>
    </div>
  )
}
