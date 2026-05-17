import { useEffect, useState } from 'react'
import { Download, Package, FileCode, Layers } from 'lucide-react'
import { getFileUrl } from '../api/client'

interface DownloadPanelProps {
  jobId: string
  files: string[]
}

// ── Format metadata ───────────────────────────────────────────────────────────

interface FormatInfo {
  ext: string
  label: string
  description: string
  icon: React.ReactNode
  colorClass: string
}

const FORMAT_INFO: Record<string, FormatInfo> = {
  stl: {
    ext: 'stl',
    label: 'STL',
    description: 'Universal 3D printing format',
    icon: <Layers size={20} />,
    colorClass: 'text-blue-400',
  },
  obj: {
    ext: 'obj',
    label: 'OBJ',
    description: 'Multi-material with colors',
    icon: <FileCode size={20} />,
    colorClass: 'text-green-400',
  },
  '3mf': {
    ext: '3mf',
    label: '3MF',
    description: 'Modern print-ready format',
    icon: <Package size={20} />,
    colorClass: 'text-purple-400',
  },
}

// ── File size fetcher ─────────────────────────────────────────────────────────

function useFileSize(url: string): string | null {
  const [size, setSize] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    const fetchSize = async () => {
      try {
        const resp = await fetch(url, { method: 'HEAD' })
        const contentLength = resp.headers.get('content-length')
        if (!cancelled && contentLength) {
          const bytes = parseInt(contentLength, 10)
          if (bytes < 1024 * 1024) {
            setSize(`${(bytes / 1024).toFixed(0)} KB`)
          } else {
            setSize(`${(bytes / (1024 * 1024)).toFixed(1)} MB`)
          }
        }
      } catch { /* ignore */ }
    }
    void fetchSize()
    return () => { cancelled = true }
  }, [url])

  return size
}

// ── Single download button ────────────────────────────────────────────────────

interface DownloadButtonProps {
  jobId: string
  filename: string
  info: FormatInfo
}

function DownloadButton({ jobId, filename, info }: DownloadButtonProps) {
  const url = getFileUrl(jobId, filename)
  const size = useFileSize(url)

  return (
    <a
      href={url}
      download={filename}
      className="flex items-center gap-3 bg-gray-800 hover:bg-gray-700 border border-gray-700
                 hover:border-gray-600 rounded-xl px-4 py-3 transition-all duration-150 group"
      aria-label={`Download ${info.label} file`}
    >
      <span className={info.colorClass}>{info.icon}</span>
      <div className="flex-1 min-w-0">
        <div className="flex items-baseline gap-2">
          <span className="font-semibold text-gray-200 group-hover:text-white transition-colors">
            {info.label}
          </span>
          {size && (
            <span className="text-xs text-gray-600">{size}</span>
          )}
        </div>
        <p className="text-xs text-gray-500 truncate">{info.description}</p>
      </div>
      <Download
        size={16}
        className="text-gray-600 group-hover:text-orange-400 transition-colors shrink-0"
      />
    </a>
  )
}

// ── Main component ────────────────────────────────────────────────────────────

export default function DownloadPanel({ jobId, files }: DownloadPanelProps) {
  // Match files to known formats (case-insensitive extension match)
  const matchedFiles = files.flatMap(filename => {
    const ext = filename.split('.').pop()?.toLowerCase() ?? ''
    const info = FORMAT_INFO[ext]
    if (!info) return []
    return [{ filename, info }]
  })

  if (matchedFiles.length === 0) {
    return (
      <div className="card text-center text-gray-500 text-sm py-6">
        No download files available.
      </div>
    )
  }

  return (
    <div className="card space-y-3">
      <h3 className="text-sm font-semibold text-gray-400 uppercase tracking-wider">
        Download Files
      </h3>
      <div className="space-y-2">
        {matchedFiles.map(({ filename, info }) => (
          <DownloadButton
            key={filename}
            jobId={jobId}
            filename={filename}
            info={info}
          />
        ))}
      </div>
    </div>
  )
}
