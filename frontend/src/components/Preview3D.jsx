import { Canvas } from '@react-three/fiber';
import { OrbitControls, Stage, useGLTF } from '@react-three/drei';
import { Suspense } from 'react';

function Model({ url }) {
  const { scene } = useGLTF(url);
  return <primitive object={scene} />;
}

export default function Preview3D({ modelUrl }) {
  return (
    <div className="w-full h-full bg-gray-200">
      <Canvas shadows camera={{ position: [0, 5, 10], fov: 50 }}>
        <Suspense fallback={null}>
          <Stage environment="city" intensity={0.5}>
            {modelUrl ? (
              <Model url={modelUrl} />
            ) : (
              <mesh>
                <boxGeometry args={[1, 1, 1]} />
                <meshStandardMaterial color="hotpink" />
              </mesh>
            )}
          </Stage>
        </Suspense>
        <OrbitControls makeDefault />
      </Canvas>
      {!modelUrl && (
        <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
          <div className="bg-white/80 p-4 rounded shadow text-gray-700">
            Upload a GPX file to generate preview
          </div>
        </div>
      )}
    </div>
  );
}
