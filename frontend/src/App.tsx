import { useState, useCallback, useEffect, useRef } from 'react'
import { Mountain } from 'lucide-react'
import GPXUpload from './components/GPXUpload'
import SettingsPanel from './components/SettingsPanel'
import ProgressBar from './components/ProgressBar'
import Preview3D from './components/Preview3D'
import DownloadPanel from './components/DownloadPanel'
import { useJobSSE } from './hooks/useJobSSE'
import { uploadGPX, submitJob, cancelJob, getFileUrl } from './api/client'
import type { AppState, GenerationParams } from './types'

const DEFAULT_PARAMS: Partial<GenerationParams> = {
  shape: 'HEXAGON',
  generation_mode: 'GENERATION',
  trailName: '',
  objSize: 100,
  api: 'TERRAIN-TILES',
  scaleElevation: 1,
  num_subdivisions: 4,
  minThickness: 2,
  pathThickness: 1.2,
  overwritePathElevation: true,
  singleColorMode: false,
  elementMode: 'PAINT',
  col_wPondsActive: false,
  col_wSmallRiversActive: false,
  col_wBigRiversActive: false,
  col_fActive: false,
  el_bActive: false,
  el_sBigActive: false,
  el_sMedActive: false,
  el_sSmallActive: false,
  titlefield: '{name}',
  textfield1: '{length}',
  textfield2: '{elevation}',
  textfield3: '{duration}',
  titleIcon: 'no',
  iconText1: 'distance',
  iconText2: 'elevation',
  iconText3: 'time',
  exportformat: 'AUTO',
}

