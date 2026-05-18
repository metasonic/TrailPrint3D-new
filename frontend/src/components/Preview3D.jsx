import { Canvas, useFrame } from '@react-three/fiber';
import { OrbitControls, Stage, useGLTF } from '@react-three/drei';
import { Suspense, useRef } from 'react';

function Model({ url }) {
  const { scene } = useGLTF(url);
  return <primitive object={scene} />;
}

function PlaceholderMesh() {
  const meshRef = useRef();

  useFrame((state, delta) => {
    if (meshRef.current) {
      meshRef.current.rotation.y += delta * 0.5;
      meshRef.current.rotation.x += delta * 0.2;
    }
  });

  return (
    <mesh ref={meshRef}>
      <octahedronGeometry args={[1, 2]} />
      <meshStandardMaterial color="#4b5563" wireframe={true} transparent opacity={0.5} />
    </mesh>
  );
}

export default function Preview3D({ modelUrl }) {
  return (
    <div className="w-full h-full bg-gray-200 relative">
      <Canvas shadows camera={{ position: [0, 5, 10], fov: 50 }}>
        <Suspense fallback={null}>
          <Stage environment="city" intensity={0.5}>
            {modelUrl ? (
              <Model url={modelUrl} />
            ) : (
              <PlaceholderMesh />
            )}
          </Stage>
        </Suspense>
        <OrbitControls makeDefault />
      </Canvas>
      {!modelUrl && (
        <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
          <div className="bg-white/90 p-4 rounded-lg shadow-lg text-gray-700 font-medium">
            Upload a GPX file to generate your 3D map
          </div>
        </div>
      )}
    </div>
  );
}
