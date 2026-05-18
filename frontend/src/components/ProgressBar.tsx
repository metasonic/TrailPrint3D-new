import { useEffect, useRef, useState, useCallback } from 'react'
import { X, Clock, Zap } from 'lucide-react'

interface ProgressBarProps {
  progress: number   // 0 – 1
  phase: string
  message: string
  onCancel?: () => void
}

function formatDuration(seconds: number): string {
  const m = Math.floor(seconds / 60)
  const s = Math.floor(seconds % 60)
  if (m === 0) return `${s}s`
  return `${m}m ${s}s`
}

export default function ProgressBar({ progress, phase, message, onCancel }: ProgressBarProps) {
  const startRef = useRef<number>(Date.now())
  const [elapsed, setElapsed] = useState(0)
  const [cancelling, setCancelling] = useState(false)

  useEffect(() => {
    startRef.current = Date.now()
    setElapsed(0)
    const id = setInterval(() => {
      setElapsed(Math.floor((Date.now() - startRef.current) / 1000))
    }, 1000)
    return () => clearInterval(id)
  }, [])

  const pct = Math.round(progress * 100)

  // Only show ETA after 5 s and 2% progress, and hide when < 5 s remaining
  let etaText: string | null = null
  if (progress > 0.02 && progress < 0.98 && elapsed > 5) {
    const totalEstimated = elapsed / progress
    const remaining = Math.max(0, totalEstimated - elapsed)
    if (remaining > 5) {
      etaText = `~${formatDuration(remaining)} remaining`
    }
  }

  const handleCancel = useCallback(() => {
    if (cancelling) return
    setCancelling(true)
    onCancel?.()
  }, [cancelling, onCancel])

  return (
    <div className="card space-y-4">
      {/* Header row */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Zap size={18} className="text-orange-500" />
          <span className="font-semibold text-gray-200 text-sm">
            {phase || 'Generating…'}
          </span>
        </div>
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1.5 text-xs text-gray-500">
            <Clock size={13} />
            <span>{formatDuration(elapsed)}</span>
          </div>
          <span className="text-orange-400 font-semibold text-sm tabular-nums">
            {pct}%
          </span>
          <button
            onClick={handleCancel}
            disabled={cancelling}
            className="p-1 rounded hover:bg-gray-700 text-gray-500 hover:text-red-400 transition-colors disabled:opacity-50"
            title="Cancel generation"
            aria-label="Cancel generation"
          >
            <X size={16} />
          </button>
        </div>
      </div>

      {/* Progress bar */}
      <div className="w-full bg-gray-800 rounded-full h-2.5 overflow-hidden">
        <div
          className={[
            'h-full rounded-full transition-all duration-500 ease-out',
            progress < 0.98 ? 'progress-shimmer' : 'bg-orange-500',
          ].join(' ')}
          style={{ width: `${Math.max(pct, 2)}%` }}
          role="progressbar"
          aria-label="Generation progress"
          aria-valuenow={pct}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuetext={`${pct}% — ${phase || 'Generating'}`}
        />
      </div>

      {/* Sub-message */}
      {(message || etaText) && (
        <div className="flex items-center justify-between text-xs text-gray-500">
          {message && <span className="truncate">{message}</span>}
          {etaText && <span className="shrink-0 ml-2">{etaText}</span>}
        </div>
      )}

      {cancelling && (
        <p className="text-xs text-red-400">Cancellation requested…</p>
      )}
    </div>
  )
}
