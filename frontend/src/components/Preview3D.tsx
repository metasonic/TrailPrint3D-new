import { useEffect, useRef } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";

interface Props {
  glbUrl: string | null;
  loading?: boolean;
  loadingMessage?: string;
  errorMessage?: string | null;
  onError?: (msg: string) => void;
}

function disposeMesh(mesh: THREE.Mesh) {
  mesh.geometry.dispose();
  const mat = mesh.material;
  if (Array.isArray(mat)) mat.forEach((m) => m.dispose());
  else mat.dispose();
}

export default function Preview3D({ glbUrl, loading = false, loadingMessage = "Generating preview…", errorMessage, onError }: Props) {
  const ariaLabel = glbUrl
    ? "Interactive 3D terrain preview. Use mouse drag or arrow keys to orbit, scroll to zoom, right-click to pan."
    : loading
    ? "3D terrain preview — loading"
    : "3D terrain preview — no model loaded";
  const mountRef = useRef<HTMLDivElement>(null);
  // Ref to always invoke the latest onError without stale-closure risk
  const onErrorRef = useRef(onError);
  useEffect(() => { onErrorRef.current = onError; });
  const rendererRef = useRef<THREE.WebGLRenderer | null>(null);
  const sceneRef = useRef<THREE.Scene | null>(null);
  const cameraRef = useRef<THREE.PerspectiveCamera | null>(null);
  const controlsRef = useRef<OrbitControls | null>(null);
  const modelGroupRef = useRef<THREE.Group | null>(null);
  const gridRef = useRef<THREE.GridHelper | null>(null);

  // Initialize Three.js scene once
  useEffect(() => {
    if (!mountRef.current) return;
    const el = mountRef.current;

    const renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setPixelRatio(window.devicePixelRatio);
    renderer.setSize(el.clientWidth, el.clientHeight);
    renderer.setClearColor(0x0d0d1a, 1); // explicit clear avoids transparency flicker on canvas resize
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    el.appendChild(renderer.domElement);
    rendererRef.current = renderer;

    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x0d0d1a); // matches CSS --bg
    // Fog gracefully fades the grid edges into the background instead of hard-terminating
    scene.fog = new THREE.Fog(0x0d0d1a, 250, 550);
    sceneRef.current = scene;

    // Reduced ambient (0.35) preserves shadow contrast for terrain depth reading
    const ambient = new THREE.AmbientLight(0xffffff, 0.35);
    scene.add(ambient);
    const sun = new THREE.DirectionalLight(0xfff8e0, 1.4);
    sun.position.set(80, 120, 60);
    sun.castShadow = true;
    sun.shadow.mapSize.set(2048, 2048);
    scene.add(sun);
    // Clearer cool-blue fill separates shadow faces from the background
    const fill = new THREE.DirectionalLight(0x8ab4e8, 0.4);
    fill.position.set(-60, 40, -80);
    scene.add(fill);

    const grid = new THREE.GridHelper(400, 20, 0x4a4a72, 0x2e2e52);
    grid.position.y = -0.5;
    scene.add(grid);
    gridRef.current = grid;

    const camera = new THREE.PerspectiveCamera(45, el.clientWidth / el.clientHeight, 0.01, 10000);
    camera.position.set(0, 80, 120);
    cameraRef.current = camera;

    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.08;
    controls.minDistance = 5;
    controls.maxDistance = 2000;
    controls.maxPolarAngle = Math.PI * 0.75;
    controlsRef.current = controls;

    let animId: number;
    function animate() {
      animId = requestAnimationFrame(animate);
      controls.update();
      renderer.render(scene, camera);
    }
    animId = requestAnimationFrame(animate);

    const ro = new ResizeObserver(() => {
      if (!mountRef.current) return;
      const w = mountRef.current.clientWidth;
      const h = mountRef.current.clientHeight;
      renderer.setSize(w, h);
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
    });
    ro.observe(el);

    return () => {
      cancelAnimationFrame(animId);
      ro.disconnect();
      controls.dispose();
      if (modelGroupRef.current) {
        modelGroupRef.current.traverse((child) => {
          if ((child as THREE.Mesh).isMesh) disposeMesh(child as THREE.Mesh);
        });
        modelGroupRef.current = null;
      }
      if (gridRef.current) {
        (gridRef.current.geometry as THREE.BufferGeometry).dispose();
        const mat = gridRef.current.material;
        if (Array.isArray(mat)) mat.forEach((m) => m.dispose());
        else (mat as THREE.Material).dispose();
        gridRef.current = null;
      }
      renderer.dispose();
      el.removeChild(renderer.domElement);
    };
  }, []);

  // Load GLB whenever URL changes
  useEffect(() => {
    if (!sceneRef.current || !cameraRef.current || !controlsRef.current) return;

    if (modelGroupRef.current) {
      modelGroupRef.current.traverse((child) => {
        if ((child as THREE.Mesh).isMesh) disposeMesh(child as THREE.Mesh);
      });
      sceneRef.current.remove(modelGroupRef.current);
      modelGroupRef.current = null;
    }

    if (!glbUrl) return;

    // Cancellation flag: if glbUrl changes before this load completes, ignore the stale callback
    let cancelled = false;

    const loader = new GLTFLoader();
    loader.load(
      glbUrl,
      (gltf) => {
        if (cancelled) {
          gltf.scene.traverse((child) => {
            if ((child as THREE.Mesh).isMesh) {
              const mesh = child as THREE.Mesh;
              mesh.geometry.dispose();
              const mat = mesh.material;
              if (Array.isArray(mat)) mat.forEach((m) => m.dispose());
              else mat.dispose();
            }
          });
          return;
        }

        const group = new THREE.Group();
        gltf.scene.traverse((child) => {
          if ((child as THREE.Mesh).isMesh) {
            const mesh = child as THREE.Mesh;
            mesh.castShadow = true;
            mesh.receiveShadow = true;
            const origMat = mesh.material;
            if (Array.isArray(origMat)) origMat.forEach((m) => m.dispose());
            else origMat.dispose();
            mesh.material =
              child.name === "trail"
                // Slightly metallic trail pops against the matte terrain
                ? new THREE.MeshStandardMaterial({ color: 0xdc3232, roughness: 0.45, metalness: 0.2 })
                : new THREE.MeshStandardMaterial({ color: 0xa8aab4, roughness: 0.65, metalness: 0.05 });
          }
        });
        group.add(gltf.scene);
        sceneRef.current!.add(group);
        modelGroupRef.current = group;

        const box = new THREE.Box3().setFromObject(group);
        const center = box.getCenter(new THREE.Vector3());
        const size = box.getSize(new THREE.Vector3());
        const maxDim = Math.max(size.x, size.y, size.z);

        controlsRef.current!.target.copy(center);
        cameraRef.current!.position.set(center.x, center.y + maxDim * 0.8, center.z + maxDim * 1.2);
        cameraRef.current!.updateProjectionMatrix();
        controlsRef.current!.update();
      },
      undefined,
      (err) => {
        if (cancelled) return;
        const msg = err instanceof Error ? err.message : "Failed to load 3D model";
        onErrorRef.current?.(msg);
      }
    );

    return () => {
      cancelled = true;
    };
  }, [glbUrl]);

  return (
    <div style={{ position: "relative", width: "100%", height: "100%" }}>
      <div
        ref={mountRef}
        tabIndex={0}
        role="application"
        aria-label={ariaLabel}
        style={{ width: "100%", height: "100%", touchAction: "none" }}
      />
      {/* Persistent live region — always in DOM so NVDA/JAWS pick up text changes */}
      <div
        role="status"
        aria-live="polite"
        aria-atomic="true"
        style={{
          position: "absolute",
          inset: loading ? 0 : undefined,
          width: loading ? undefined : 1,
          height: loading ? undefined : 1,
          overflow: loading ? undefined : "hidden",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          // Plain dark overlay — backdrop-filter blur over WebGL causes GPU compositing cost
          background: loading ? "rgba(13,13,26,0.8)" : "transparent",
          color: "#fff",
          fontSize: "1rem",
          gap: "0.5rem",
          pointerEvents: loading ? undefined : "none",
        }}
      >
        {loading ? (
          <>
            <span className="spinner" aria-hidden="true" />
            {loadingMessage}
          </>
        ) : glbUrl ? (
          "Preview ready"
        ) : (
          ""
        )}
      </div>
      {/* Error overlay — bottom-anchored so OrbitControls remain accessible above it */}
      {errorMessage && !loading && (
        <div
          role="alert"
          style={{
            position: "absolute",
            bottom: "0.75rem",
            left: "0.75rem",
            right: "0.75rem",
            background: "rgba(239,68,68,0.15)",
            border: "1px solid #ef4444",
            color: "#f87171",
            borderRadius: "8px",
            padding: "0.5rem 0.75rem",
            fontSize: "0.8rem",
            lineHeight: 1.5,
            // Allow text selection so users can copy error details for bug reports
            pointerEvents: "auto",
            userSelect: "text",
          }}
        >
          {errorMessage}
        </div>
      )}
      {!glbUrl && !loading && (
        <div
          aria-hidden="true"
          style={{
            position: "absolute",
            inset: 0,
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            color: "#8899cc",
            pointerEvents: "none",
          }}
        >
          {/* Mountain / terrain icon — semantically related to the feature */}
          <svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true">
            <path d="M3 20l5-9 4 6 3-5 6 8H3z" />
            <circle cx="17" cy="5" r="2" />
          </svg>
          <p style={{ marginTop: "1rem", fontSize: "1rem", fontWeight: 500 }}>Upload a GPX file to see the 3D preview</p>
          <p style={{ marginTop: "0.35rem", fontSize: "0.85rem", color: "#6677aa" }}>Supports .gpx and .igc formats</p>
        </div>
      )}
    </div>
  );
}
