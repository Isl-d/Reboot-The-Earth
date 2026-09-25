import type { RiskLevel } from '../../types'

const styles: Record<RiskLevel, string> = {
  LOW: 'text-risk-low bg-elevated',
  MEDIUM: 'text-risk-medium bg-elevated',
  HIGH: 'text-risk-high bg-elevated',
  CRITICAL: 'text-risk-critical bg-elevated animate-pulse',
}

interface Props {
  level: RiskLevel
  score?: number
  className?: string
}

export function RiskBadge({ level, score, className = '' }: Props) {
  return (
    <span
      className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-sm text-[11px] font-medium tracking-[0.06em] uppercase ${styles[level]} ${className}`}
    >
      <span className="w-1.5 h-1.5 rounded-full bg-current" />
      {level}
      {score !== undefined && <span className="opacity-60 ml-0.5">{score}</span>}
    </span>
  )
}
