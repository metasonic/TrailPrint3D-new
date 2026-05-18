import { useState, useRef } from 'react';
import Preview3D from './Preview3D';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

// Simple SVG Spinner
const Spinner = () => (
  <svg className="animate-spin -ml-1 mr-3 h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
  </svg>
);

export default function App() {
  const [file, setFile] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [fileId, setFileId] = useState(null);
  const [modelUrl, setModelUrl] = useState(null);
  const [status, setStatus] = useState('');
  const [isDragActive, setIsDragActive] = useState(false);

  // Settings state
  const [shape, setShape] = useState('circle');
  const [colorMode, setColorMode] = useState(false);
  const [roads, setRoads] = useState(false);

  const fileInputRef = useRef(null);

  const processFile = async (selectedFile) => {
    if (!selectedFile) return;
    if (!selectedFile.name.endsWith('.gpx')) {
      setStatus('Error: Only .gpx files are allowed');
      return;
    }

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
      if (!res.ok) throw new Error(await res.text());

      const data = await res.json();
      setFileId(data.file_id);
      generatePreview(data.file_id, shape, colorMode, roads);
    } catch (err) {
      setStatus(`Error uploading: ${err.message}`);
      setUploading(false);
    }
  };

  const handleUpload = (e) => {
    processFile(e.target.files[0]);
  };

  const handleDragOver = (e) => {
    e.preventDefault();
    setIsDragActive(true);
  };

  const handleDragLeave = (e) => {
    e.preventDefault();
    setIsDragActive(false);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setIsDragActive(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      processFile(e.dataTransfer.files[0]);
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
          // Auto clear success message after 3s
          setTimeout(() => setStatus(''), 3000);
        } else {
          setStatus('Export complete!');
          window.location.href = `${API_URL}/download/${data.result.split('/').pop()}`;
          setUploading(false);
          setTimeout(() => setStatus(''), 3000);
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
    setUploading(true);
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
    setUploading(true);
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
      setUploading(false);
    }
  };

  return (
    <div className="flex h-full w-full">
      {/* Sidebar Panel */}
      <div className="w-80 bg-white border-r flex flex-col p-4 overflow-y-auto">
        <div className="mb-6">
          <h2 className="text-lg font-bold mb-2">1. Upload Track</h2>
          <div
            className={`border-2 border-dashed rounded-lg p-6 text-center cursor-pointer transition-colors ${
              isDragActive ? 'border-blue-500 bg-blue-50' : 'border-gray-300 hover:border-blue-400 hover:bg-gray-50'
            }`}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
            onClick={() => !uploading && fileInputRef.current?.click()}
          >
            <input
              type="file"
              className="hidden"
              accept=".gpx"
              onChange={handleUpload}
              disabled={uploading}
              ref={fileInputRef}
            />
            {file ? (
              <div className="text-blue-600 font-medium break-all">{file.name}</div>
            ) : (
              <div className="text-gray-500">
                <p className="font-medium">Click or drag GPX here</p>
                <p className="text-sm mt-1">Maximum size: 50MB</p>
              </div>
            )}
          </div>
        </div>

        <div className={`mb-6 ${!fileId || uploading ? 'opacity-50 pointer-events-none' : ''}`}>
          <h2 className="text-lg font-bold mb-2">2. Map Settings</h2>
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700">Shape</label>
              <select className="mt-1 block w-full rounded-md border-gray-300 shadow-sm p-2 border focus:border-blue-500 focus:ring-blue-500" value={shape} onChange={e => setShape(e.target.value)}>
                <option value="circle">Circle</option>
                <option value="square">Square</option>
                <option value="hexagon">Hexagon</option>
              </select>
            </div>

            <label className="flex items-center cursor-pointer">
              <input type="checkbox" className="rounded border-gray-300 text-blue-600 shadow-sm mr-2 focus:ring-blue-500" checked={colorMode} onChange={e => setColorMode(e.target.checked)} />
              <span className="text-sm text-gray-700">Single-color Print Mode</span>
            </label>

            <label className="flex items-center cursor-pointer">
              <input type="checkbox" className="rounded border-gray-300 text-blue-600 shadow-sm mr-2 focus:ring-blue-500" checked={roads} onChange={e => setRoads(e.target.checked)} />
              <span className="text-sm text-gray-700">Include Roads</span>
            </label>

            <button className="w-full bg-blue-100 text-blue-700 font-medium p-2 rounded text-sm hover:bg-blue-200 transition" onClick={() => fileId && generatePreview(fileId, shape, colorMode, roads)}>
              Update Preview
            </button>
          </div>
        </div>

        <div className={`mt-auto ${!fileId || uploading ? 'opacity-50 pointer-events-none' : ''}`}>
          <h2 className="text-lg font-bold mb-2">3. Export</h2>
          <div className="grid grid-cols-3 gap-2">
            <button onClick={() => handleExport('stl')} className="bg-blue-600 text-white p-2 rounded hover:bg-blue-700 text-sm font-medium shadow-sm">STL</button>
            <button onClick={() => handleExport('obj')} className="bg-blue-600 text-white p-2 rounded hover:bg-blue-700 text-sm font-medium shadow-sm">OBJ</button>
            <button onClick={() => handleExport('3mf')} className="bg-blue-600 text-white p-2 rounded hover:bg-blue-700 text-sm font-medium shadow-sm">3MF</button>
          </div>
        </div>
      </div>

      {/* 3D Viewport */}
      <div className="flex-grow relative">
        <Preview3D modelUrl={modelUrl} />

        {/* Status Bar */}
        <div className="absolute bottom-4 left-4 right-4 flex justify-between pointer-events-none">
          <div className={`bg-gray-900/90 text-white px-4 py-3 rounded-lg shadow-lg flex items-center transition-opacity duration-300 ${status ? 'opacity-100' : 'opacity-0'}`}>
            {uploading && <Spinner />}
            <span className="font-medium">{status}</span>
          </div>
        </div>
      </div>
    </div>
  );
}
