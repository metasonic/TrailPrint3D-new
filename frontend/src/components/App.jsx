import { useState } from 'react';
import Preview3D from './Preview3D';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export default function App() {
  const [file, setFile] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [fileId, setFileId] = useState(null);
  const [modelUrl, setModelUrl] = useState(null);
  const [status, setStatus] = useState('');

  // Settings state
  const [shape, setShape] = useState('circle');
  const [colorMode, setColorMode] = useState(false);
  const [roads, setRoads] = useState(false);

  const handleUpload = async (e) => {
    const selectedFile = e.target.files[0];
    if (!selectedFile) return;

    setFile(selectedFile);
    setUploading(true);
    setStatus('Uploading...');

    const formData = new FormData();
    formData.append('file', selectedFile);

    try {
      const res = await fetch(`${API_URL}/upload`, {
        method: 'POST',
        body: formData,
      });
      const data = await res.json();
      setFileId(data.file_id);
      generatePreview(data.file_id, shape, colorMode, roads);
    } catch (err) {
      setStatus(`Error uploading: ${err.message}`);
      setUploading(false);
    }
  };

  const pollJob = async (jobId, type) => {
    try {
      const res = await fetch(`${API_URL}/job/${jobId}`);
      const data = await res.json();

      if (data.status === 'finished') {
        if (type === 'preview') {
          setModelUrl(`${API_URL}/download/${data.result.split('/').pop()}`);
          setStatus('Preview generated!');
          setUploading(false);
        } else {
          setStatus('Export complete!');
          window.location.href = `${API_URL}/download/${data.result.split('/').pop()}`;
        }
      } else if (data.status === 'failed') {
        setStatus(`Job failed: ${data.error}`);
        setUploading(false);
      } else {
        setTimeout(() => pollJob(jobId, type), 2000);
      }
    } catch (err) {
      setStatus(`Error polling job: ${err.message}`);
      setUploading(false);
    }
  };

  const generatePreview = async (id, currentShape, currentColor, currentRoads) => {
    setStatus('Generating preview...');
    try {
      const res = await fetch(`${API_URL}/preview/${id}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          shape: currentShape || shape,
          colorMode: currentColor !== undefined ? currentColor : colorMode,
          roads: currentRoads !== undefined ? currentRoads : roads
        })
      });
      const data = await res.json();
      pollJob(data.job_id, 'preview');
    } catch (err) {
      setStatus(`Error requesting preview: ${err.message}`);
      setUploading(false);
    }
  };

  const handleExport = async (format) => {
    if (!fileId) return;
    setStatus(`Exporting ${format}...`);
    try {
      const res = await fetch(`${API_URL}/export`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          gpx_filename: `${fileId}.gpx`,
          format,
          shape,
          colorMode,
          roads
        })
      });
      const data = await res.json();
      pollJob(data.job_id, 'export');
    } catch (err) {
      setStatus(`Error requesting export: ${err.message}`);
    }
  };

  return (
    <div className="flex h-full w-full">
      {/* Sidebar Panel */}
      <div className="w-80 bg-white border-r flex flex-col p-4 overflow-y-auto">
        <div className="mb-6">
          <h2 className="text-lg font-bold mb-2">1. Upload Track</h2>
          <label className="block w-full cursor-pointer bg-blue-50 text-blue-700 border border-blue-200 p-4 rounded text-center hover:bg-blue-100 transition">
            {uploading ? 'Processing...' : (file ? file.name : 'Select GPX File')}
            <input type="file" className="hidden" accept=".gpx" onChange={handleUpload} disabled={uploading} />
          </label>
        </div>

        <div className={`mb-6 ${!fileId ? 'opacity-50 pointer-events-none' : ''}`}>
          <h2 className="text-lg font-bold mb-2">2. Map Settings</h2>
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700">Shape</label>
              <select className="mt-1 block w-full rounded-md border-gray-300 shadow-sm p-2 border" value={shape} onChange={e => setShape(e.target.value)}>
                <option value="circle">Circle</option>
                <option value="square">Square</option>
                <option value="hexagon">Hexagon</option>
              </select>
            </div>

            <label className="flex items-center">
              <input type="checkbox" className="rounded border-gray-300 text-blue-600 shadow-sm mr-2" checked={colorMode} onChange={e => setColorMode(e.target.checked)} />
              <span className="text-sm text-gray-700">Single-color Print Mode</span>
            </label>

            <label className="flex items-center">
              <input type="checkbox" className="rounded border-gray-300 text-blue-600 shadow-sm mr-2" checked={roads} onChange={e => setRoads(e.target.checked)} />
              <span className="text-sm text-gray-700">Include Roads</span>
            </label>

            <button className="w-full bg-gray-200 p-2 rounded text-sm hover:bg-gray-300 transition" onClick={() => fileId && generatePreview(fileId, shape, colorMode, roads)}>
              Update Preview
            </button>
          </div>
        </div>

        <div className={`mt-auto ${!fileId ? 'opacity-50 pointer-events-none' : ''}`}>
          <h2 className="text-lg font-bold mb-2">3. Export</h2>
          <div className="grid grid-cols-3 gap-2">
            <button onClick={() => handleExport('stl')} className="bg-blue-600 text-white p-2 rounded hover:bg-blue-700 text-sm font-medium">STL</button>
            <button onClick={() => handleExport('obj')} className="bg-blue-600 text-white p-2 rounded hover:bg-blue-700 text-sm font-medium">OBJ</button>
            <button onClick={() => handleExport('3mf')} className="bg-blue-600 text-white p-2 rounded hover:bg-blue-700 text-sm font-medium">3MF</button>
          </div>
        </div>
      </div>

      {/* 3D Viewport */}
      <div className="flex-grow relative">
        <Preview3D modelUrl={modelUrl} />

        {/* Status Bar */}
        <div className="absolute bottom-4 left-4 right-4 flex justify-between pointer-events-none">
          <div className={`bg-gray-900/80 text-white px-4 py-2 rounded shadow transition-opacity ${status ? 'opacity-100' : 'opacity-0'}`}>
            {status}
          </div>
        </div>
      </div>
    </div>
  );
}
