/**
 * Three.js canvas with orbit controls. Loads a GLB from `url` whenever it
 * changes. Phase 5 only handles the canvas + scene lifecycle; the backend GLB
 * URL is wired up in Phase 6.
 */

import { useEffect, useRef } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";

interface Props {
  url: string | null;
}

export function PreviewCanvas({ url }: Props) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const sceneStateRef = useRef<SceneState | null>(null);
  const currentModelRef = useRef<THREE.Object3D | null>(null);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;
    const state = createScene(container);
    sceneStateRef.current = state;
    return () => {
      state.dispose();
      sceneStateRef.current = null;
      currentModelRef.current = null;
    };
  }, []);

  useEffect(() => {
    const state = sceneStateRef.current;
    if (!state) return;
    if (currentModelRef.current) {
      state.scene.remove(currentModelRef.current);
      disposeObject(currentModelRef.current);
      currentModelRef.current = null;
    }
    if (!url) return;
    const loader = new GLTFLoader();
    loader.load(
      url,
      (gltf) => {
        // trimesh exports with Z-up; three.js renders Y-up. Wrap the model
        // in a Group, rotate the inner model to convert Z-up -> Y-up, then
        // centre + scale + drop onto the grid via the outer Group's
        // transform. The wrapper keeps math simple: T(position) * S(scale)
        // applied to a pre-oriented child.
        const model = gltf.scene;
        model.rotation.x = -Math.PI / 2;
        const wrapper = new THREE.Group();
        wrapper.add(model);
        wrapper.updateMatrixWorld(true);

        const box = new THREE.Box3().setFromObject(wrapper);
        const size = box.getSize(new THREE.Vector3());
        const centre = box.getCenter(new THREE.Vector3());

        const target = 100; // model frame size in mm (camera frames ~target)
        const maxExtent = Math.max(size.x, size.y, size.z) || 1;
        const factor = target / maxExtent;

        // Position is applied in world units (after scale); compute it so the
        // model centre lands at (0, target/2, 0) — half-height above the grid.
        wrapper.scale.setScalar(factor);
        wrapper.position.set(-centre.x * factor, -box.min.y * factor, -centre.z * factor);

        state.scene.add(wrapper);
        currentModelRef.current = wrapper;

        // Frame the camera around the now-positioned model.
        const dist = target * 1.6;
        state.camera.position.set(dist, dist * 0.8, dist);
        state.controls.target.set(0, target * 0.15, 0);
        state.controls.update();
      },
      undefined,
      (err) => {
        console.error("GLB load failed:", err);
      },
    );
  }, [url]);

  return (
    <div
      ref={containerRef}
      data-testid="preview-canvas"
      className="h-full min-h-[420px] w-full rounded-(--radius-md) bg-[var(--color-surface)]"
    />
  );
}

interface SceneState {
  scene: THREE.Scene;
  renderer: THREE.WebGLRenderer;
  camera: THREE.PerspectiveCamera;
  controls: OrbitControls;
  dispose: () => void;
}

function createScene(container: HTMLElement): SceneState {
  const scene = new THREE.Scene();
  scene.background = new THREE.Color(0x0f1f2c);

  const camera = new THREE.PerspectiveCamera(45, 1, 0.1, 5000);
  camera.position.set(120, 120, 120);

  const renderer = new THREE.WebGLRenderer({ antialias: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  container.appendChild(renderer.domElement);

  const controls = new OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true;
  controls.dampingFactor = 0.08;
  controls.target.set(0, 0, 0);

  const ambient = new THREE.AmbientLight(0xffffff, 0.6);
  scene.add(ambient);
  const key = new THREE.DirectionalLight(0xffffff, 1.0);
  key.position.set(80, 120, 60);
  scene.add(key);
  const fill = new THREE.DirectionalLight(0xa8c8e8, 0.4);
  fill.position.set(-80, -40, -60);
  scene.add(fill);

  const grid = new THREE.GridHelper(200, 20, 0x1f3447, 0x15293a);
  grid.position.y = -1;
  scene.add(grid);

  let rafId = 0;
  const tick = () => {
    rafId = requestAnimationFrame(tick);
    controls.update();
    renderer.render(scene, camera);
  };

  const resize = () => {
    const w = container.clientWidth || 1;
    const h = container.clientHeight || 1;
    renderer.setSize(w, h, false);
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
  };
  resize();
  tick();

  const observer = new ResizeObserver(resize);
  observer.observe(container);

  return {
    scene,
    renderer,
    camera,
    controls,
    dispose: () => {
      cancelAnimationFrame(rafId);
      observer.disconnect();
      controls.dispose();
      renderer.dispose();
      if (renderer.domElement.parentElement === container) {
        container.removeChild(renderer.domElement);
      }
    },
  };
}

function disposeObject(obj: THREE.Object3D): void {
  obj.traverse((node) => {
    if (node instanceof THREE.Mesh) {
      node.geometry?.dispose();
      const mat = node.material;
      if (Array.isArray(mat)) {
        mat.forEach((m) => m.dispose());
      } else {
        mat?.dispose();
      }
    }
  });
}
