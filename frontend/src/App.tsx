import { useState, useCallback, useEffect, useRef, lazy, Suspense } from 'react'
import { AlertCircle, RefreshCw, Settings2, MapPin } from 'lucide-react'
import GPXUpload from './components/GPXUpload'
import SettingsPanel, { DEFAULT_PARAMS } from './components/SettingsPanel'
import ProgressBar from './components/ProgressBar'
import DownloadPanel from './components/DownloadPanel'
import { useJobSSE } from './hooks/useJobSSE'
import { uploadGPX, submitJob, cancelJob, getFileUrl } from './api/client'
import type { AppState, GenerationParams } from './types'

// Lazy-load the 3D preview to keep the initial bundle light
const Preview3D = lazy(() => import('./components/Preview3D'))

// ── Layout wrapper ────────────────────────────────────────────────────────────

function PageLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen flex flex-col bg-gray-950">
      <header className="border-b border-gray-800 bg-gray-900/80 backdrop-blur sticky top-0 z-20">
        <div className="max-w-7xl mx-auto px-4 py-3 flex items-center gap-3">
          <MapPin className="w-6 h-6 text-orange-500" strokeWidth={2} />
          <span className="font-bold text-white text-lg tracking-tight">TrailPrint3D</span>
          <span className="text-xs text-gray-600 font-mono ml-1 hidden sm:inline">
            GPS → 3D Map Generator
          </span>
        </div>
      </header>
      <main className="flex-1 max-w-7xl mx-auto w-full px-4 py-6">
        {children}
      </main>
      <footer className="border-t border-gray-800 py-3 text-center">
        <p className="text-xs text-gray-700">
          Powered by{' '}
          <a
            href="https://www.blender.org"
            target="_blank"
            rel="noopener noreferrer"
            className="text-gray-600 hover:text-gray-400 transition-colors underline underline-offset-2"
          >
            Blender
          </a>
          {' '}· TrailPrint3D
        </p>
      </footer>
    </div>
  )
}

// ── Error banner ──────────────────────────────────────────────────────────────

function ErrorBanner({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div className="card border-red-800 bg-red-900/20 flex items-start gap-3">
      <AlertCircle size={18} className="text-red-400 shrink-0 mt-0.5" />
      <div className="flex-1 min-w-0">
        <p className="text-sm font-semibold text-red-300">Error</p>
        <p className="text-sm text-red-400 mt-0.5 break-words">{message}</p>
      </div>
      <button
        onClick={onRetry}
        className="shrink-0 flex items-center gap-1.5 text-xs text-gray-400 hover:text-white
                   bg-gray-800 hover:bg-gray-700 px-3 py-1.5 rounded-lg transition-colors"
      >
        <RefreshCw size={12} />
        Retry
      </button>
    </div>
  )
}

// ── Main App ──────────────────────────────────────────────────────────────────