export default function App() {
  const [appState, setAppState] = useState<AppState>('idle')
  const [uploadId, setUploadId] = useState<string | null>(null)
  const [uploadFilename, setUploadFilename] = useState<string>('')
  const [jobId, setJobId] = useState<string | null>(null)
  const [params, setParams] = useState<Partial<GenerationParams>>(DEFAULT_PARAMS)
  const [error, setError] = useState<string | null>(null)

  const { progress, phase, message, status: jobStatus, files } = useJobSSE(
    appState === 'generating' ? jobId : null
  )

  // Transition to done/error when job completes (use useEffect to avoid setState-in-render)
  // eslint-disable-next-line react-hooks/exhaustive-deps
  const prevJobStatus = useRef<typeof jobStatus>(null)
  useEffect(() => {
    if (prevJobStatus.current === jobStatus) return
    prevJobStatus.current = jobStatus
    if (appState === 'generating' && jobStatus === 'done') {
      setAppState('done')
    } else if (appState === 'generating' && jobStatus === 'failed') {
      setAppState('error')
      setError('Generation failed. Check settings and try again.')
    }
  }, [appState, jobStatus])

  const handleUpload = useCallback(async (file: File) => {
    setAppState('uploading')
    setError(null)
    try {
      const result = await uploadGPX(file)
      setUploadId(result.upload_id)
      setUploadFilename(result.filename)
      // Pre-fill trail name from filename
      const name = result.filename.replace(/\.(gpx|igc)$/i, '')
      setParams(p => ({ ...p, trailName: name }))
      setAppState('uploaded')
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Upload failed'
      setError(msg)
      setAppState('error')
    }
  }, [])

  const handleGenerate = useCallback(async () => {
    if (!uploadId) return
    setAppState('generating')
    setError(null)
    setJobId(null)
    try {
      const result = await submitJob(uploadId, params)
      setJobId(result.job_id)
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to start generation'
      setError(msg)
      setAppState('error')
    }
  }, [uploadId, params])

  const handleCancel = useCallback(async () => {
    if (jobId) await cancelJob(jobId).catch(() => {})
    setAppState('uploaded')
    setJobId(null)
  }, [jobId])

  const handleRegenerate = useCallback(() => {
    setAppState('uploaded')
    setJobId(null)
  }, [])

  const handleParamChange = useCallback((key: keyof GenerationParams, value: unknown) => {
    setParams(p => ({ ...p, [key]: value }))
  }, [])

  const glbFile = files.find(f => f.endsWith('.glb'))
  const glbUrl = glbFile && jobId ? getFileUrl(jobId, glbFile) : null

  return (
    <div className="min-h-screen bg-gray-950 text-gray-100">
      {/* Header */}
      <header className="border-b border-gray-800 bg-gray-900 px-6 py-4">
        <div className="mx-auto flex max-w-7xl items-center gap-3">
          <Mountain className="h-7 w-7 text-orange-500" />
          <span className="text-xl font-bold tracking-tight">TrailPrint3D</span>
          <span className="ml-2 text-sm text-gray-500">Web</span>
        </div>
      </header>

      <main className="mx-auto max-w-7xl px-4 py-8">
        {/* IDLE — Upload screen */}
        {appState === 'idle' && (
          <div className="flex flex-col items-center justify-center py-16">
            <h1 className="mb-3 text-3xl font-bold">Create Your Trail Map</h1>
            <p className="mb-10 text-center text-gray-400 max-w-lg">
              Upload a GPX or IGC trail file to generate a 3D-printable miniature map.
              Customize shapes, terrain elements, and export in STL, OBJ, or 3MF.
            </p>
            <GPXUpload onUpload={handleUpload} />
          </div>
        )}

        {/* UPLOADING */}
        {appState === 'uploading' && (
          <div className="flex flex-col items-center justify-center py-24">
            <div className="h-10 w-10 animate-spin rounded-full border-4 border-orange-500 border-t-transparent" />
            <p className="mt-4 text-gray-400">Uploading file…</p>
          </div>
        )}

        {/* UPLOADED / GENERATING — Settings + Generate */}
        {(appState === 'uploaded' || appState === 'generating') && (
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
            {/* Left: Settings */}
            <div className="lg:col-span-2">
              <div className="mb-4 flex items-center justify-between rounded-lg bg-gray-900 px-4 py-3">
                <div>
                  <p className="font-medium">{uploadFilename}</p>
                  <p className="text-sm text-gray-500">File uploaded successfully</p>
                </div>
                {appState === 'uploaded' && (
                  <button
                    onClick={() => { setAppState('idle'); setUploadId(null) }}
                    className="text-sm text-gray-500 hover:text-gray-300"
                  >
                    Change file
                  </button>
                )}
              </div>
              <SettingsPanel
                params={params}
                onChange={handleParamChange}
                disabled={appState === 'generating'}
              />
            </div>

            {/* Right: Generate panel */}
            <div className="flex flex-col gap-4">
              {appState === 'uploaded' && (
                <button
                  onClick={handleGenerate}
                  className="w-full rounded-lg bg-orange-600 px-6 py-4 text-lg font-bold transition hover:bg-orange-500 active:scale-95"
                >
                  Generate Map
                </button>
              )}

              {appState === 'generating' && (
                <div className="rounded-lg bg-gray-900 p-4">
                  <ProgressBar
                    progress={progress}
                    phase={phase}
                    message={message}
                    onCancel={handleCancel}
                  />
                </div>
              )}

              {appState === 'uploaded' && (
                <div className="rounded-lg bg-gray-900 p-4 text-sm text-gray-400">
                  <p className="font-medium text-gray-300">Generation takes 30–90 seconds</p>
                  <p className="mt-1">Elevation data is fetched from external APIs. Results are cached.</p>
                </div>
              )}
            </div>
          </div>
        )}

        {/* DONE — Preview + Downloads */}
        {appState === 'done' && jobId && (
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
            {/* 3D Preview */}
            <div className="lg:col-span-2">
              <div className="overflow-hidden rounded-lg bg-gray-900">
                <div className="border-b border-gray-800 px-4 py-3">
                  <h2 className="font-semibold">3D Preview</h2>
                  <p className="text-xs text-gray-500">Click and drag to rotate · Scroll to zoom</p>
                </div>
                <div className="h-[480px]">
                  {glbUrl ? (
                    <Preview3D glbUrl={glbUrl} />
                  ) : (
                    <div className="flex h-full items-center justify-center text-gray-500">
                      Preview not available
                    </div>
                  )}
                </div>
              </div>
            </div>

            {/* Downloads + regenerate */}
            <div className="flex flex-col gap-4">
              <DownloadPanel jobId={jobId} files={files} />
              <button
                onClick={handleRegenerate}
                className="w-full rounded-lg border border-gray-700 bg-gray-900 px-4 py-3 font-medium transition hover:border-orange-500 hover:text-orange-400"
              >
                Adjust Settings &amp; Regenerate
              </button>
              <button
                onClick={() => { setAppState('idle'); setUploadId(null); setJobId(null) }}
                className="text-sm text-gray-600 hover:text-gray-400"
              >
                Start over with a new file
              </button>
            </div>
          </div>
        )}

        {/* ERROR */}
        {appState === 'error' && (
          <div className="flex flex-col items-center justify-center py-16">
            <div className="mb-4 rounded-lg border border-red-900 bg-red-950 px-6 py-4 text-red-300">
              {error ?? 'An error occurred.'}
            </div>
            <button
              onClick={() => setAppState(uploadId ? 'uploaded' : 'idle')}
              className="rounded-lg bg-orange-600 px-6 py-2 font-medium hover:bg-orange-500"
            >
              Try Again
            </button>
          </div>
        )}
      </main>

      {/* Footer */}
      <footer className="mt-16 border-t border-gray-800 py-6 text-center text-xs text-gray-600">
        Powered by{' '}
        <a href="https://www.blender.org" className="hover:text-gray-400" target="_blank" rel="noreferrer">
          Blender
        </a>{' '}
        · TrailPrint3D Web
      </footer>
    </div>
  )
}
