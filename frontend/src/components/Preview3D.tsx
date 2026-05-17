import { useEffect, useRef, useState } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";

interface Props {
  glbUrl: string | null;
  loading?: boolean;
  onError?: (msg: string) => void;
}

export default function Preview3D({ glbUrl, loading = false, onError }: Props) {
  const mountRef = useRef<HTMLDivElement>(null);
  const rendererRef = useRef<THREE.WebGLRenderer | null>(null);
  const sceneRef = useRef<THREE.Scene | null>(null);
  const cameraRef = useRef<THREE.PerspectiveCamera | null>(null);
  const controlsRef = useRef<OrbitControls | null>(null);
  const modelGroupRef = useRef<THREE.Group | null>(null);

  // Initialize Three.js scene once
  useEffect(() => {
    if (!mountRef.current) return;
    const el = mountRef.current;

    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setPixelRatio(window.devicePixelRatio);
    renderer.setSize(el.clientWidth, el.clientHeight);
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    el.appendChild(renderer.domElement);
    rendererRef.current = renderer;

    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x1a1a2e);
    sceneRef.current = scene;

    const ambient = new THREE.AmbientLight(0xffffff, 0.6);
    scene.add(ambient);
    const sun = new THREE.DirectionalLight(0xfff8e0, 1.4);
    sun.position.set(80, 120, 60);
    sun.castShadow = true;
    sun.shadow.mapSize.set(2048, 2048);
    scene.add(sun);
    const fill = new THREE.DirectionalLight(0xc0d8ff, 0.4);
    fill.position.set(-60, 40, -80);
    scene.add(fill);

    const grid = new THREE.GridHelper(400, 20, 0x333355, 0x222244);
    grid.position.y = -0.5;
    scene.add(grid);

    const camera = new THREE.PerspectiveCamera(45, el.clientWidth / el.clientHeight, 0.01, 10000);
    camera.position.set(0, 150, 200);
    cameraRef.current = camera;

    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.08;
    controls.minDistance = 5;
    controls.maxDistance = 2000;
    controls.maxPolarAngle = Math.PI * 0.85;
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
      renderer.dispose();
      el.removeChild(renderer.domElement);
    };
  }, []);

  // Load GLB whenever URL changes
  useEffect(() => {
    if (!sceneRef.current || !cameraRef.current || !controlsRef.current) return;

    // Dispose old model to prevent geometry/material leaks
    if (modelGroupRef.current) {
      modelGroupRef.current.traverse((child) => {
        if ((child as THREE.Mesh).isMesh) {
          const mesh = child as THREE.Mesh;
          mesh.geometry.dispose();
          const mat = mesh.material;
          if (Array.isArray(mat)) mat.forEach((m) => m.dispose());
          else mat.dispose();
        }
      });
      sceneRef.current.remove(modelGroupRef.current);
      modelGroupRef.current = null;
    }

    if (!glbUrl) return;

    const loader = new GLTFLoader();
    loader.load(
      glbUrl,
      (gltf) => {
        const group = new THREE.Group();
        gltf.scene.traverse((child) => {
          if ((child as THREE.Mesh).isMesh) {
            const mesh = child as THREE.Mesh;
            mesh.castShadow = true;
            mesh.receiveShadow = true;
            mesh.material =
              child.name === "trail"
                ? new THREE.MeshStandardMaterial({ color: 0xdc3232, roughness: 0.6, metalness: 0.1 })
                : new THREE.MeshStandardMaterial({ color: 0xb8b8c0, roughness: 0.8, metalness: 0.05 });
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
        const msg = err instanceof Error ? err.message : "Failed to load 3D model";
        onError?.(msg);
      }
    );
  }, [glbUrl]);

  return (
    <div style={{ position: "relative", width: "100%", height: "100%" }}>
      <div ref={mountRef} style={{ width: "100%", height: "100%" }} aria-label="3D terrain preview" role="img" />
      {loading && (
        <div
          role="status"
          aria-live="polite"
          style={{
            position: "absolute",
            inset: 0,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            background: "rgba(26,26,46,0.7)",
            color: "#fff",
            fontSize: "1rem",
            gap: "0.5rem",
          }}
        >
          <span className="spinner" aria-hidden="true" /> Generating preview…
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
            color: "#667",
            pointerEvents: "none",
          }}
        >
          <svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true">
            <path d="M12 2L2 7l10 5 10-5-10-5z" />
            <path d="M2 17l10 5 10-5" />
            <path d="M2 12l10 5 10-5" />
          </svg>
          <p style={{ marginTop: "1rem" }}>Upload a GPX file to see the 3D preview</p>
        </div>
      )}
    </div>
  );
}