export default function App() {
  const [appState, setAppState] = useState<AppState>('idle')
  const [uploadId, setUploadId] = useState<string | null>(null)
  const [uploadedFilename, setUploadedFilename] = useState<string>('')
  const [jobId, setJobId] = useState<string | null>(null)
  const [params, setParams] = useState<Partial<GenerationParams>>({})
  const [errorMessage, setErrorMessage] = useState<string>('')

  // SSE: only active while generating
  const sseJobId = appState === 'generating' ? jobId : null
  const sse = useJobSSE(sseJobId)

  // Transition to done/error when SSE status changes (via useEffect to avoid setState-in-render)
  const prevSseStatus = useRef<typeof sse.status>(null)
  useEffect(() => {
    if (prevSseStatus.current === sse.status) return
    prevSseStatus.current = sse.status
    if (appState === 'generating' && sse.status === 'done') {
      setAppState('done')
    } else if (appState === 'generating' && sse.status === 'failed') {
      setErrorMessage(sse.error ?? 'An unknown error occurred during generation.')
      setAppState('error')
    }
  }, [appState, sse.status, sse.error])

  // ── Param change ────────────────────────────────────────────────────────────
  const handleParamChange = useCallback(
    (key: keyof GenerationParams, value: GenerationParams[keyof GenerationParams]) => {
      setParams(prev => ({ ...prev, [key]: value }))
    },
    [],
  )

  // ── Upload ──────────────────────────────────────────────────────────────────
  const handleFileSelected = useCallback(async (file: File) => {
    setAppState('uploading')
    setErrorMessage('')
    try {
      const result = await uploadGPX(file)
      setUploadId(result.upload_id)
      setUploadedFilename(result.filename)
      // Pre-fill trail name from filename (strip extension)
      const inferredName = result.filename.replace(/\.(gpx|igc)$/i, '').replace(/[-_]/g, ' ')
      setParams(prev => ({ ...prev, trailName: prev.trailName || inferredName }))
      setAppState('uploaded')
    } catch (err: unknown) {
      const msg =
        err instanceof Error ? err.message : 'Upload failed. Please check your connection and try again.'
      setErrorMessage(msg)
      setAppState('error')
    }
  }, [])

  // ── Generate ────────────────────────────────────────────────────────────────
  const handleGenerate = useCallback(async () => {
    if (!uploadId) return
    setErrorMessage('')
    setJobId(null)
    try {
      const result = await submitJob(uploadId, params)
      setJobId(result.job_id)
      setAppState('generating')
    } catch (err: unknown) {
      const msg =
        err instanceof Error ? err.message : 'Failed to start generation job. Please try again.'
      setErrorMessage(msg)
      setAppState('error')
    }
  }, [uploadId, params])

  // ── Cancel ──────────────────────────────────────────────────────────────────
  const handleCancel = useCallback(async () => {
    if (jobId) await cancelJob(jobId).catch(() => {})
    setAppState('uploaded')
    setJobId(null)
  }, [jobId])

  // ── Regenerate ──────────────────────────────────────────────────────────────
  const handleRegenerate = useCallback(() => {
    setJobId(null)
    setAppState('uploaded')
  }, [])

  // ── Reset to start ──────────────────────────────────────────────────────────
  const handleReset = useCallback(() => {
    setAppState('idle')
    setUploadId(null)
    setUploadedFilename('')
    setJobId(null)
    setParams({})
    setErrorMessage('')
  }, [])

  // ── Retry after error ───────────────────────────────────────────────────────
  const handleRetry = useCallback(() => {
    setErrorMessage('')
    setAppState(uploadId ? 'uploaded' : 'idle')
  }, [uploadId])

  // ─────────────────────────────────────────────────────────────────────────────
  // Render
  // ─────────────────────────────────────────────────────────────────────────────

  // Idle / Uploading → full-page upload zone
  if (appState === 'idle' || appState === 'uploading') {
    return (
      <PageLayout>
        <GPXUpload
          onUpload={handleFileSelected}
          isUploading={appState === 'uploading'}
        />
      </PageLayout>
    )
  }

  // Error with no uploadId → show upload zone with banner
  if (appState === 'error' && !uploadId) {
    return (
      <PageLayout>
        <div className="flex flex-col items-center gap-4 pt-8">
          <div className="w-full max-w-lg">
            <ErrorBanner message={errorMessage} onRetry={handleRetry} />
          </div>
          <GPXUpload onUpload={handleFileSelected} isUploading={false} />
        </div>
      </PageLayout>
    )
  }

  // Done → split layout: 3D preview left, downloads + regenerate right
  if (appState === 'done' && jobId) {
    const outputFiles = sse.files
    const glbFilename = outputFiles.find(f => f.toLowerCase().endsWith('.glb'))
    const glbUrl = glbFilename ? getFileUrl(jobId, glbFilename) : null

    return (
      <PageLayout>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Left: 3D preview */}
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-semibold text-white">3D Preview</h2>
              <button
                onClick={handleReset}
                className="text-xs text-gray-500 hover:text-gray-300 transition-colors"
              >
                New file
              </button>
            </div>
            <div className="h-[480px]">
              {glbUrl ? (
                <Suspense
                  fallback={
                    <div className="h-full card flex items-center justify-center">
                      <div className="w-10 h-10 rounded-full border-[3px] border-orange-500/30 border-t-orange-500 animate-spin" />
                    </div>
                  }
                >
                  <Preview3D glbUrl={glbUrl} />
                </Suspense>
              ) : (
                <div className="h-full card flex items-center justify-center text-gray-600 text-sm">
                  No preview available
                </div>
              )}
            </div>
          </div>

          {/* Right: downloads + re-generate */}
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-semibold text-white">
                {uploadedFilename || 'Your Map'}
              </h2>
              <span className="text-xs text-green-400 bg-green-900/30 border border-green-800 px-2 py-0.5 rounded-full">
                Done
              </span>
            </div>

            <DownloadPanel jobId={jobId} files={outputFiles} />

            <div className="card space-y-3">
              <div className="flex items-center gap-2">
                <Settings2 size={15} className="text-gray-500" />
                <span className="text-sm font-medium text-gray-400">Adjust &amp; Regenerate</span>
              </div>
              <p className="text-xs text-gray-600">
                Tweak your settings and generate again using the same GPX file.
              </p>
              <button
                onClick={handleRegenerate}
                className="w-full rounded-lg border border-gray-700 bg-gray-900 px-4 py-3 font-medium
                           transition hover:border-orange-500 hover:text-orange-400 flex items-center
                           justify-center gap-2 text-gray-300"
              >
                <RefreshCw size={15} />
                Adjust Settings &amp; Regenerate
              </button>
              <button
                onClick={handleReset}
                className="w-full text-xs text-gray-600 hover:text-gray-400 transition-colors py-1"
              >
                Start over with a new file
              </button>
            </div>
          </div>
        </div>
      </PageLayout>
    )
  }

  // Uploaded / Generating / Error-with-uploadId → settings panel + sidebar
  const isGenerating = appState === 'generating'

  return (
    <PageLayout>
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left: Settings panel (2/3 width on large screens) */}
        <div className="lg:col-span-2 space-y-4">
          {/* File info bar */}
          <div className="flex items-center justify-between bg-gray-900 border border-gray-800 rounded-xl px-4 py-3">
            <div className="flex items-center gap-2 min-w-0">
              <MapPin size={15} className="text-orange-400 shrink-0" />
              <span className="text-sm text-gray-300 truncate font-medium">
                {uploadedFilename || 'Uploaded GPX'}
              </span>
              <span className="text-xs text-green-500 shrink-0">✓</span>
            </div>
            {!isGenerating && (
              <button
                onClick={handleReset}
                className="text-xs text-gray-600 hover:text-gray-300 shrink-0 ml-2 transition-colors"
              >
                Change file
              </button>
            )}
          </div>

          <SettingsPanel
            params={params}
            onChange={handleParamChange}
            disabled={isGenerating}
          />
        </div>

        {/* Right: progress / generate button */}
        <div className="space-y-4">
          {/* Error banner */}
          {appState === 'error' && (
            <ErrorBanner message={errorMessage} onRetry={handleRetry} />
          )}

          {/* Progress */}
          {isGenerating && jobId && (
            <ProgressBar
              jobId={jobId}
              progress={sse.progress}
              phase={sse.phase}
              message={sse.message}
              onCancel={handleCancel}
            />
          )}

          {/* Generate button */}
          {!isGenerating && (
            <button
              onClick={handleGenerate}
              disabled={!uploadId}
              className="w-full rounded-lg bg-orange-600 px-6 py-4 text-lg font-bold transition
                         hover:bg-orange-500 active:scale-95 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Generate 3D Map
            </button>
          )}

          {/* Active settings summary */}
          {!isGenerating && (
            <div className="card space-y-2 text-xs text-gray-600">
              <p className="font-semibold text-gray-500 uppercase tracking-wider">Active Settings</p>
              <div className="space-y-1">
                <p>Shape: <span className="text-gray-400">{params.shape ?? DEFAULT_PARAMS.shape}</span></p>
                <p>Size: <span className="text-gray-400">{params.objSize ?? DEFAULT_PARAMS.objSize} mm</span></p>
                <p>API: <span className="text-gray-400">{params.api ?? DEFAULT_PARAMS.api}</span></p>
                <p>Subdivisions: <span className="text-gray-400">{params.num_subdivisions ?? DEFAULT_PARAMS.num_subdivisions}</span></p>
                <p>Elev. Scale: <span className="text-gray-400">{params.scaleElevation ?? DEFAULT_PARAMS.scaleElevation}×</span></p>
              </div>
            </div>
          )}

          {!isGenerating && (
            <p className="text-xs text-gray-700 text-center px-2">
              Generation typically takes 2–10 minutes depending on area size and enabled elements.
            </p>
          )}
        </div>
      </div>
    </PageLayout>
  )
}
