let currentSessionId = null;
let currentJobId = null;
let checkInterval = null;

// Three.js setup
const container = document.getElementById('viewer-container');
const scene = new THREE.Scene();
scene.background = new THREE.Color(0xdddddd);

const camera = new THREE.PerspectiveCamera(45, container.clientWidth / container.clientHeight, 1, 1000);
camera.position.set(0, -150, 150);

const renderer = new THREE.WebGLRenderer({ antialias: true });
renderer.setSize(container.clientWidth, container.clientHeight);
renderer.shadowMap.enabled = true;
container.appendChild(renderer.domElement);

const controls = new THREE.OrbitControls(camera, renderer.domElement);
controls.enableDamping = true;

// Lighting
const hemiLight = new THREE.HemisphereLight(0xffffff, 0x444444);
hemiLight.position.set(0, 0, 200);
scene.add(hemiLight);

const dirLight = new THREE.DirectionalLight(0xffffff);
dirLight.position.set(0, 200, 100);
dirLight.castShadow = true;
scene.add(dirLight);

window.addEventListener('resize', () => {
    camera.aspect = container.clientWidth / container.clientHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(container.clientWidth, container.clientHeight);
});

function animate() {
    requestAnimationFrame(animate);
    controls.update();
    renderer.render(scene, camera);
}
animate();

let meshGroup = new THREE.Group();
scene.add(meshGroup);

function loadSTL(url, color) {
    const loader = new THREE.STLLoader();
    loader.load(url, function (geometry) {
        const material = new THREE.MeshStandardMaterial({ color: color, roughness: 0.5 });
        const mesh = new THREE.Mesh(geometry, material);
        mesh.castShadow = true;
        mesh.receiveShadow = true;

        geometry.computeBoundingBox();
        const center = new THREE.Vector3();
        geometry.boundingBox.getCenter(center);
        mesh.position.sub(center);
        mesh.rotation.x = -Math.PI / 2;

        meshGroup.add(mesh);
    });
}

function clearMeshes() {
    while(meshGroup.children.length > 0){
        meshGroup.remove(meshGroup.children[0]);
    }
}

function pollDownload(jobId, onComplete) {
    if(checkInterval) clearInterval(checkInterval);
    checkInterval = setInterval(async () => {
        try {
            const checkRes = await fetch(`/download/${jobId}?format=stl`, { method: 'HEAD' });
            if (checkRes.ok) {
                clearInterval(checkInterval);
                onComplete();
            }
        } catch (e) {}
    }, 3000);
}

// 1. Instant Preview on Upload
document.getElementById('gpxFile').addEventListener('change', async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    const statusEl = document.getElementById('status');
    const btn = document.getElementById('generateBtn');

    statusEl.innerText = "Uploading GPX...";
    btn.disabled = true;

    const formData = new FormData();
    formData.append('gpx_file', file);

    try {
        const upRes = await fetch('/upload', { method: 'POST', body: formData });
        if (!upRes.ok) throw new Error("Upload failed");
        currentSessionId = (await upRes.json()).id;

        statusEl.innerText = "Generating fast preview...";

        const reqBody = {
            id: currentSessionId,
            settings: {
                shape: document.getElementById('shape').value,
                scaleElevation: parseFloat(document.getElementById('scaleElevation').value)
            }
        };

        const prevRes = await fetch('/preview', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(reqBody)
        });

        const previewJobId = (await prevRes.json()).job_id;

        pollDownload(previewJobId, () => {
            clearMeshes();
            loadSTL(`/download/${previewJobId}?format=stl`, 0xcccccc);
            statusEl.innerText = "Preview loaded. Adjust settings or generate high-res map.";
            btn.disabled = false;
        });

    } catch (err) {
        statusEl.innerText = `Error: ${err.message}`;
    }
});

// 2. High-Res Generation
document.getElementById('generateBtn').addEventListener('click', async () => {
    if (!currentSessionId) return;

    const statusEl = document.getElementById('status');
    const downloadLinks = document.getElementById('download-links');
    const btn = document.getElementById('generateBtn');

    btn.disabled = true;
    statusEl.innerText = "Generating high-resolution Map (this may take a few minutes)...";
    downloadLinks.classList.add('hidden');

    try {
        const reqBody = {
            id: currentSessionId,
            settings: {
                shape: document.getElementById('shape').value,
                objSize: parseFloat(document.getElementById('objSize').value),
                scaleElevation: parseFloat(document.getElementById('scaleElevation').value),
                minThickness: parseFloat(document.getElementById('minThickness').value),
                singleColorMode: document.getElementById('singleColorMode').checked ? 1 : 0,
                elementMode: document.getElementById('singleColorMode').checked ? 'MERGED' : 'SEPARATE',,
                col_wPondsActive: document.getElementById('showWater').checked ? 1 : 0,
                col_wSmallRiversActive: document.getElementById('showWater').checked ? 1 : 0,
                col_wBigRiversActive: document.getElementById('showWater').checked ? 1 : 0,
                api: "OPENTOPODATA",
                dataset: "srtm30m",
                sMapInKm: 1.0,
            }
        };

        const genRes = await fetch('/generate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(reqBody)
        });

        if (!genRes.ok) throw new Error("Generation failed");
        currentJobId = (await genRes.json()).job_id;

        pollDownload(currentJobId, () => {
            statusEl.innerText = "High-Res Generation complete!";
            downloadLinks.classList.remove('hidden');
            btn.disabled = false;

            clearMeshes();
            loadSTL(`/download/${currentJobId}?format=stl`, 0xcccccc);
        });

    } catch (e) {
        statusEl.innerText = `Error: ${e.message}`;
        btn.disabled = false;
    }
});

document.getElementById('downloadStl').addEventListener('click', () => {
    if (currentJobId) window.open(`/download/${currentJobId}?format=stl`, '_blank');
});

document.getElementById('downloadObj').addEventListener('click', () => {
    if (currentJobId) window.open(`/download/${currentJobId}?format=obj`, '_blank');
});

document.getElementById('download3mf').addEventListener('click', () => {
    if (currentJobId) window.open(`/download/${currentJobId}?format=3mf`, '_blank');
});
