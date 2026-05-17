import { Suspense, useRef, useState } from 'react'
import { Canvas } from '@react-three/fiber'
import { OrbitControls, useGLTF, Center, Environment } from '@react-three/drei'
import { AlertTriangle, RotateCcw, MousePointer2 } from 'lucide-react'
import type { Group } from 'three'

// ── Inner model component ─────────────────────────────────────────────────────

function GLBModel({ url }: { url: string }) {
  const { scene } = useGLTF(url)
  const groupRef = useRef<Group>(null)

  return (
    <Center>
      <primitive ref={groupRef} object={scene} />
    </Center>
  )
}

// ── Error boundary component ──────────────────────────────────────────────────

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
      <div className="w-10 h-10 rounded-full border-3 border-orange-500/30 border-t-orange-500 animate-spin" style={{ borderWidth: 3 }} />
      <p className="text-sm text-gray-400">Loading preview…</p>
    </div>
  )
}

// ── Scene ─────────────────────────────────────────────────────────────────────

interface SceneProps {
  url: string
}

function Scene({ url }: SceneProps) {
  return (
    <>
      <ambientLight intensity={0.6} />
      <directionalLight position={[5, 10, 5]} intensity={1.2} castShadow />
      <directionalLight position={[-5, -5, -5]} intensity={0.3} />
      <Environment preset="city" />
      <GLBModel url={url} />
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

  const handleRetry = () => {
    setHasError(false)
    setIsLoading(true)
    setKey(k => k + 1)
    // Clear drei's GLTF cache for this URL
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
            onCreated={() => setIsLoading(false)}
            style={{ background: 'transparent' }}
            gl={{ antialias: true, alpha: true }}
          >
            <Suspense fallback={null}>
              <Scene url={glbUrl} />
            </Suspense>
          </Canvas>

          {isLoading && <LoadingOverlay />}

          {/* Hint text */}
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
