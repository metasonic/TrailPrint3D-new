import { useEffect, useRef, useState, useCallback } from 'react'
import { getStreamUrl, getJobStatus } from '../api/client'
import type { JobStatus, SSEProgressEvent } from '../types'

export interface SSEState {
  status: JobStatus['status'] | null
  progress: number
  phase: string
  message: string
  files: string[]
  error: string | null
}

const INITIAL_STATE: SSEState = {
  status: null,
  progress: 0,
  phase: '',
  message: '',
  files: [],
  error: null,
}

/**
 * Opens an EventSource to /api/jobs/{jobId}/stream and tracks job progress.
 * Falls back to polling getJobStatus every 3 s if SSE is unavailable.
 */
export function useJobSSE(jobId: string | null): SSEState & { reset: () => void } {
  const [state, setState] = useState<SSEState>(INITIAL_STATE)
  const esRef = useRef<EventSource | null>(null)
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const reset = useCallback(() => {
    setState(INITIAL_STATE)
  }, [])

  // ── Helpers ──────────────────────────────────────────────────────────────────

  const applyProgress = useCallback((ev: SSEProgressEvent) => {
    setState(prev => {
      if (ev.event === 'complete') {
        return {
          status: 'done',
          progress: 1,
          phase: ev.phase ?? 'Complete',
          message: ev.message ?? 'Generation finished.',
          files: ev.files ?? prev.files,
          error: null,
        }
      }
      if (ev.event === 'error') {
        return {
          ...prev,
          status: 'failed',
          error: ev.error ?? 'Unknown error',
          phase: 'Failed',
        }
      }
      // progress event
      return {
        ...prev,
        status: 'running',
        progress: ev.progress ?? prev.progress,
        phase: ev.phase ?? prev.phase,
        message: ev.message ?? prev.message,
      }
    })
  }, [])

  const stopPolling = useCallback(() => {
    if (pollRef.current !== null) {
      clearInterval(pollRef.current)
      pollRef.current = null
    }
  }, [])

  const startPolling = useCallback(
    (id: string) => {
      stopPolling()
      const poll = async () => {
        try {
          const job = await getJobStatus(id)
          setState({
            status: job.status,
            progress: job.progress,
            phase: job.phase,
            message: job.message,
            files: job.files,
            error: job.error,
          })
          if (job.status === 'done' || job.status === 'failed') {
            stopPolling()
          }
        } catch {
          // ignore transient errors
        }
      }
      pollRef.current = setInterval(poll, 3_000)
      void poll()
    },
    [stopPolling],
  )

  // ── Main effect ───────────────────────────────────────────────────────────────

  useEffect(() => {
    if (!jobId) {
      // Cleanup when jobId becomes null
      esRef.current?.close()
      esRef.current = null
      stopPolling()
      setState(INITIAL_STATE)
      return
    }

    setState(INITIAL_STATE)

    const url = getStreamUrl(jobId)
    let es: EventSource

    try {
      es = new EventSource(url)
    } catch {
      // EventSource not supported or URL invalid – fall back to polling
      startPolling(jobId)
      return
    }

    esRef.current = es

    es.onopen = () => {
      // SSE connected – cancel any existing poll
      stopPolling()
    }

    es.addEventListener('progress', (raw) => {
      try {
        const ev = JSON.parse((raw as MessageEvent<string>).data) as SSEProgressEvent
        applyProgress({ ...ev, event: 'progress' })
      } catch { /* ignore malformed */ }
    })

    es.addEventListener('complete', (raw) => {
      try {
        const ev = JSON.parse((raw as MessageEvent<string>).data) as SSEProgressEvent
        applyProgress({ ...ev, event: 'complete' })
      } catch { /* ignore */ }
      es.close()
    })

    es.addEventListener('error', (raw) => {
      if ((raw as MessageEvent).data) {
        try {
          const ev = JSON.parse((raw as MessageEvent<string>).data) as SSEProgressEvent
          applyProgress({ ...ev, event: 'error' })
        } catch { /* ignore */ }
      }
    })

    es.onerror = () => {
      // SSE connection dropped – fall back to polling
      es.close()
      setState(prev => {
        if (prev.status === 'done' || prev.status === 'failed') return prev
        return prev
      })
      startPolling(jobId)
    }

    // Also handle generic "message" events (server may emit data without event type)
    es.onmessage = (raw) => {
      try {
        const ev = JSON.parse(raw.data as string) as SSEProgressEvent
        if (ev.event) applyProgress(ev)
      } catch { /* ignore */ }
    }

    return () => {
      es.close()
      esRef.current = null
      stopPolling()
    }
  }, [jobId, applyProgress, startPolling, stopPolling])

  return { ...state, reset }
}
