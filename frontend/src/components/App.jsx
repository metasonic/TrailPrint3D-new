import { useState, useRef } from 'react';
import Preview3D from './Preview3D';

// Use a relative path so Nginx can reverse proxy it.
// If running dev server locally without Nginx, it falls back to localhost.
const API_URL = import.meta.env.DEV ? 'http://localhost:8000' : '/api';

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
      setTimeout(() => setStatus(''), 4000);
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

  const clearFile = () => {
    setFile(null);
    setFileId(null);
    setModelUrl(null);
    if (fileInputRef.current) {
        fileInputRef.current.value = "";
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
      <div className="w-80 bg-white shadow-xl z-20 flex flex-col p-5 overflow-y-auto">
        <div className="mb-8">
          <h2 className="text-sm font-bold text-gray-400 uppercase tracking-wider mb-3">1. Upload Track</h2>
          <div
            className={`relative border-2 border-dashed rounded-xl p-6 text-center cursor-pointer transition-all duration-200 ${
              isDragActive ? 'border-indigo-500 bg-indigo-50 shadow-inner' : 'border-gray-200 hover:border-indigo-400 hover:bg-gray-50'
            }`}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
            onClick={() => !uploading && !file && fileInputRef.current?.click()}
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
              <div className="flex flex-col items-center">
                 <svg xmlns="http://www.w3.org/2000/svg" className="h-8 w-8 text-indigo-500 mb-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                 </svg>
                <div className="text-gray-800 font-medium break-all text-sm mb-3">{file.name}</div>
                <button
                  onClick={(e) => { e.stopPropagation(); clearFile(); }}
                  disabled={uploading}
                  className="px-3 py-1 text-xs font-semibold text-red-600 bg-red-50 rounded-full hover:bg-red-100 transition disabled:opacity-50"
                >
                  Clear File
                </button>
              </div>
            ) : (
              <div className="text-gray-500">
                <svg xmlns="http://www.w3.org/2000/svg" className="h-8 w-8 mx-auto text-gray-400 mb-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                </svg>
                <p className="font-medium text-sm text-gray-600">Click or drag GPX here</p>
                <p className="text-xs text-gray-400 mt-1">Maximum size: 50MB</p>
              </div>
            )}
          </div>
        </div>

        <div className={`mb-8 transition-opacity duration-300 ${!fileId || uploading ? 'opacity-40 pointer-events-none' : 'opacity-100'}`}>
          <h2 className="text-sm font-bold text-gray-400 uppercase tracking-wider mb-3">2. Map Settings</h2>
          <div className="bg-gray-50 p-4 rounded-xl border border-gray-100 space-y-4 shadow-sm">
            <div>
              <label className="block text-xs font-semibold text-gray-600 mb-1">Shape</label>
              <select className="block w-full rounded-md border-gray-200 bg-white shadow-sm py-2 px-3 text-sm focus:border-indigo-500 focus:ring-indigo-500 transition" value={shape} onChange={e => setShape(e.target.value)}>
                <option value="circle">Circle</option>
                <option value="square">Square</option>
                <option value="hexagon">Hexagon</option>
              </select>
            </div>

            <div className="pt-2">
                <label className="flex items-center cursor-pointer group">
                <input type="checkbox" className="rounded text-indigo-600 border-gray-300 shadow-sm focus:ring-indigo-500 mr-3" checked={colorMode} onChange={e => setColorMode(e.target.checked)} />
                <span className="text-sm text-gray-700 group-hover:text-indigo-700 transition">Single-color Print Mode</span>
                </label>
            </div>

            <div>
                <label className="flex items-center cursor-pointer group">
                <input type="checkbox" className="rounded text-indigo-600 border-gray-300 shadow-sm focus:ring-indigo-500 mr-3" checked={roads} onChange={e => setRoads(e.target.checked)} />
                <span className="text-sm text-gray-700 group-hover:text-indigo-700 transition">Include Roads</span>
                </label>
            </div>

            <div className="pt-2">
                <button className="w-full bg-indigo-50 text-indigo-700 font-semibold py-2 px-4 rounded-lg text-sm border border-indigo-100 hover:bg-indigo-100 hover:border-indigo-200 transition" onClick={() => fileId && generatePreview(fileId, shape, colorMode, roads)}>
                Update Preview
                </button>
            </div>
          </div>
        </div>

        <div className={`mt-auto transition-opacity duration-300 ${!fileId || uploading ? 'opacity-40 pointer-events-none' : 'opacity-100'}`}>
          <h2 className="text-sm font-bold text-gray-400 uppercase tracking-wider mb-3">3. Export</h2>
          <div className="grid grid-cols-3 gap-2">
            <button onClick={() => handleExport('stl')} className="bg-indigo-600 text-white py-2 rounded-lg hover:bg-indigo-700 text-sm font-bold shadow-md hover:shadow-lg transition">STL</button>
            <button onClick={() => handleExport('obj')} className="bg-indigo-600 text-white py-2 rounded-lg hover:bg-indigo-700 text-sm font-bold shadow-md hover:shadow-lg transition">OBJ</button>
            <button onClick={() => handleExport('3mf')} className="bg-indigo-600 text-white py-2 rounded-lg hover:bg-indigo-700 text-sm font-bold shadow-md hover:shadow-lg transition">3MF</button>
          </div>
        </div>
      </div>

      {/* 3D Viewport */}
      <div className="flex-grow relative z-0">
        <Preview3D modelUrl={modelUrl} />

        {/* Status Bar */}
        <div className="absolute bottom-6 left-6 right-6 flex justify-center pointer-events-none">
          <div className={`bg-gray-900/90 backdrop-blur text-white px-5 py-3 rounded-full shadow-2xl flex items-center transform transition-all duration-300 ${status ? 'translate-y-0 opacity-100' : 'translate-y-4 opacity-0'}`}>
            {uploading && <Spinner />}
            <span className="font-medium tracking-wide">{status}</span>
          </div>
        </div>
      </div>
    </div>
  );
}
