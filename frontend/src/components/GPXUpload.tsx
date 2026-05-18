import React, { useCallback, useRef, useState } from 'react'
import { Upload, MapPin, FileText, AlertCircle } from 'lucide-react'

interface GPXUploadProps {
  onUpload: (file: File) => void
  isUploading: boolean
  disabled?: boolean
}

const ACCEPTED_TYPES = ['.gpx', '.igc']
const ACCEPTED_MIME = ['application/gpx+xml', 'application/xml', 'text/xml', 'text/plain']
const MAX_SIZE_MB = 50

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

function isValidFile(file: File): string | null {
  const ext = file.name.split('.').pop()?.toLowerCase() ?? ''
  if (!['gpx', 'igc'].includes(ext)) {
    return `Unsupported file type ".${ext}". Please upload a .gpx or .igc file.`
  }
  if (file.size > MAX_SIZE_MB * 1024 * 1024) {
    return `File too large (${formatBytes(file.size)}). Maximum size is ${MAX_SIZE_MB} MB.`
  }
  return null
}

export default function GPXUpload({ onUpload, isUploading, disabled = false }: GPXUploadProps) {
  const [isDragOver, setIsDragOver] = useState(false)
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [validationError, setValidationError] = useState<string | null>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  const handleFile = useCallback(
    (file: File) => {
      const err = isValidFile(file)
      if (err) {
        setValidationError(err)
        setSelectedFile(null)
        return
      }
      setValidationError(null)
      setSelectedFile(file)
      onUpload(file)
    },
    [onUpload],
  )

  const onDragOver = useCallback((e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault()
    if (!disabled && !isUploading) setIsDragOver(true)
  }, [disabled, isUploading])

  const onDragLeave = useCallback((e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault()
    setIsDragOver(false)
  }, [])

  const onDrop = useCallback(
    (e: React.DragEvent<HTMLDivElement>) => {
      e.preventDefault()
      setIsDragOver(false)
      if (disabled || isUploading) return
      const file = e.dataTransfer.files[0]
      if (file) handleFile(file)
    },
    [disabled, isUploading, handleFile],
  )

  const onInputChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0]
      if (file) handleFile(file)
      // Reset input so same file can be re-selected
      e.target.value = ''
    },
    [handleFile],
  )

  const onClick = useCallback(() => {
    if (!disabled && !isUploading) inputRef.current?.click()
  }, [disabled, isUploading])

  const isInteractive = !disabled && !isUploading

  return (
    <div className="flex flex-col items-center justify-center min-h-[60vh] px-4">
      {/* Logo / hero area */}
      <div className="mb-8 text-center">
        <div className="flex items-center justify-center gap-3 mb-3">
          <MapPin className="w-10 h-10 text-orange-500" strokeWidth={1.5} />
          <h1 className="text-3xl font-bold text-white tracking-tight">TrailPrint3D</h1>
        </div>
        <p className="text-gray-400 text-lg">
          Convert your GPS trails into stunning 3D-printable topographic maps
        </p>
      </div>

      {/* Drop zone */}
      <div
        role="button"
        tabIndex={isInteractive ? 0 : -1}
        aria-label="Upload GPX or IGC file"
        aria-busy={isUploading}
        aria-disabled={!isInteractive}
        className={[
          'relative w-full max-w-lg rounded-2xl border-2 border-dashed p-10',
          'flex flex-col items-center justify-center gap-4 cursor-pointer',
          'transition-all duration-200 outline-none',
          isDragOver
            ? 'border-orange-500 bg-orange-500/10 scale-[1.01]'
            : 'border-gray-700 bg-gray-900 hover:border-gray-500 hover:bg-gray-800/60',
          !isInteractive ? 'opacity-60 cursor-not-allowed' : '',
        ].join(' ')}
        onDragOver={onDragOver}
        onDragLeave={onDragLeave}
        onDrop={onDrop}
        onClick={onClick}
        onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onClick() } }}
      >
        <input
          ref={inputRef}
          type="file"
          accept={ACCEPTED_TYPES.join(',')}
          className="hidden"
          onChange={onInputChange}
          disabled={!isInteractive}
          aria-hidden="true"
          // tell browsers which mime types we also accept
          {...(ACCEPTED_MIME.length ? {} : {})}
        />

        {/* Icon */}
        {isUploading ? (
          <div className="flex flex-col items-center gap-3">
            <div className="w-14 h-14 rounded-full border-4 border-orange-500/30 border-t-orange-500 animate-spin" />
            <p className="text-gray-300 font-medium">Uploading…</p>
          </div>
        ) : (
          <>
            <div
              className={[
                'w-16 h-16 rounded-full flex items-center justify-center transition-colors',
                isDragOver ? 'bg-orange-500/20' : 'bg-gray-800',
              ].join(' ')}
            >
              <Upload
                className={isDragOver ? 'text-orange-400' : 'text-gray-400'}
                size={28}
                strokeWidth={1.5}
              />
            </div>

            <div className="text-center">
              <p className="text-lg font-semibold text-gray-200">
                {isDragOver ? 'Release to upload' : 'Drop your GPX file here'}
              </p>
              <p className="text-sm text-gray-500 mt-1">
                or <span className="text-orange-400 underline underline-offset-2">click to browse</span>
              </p>
              <p className="text-xs text-gray-600 mt-3">
                Supports .gpx and .igc files · max {MAX_SIZE_MB} MB
              </p>
            </div>
          </>
        )}

        {/* Selected file info */}
        {selectedFile && !isUploading && (
          <div className="mt-2 flex items-center gap-2 text-sm text-gray-400 bg-gray-800 rounded-lg px-3 py-2 w-full justify-center">
            <FileText size={14} className="text-orange-400 shrink-0" />
            <span className="truncate font-medium text-gray-300">{selectedFile.name}</span>
            <span className="shrink-0 text-gray-500">{formatBytes(selectedFile.size)}</span>
          </div>
        )}
      </div>

      {/* Validation error */}
      {validationError && (
        <div role="alert" className="mt-4 flex items-start gap-2 text-sm text-red-400 bg-red-900/20 border border-red-800 rounded-lg px-4 py-3 max-w-lg w-full">
          <AlertCircle size={16} className="shrink-0 mt-0.5" />
          <span>{validationError}</span>
        </div>
      )}

      {/* Feature pills */}
      <div className="mt-8 flex flex-wrap gap-2 justify-center max-w-lg">
        {['STL / OBJ / 3MF Export', '90+ Settings', 'Live 3D Preview', 'Terrain + OSM Data'].map(
          (label) => (
            <span
              key={label}
              className="text-xs text-gray-500 bg-gray-900 border border-gray-800 rounded-full px-3 py-1"
            >
              {label}
            </span>
          ),
        )}
      </div>
    </div>
  )
}
