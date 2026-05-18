import { Component, Suspense, useEffect, useRef, useState } from 'react'
import { Canvas } from '@react-three/fiber'
import { OrbitControls, useGLTF, Center, Environment } from '@react-three/drei'
import { AlertTriangle, RotateCcw, MousePointer2 } from 'lucide-react'
import type { Group } from 'three'
import type { ReactNode } from 'react'

// ── Error boundary ────────────────────────────────────────────────────────────

interface EBState { hasError: boolean }

class ModelErrorBoundary extends Component<{ onError: () => void; children: ReactNode }, EBState> {
  constructor(props: { onError: () => void; children: ReactNode }) {
    super(props)
    this.state = { hasError: false }
  }
  static getDerivedStateFromError(): EBState {
    return { hasError: true }
  }
  componentDidCatch() {
    this.props.onError()
  }
  render() {
    return this.state.hasError ? null : this.props.children
  }
}

// ── Inner model component ─────────────────────────────────────────────────────

function GLBModel({ url, onLoad }: { url: string; onLoad: () => void }) {
  const { scene } = useGLTF(url)
  const groupRef = useRef<Group>(null)

  // Signal parent after first render — model is ready by the time this component mounts.
  useEffect(() => { onLoad() }, []) // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <Center>
      <primitive ref={groupRef} object={scene} />
    </Center>
  )
}

// ── Error fallback ────────────────────────────────────────────────────────────

function ModelErrorFallback({ onRetry }: { onRetry: () => void }) {
  return (
    <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 text-gray-400">
      <AlertTriangle size={32} className="text-yellow-500" />
      <p className="text-sm text-center px-4">Failed to load 3D preview.</p>
      <button
        onClick={onRetry}
        className="flex items-center gap-1.5 text-xs text-orange-400 hover:text-orange-300"
      >
        <RotateCcw size={13} />
        Retry
      </button>
    </div>
  )
}

// ── Loading overlay ───────────────────────────────────────────────────────────

function LoadingOverlay() {
  return (
    <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 bg-gray-900/80 rounded-xl">
      <div className="w-10 h-10 rounded-full border-orange-500/30 border-t-orange-500 animate-spin" style={{ borderWidth: 3 }} />
      <p className="text-sm text-gray-400">Loading preview…</p>
    </div>
  )
}

// ── Scene ─────────────────────────────────────────────────────────────────────

function Scene({ url, onLoad }: { url: string; onLoad: () => void }) {
  return (
    <>
      <ambientLight intensity={0.6} />
      <directionalLight position={[5, 10, 5]} intensity={1.2} castShadow />
      <directionalLight position={[-5, -5, -5]} intensity={0.3} />
      <Environment preset="city" />
      <Suspense fallback={null}>
        <GLBModel url={url} onLoad={onLoad} />
      </Suspense>
      <OrbitControls
        enablePan={true}
        enableZoom={true}
        enableRotate={true}
        autoRotate={true}
        autoRotateSpeed={1.5}
        makeDefault
      />
    </>
  )
}

// ── Main component ────────────────────────────────────────────────────────────

interface Preview3DProps {
  glbUrl: string
}

export default function Preview3D({ glbUrl }: Preview3DProps) {
  const [key, setKey] = useState(0)
  const [hasError, setHasError] = useState(false)
  const [isLoading, setIsLoading] = useState(true)

  const handleError = () => {
    setHasError(true)
    setIsLoading(false)
  }

  const handleLoad = () => setIsLoading(false)

  const handleRetry = () => {
    setHasError(false)
    setIsLoading(true)
    setKey(k => k + 1)
    useGLTF.clear(glbUrl)
  }

  return (
    <div className="relative w-full h-full rounded-xl overflow-hidden bg-gray-900 border border-gray-800">
      {hasError ? (
        <ModelErrorFallback onRetry={handleRetry} />
      ) : (
        <>
          <Canvas
            key={key}
            camera={{ position: [0, 3, 6], fov: 45 }}
            shadows
            style={{ background: 'transparent' }}
            gl={{ antialias: true, alpha: true }}
          >
            <ModelErrorBoundary onError={handleError}>
              <Scene url={glbUrl} onLoad={handleLoad} />
            </ModelErrorBoundary>
          </Canvas>

          {isLoading && <LoadingOverlay />}

          {!isLoading && (
            <div className="absolute bottom-3 left-1/2 -translate-x-1/2 flex items-center gap-1.5 text-xs text-gray-600 bg-gray-950/70 rounded-full px-3 py-1 pointer-events-none">
              <MousePointer2 size={11} />
              <span>Drag to rotate · Scroll to zoom</span>
            </div>
          )}
        </>
      )}
    </div>
  )
}
