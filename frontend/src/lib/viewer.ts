import * as THREE from "three";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";

export class Viewer3D {
  private readonly scene: THREE.Scene;
  private readonly camera: THREE.PerspectiveCamera;
  private readonly renderer: THREE.WebGLRenderer;
  private readonly controls: OrbitControls;
  private readonly loader = new GLTFLoader();
  private model: THREE.Object3D | null = null;

  constructor(canvas: HTMLCanvasElement) {
    const container = canvas.parentElement ?? document.body;
    const w = container.clientWidth;
    const h = container.clientHeight;

    this.scene = new THREE.Scene();
    this.scene.background = new THREE.Color(0x0a0f1a);
    this.scene.fog = new THREE.FogExp2(0x0a0f1a, 0.0008);

    this.camera = new THREE.PerspectiveCamera(50, w / h, 0.1, 10_000);
    this.camera.position.set(0, 150, 250);

    this.renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    this.renderer.setSize(w, h, false);

    // Three-point lighting for terrain
    this.scene.add(new THREE.AmbientLight(0xffffff, 0.6));
    const sun = new THREE.DirectionalLight(0xfff8f0, 1.8);
    sun.position.set(1, 2, 1.5);
    this.scene.add(sun);
    const fill = new THREE.DirectionalLight(0xd0e8ff, 0.4);
    fill.position.set(-1, 0.5, -1);
    this.scene.add(fill);

    this.controls = new OrbitControls(this.camera, canvas);
    this.controls.enableDamping = true;
    this.controls.dampingFactor = 0.06;
    this.controls.screenSpacePanning = false;

    new ResizeObserver(() => {
      const cw = container.clientWidth;
      const ch = container.clientHeight;
      this.camera.aspect = cw / ch;
      this.camera.updateProjectionMatrix();
      this.renderer.setSize(cw, ch, false);
    }).observe(container);

    this.tick();
  }

  get hasModel(): boolean {
    return this.model !== null;
  }

  async loadGLB(url: string): Promise<void> {
    if (this.model) {
      this.scene.remove(this.model);
      this.model = null;
    }
    const gltf = await this.loader.loadAsync(url);
    this.model = gltf.scene;
    this.scene.add(gltf.scene);
    this.fitCamera(gltf.scene);
  }

  private fitCamera(object: THREE.Object3D): void {
    const box = new THREE.Box3().setFromObject(object);
    const center = box.getCenter(new THREE.Vector3());
    const size = box.getSize(new THREE.Vector3()).length();

    this.camera.near = size / 200;
    this.camera.far = size * 100;
    this.camera.updateProjectionMatrix();

    const dist = size * 1.3;
    this.camera.position.set(
      center.x,
      center.y + size * 0.5,
      center.z + dist,
    );
    this.controls.target.copy(center);
    this.controls.minDistance = size * 0.05;
    this.controls.maxDistance = size * 8;
    this.controls.update();
  }

  private tick(): void {
    requestAnimationFrame(() => this.tick());
    this.controls.update();
    this.renderer.render(this.scene, this.camera);
  }
}
