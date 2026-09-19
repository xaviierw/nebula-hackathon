import { useRef, useState } from 'react'

const MAX_ACV_FILE_BYTES = 25 * 1024 * 1024

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

interface AcvFileDropzoneProps {
  onFileSelected: (file: File) => void
  selectedFile: File | null
  disabled?: boolean
}

export function AcvFileDropzone({ onFileSelected, selectedFile, disabled = false }: AcvFileDropzoneProps) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [isDraggingOver, setIsDraggingOver] = useState(false)
  const [rejection, setRejection] = useState<string | null>(null)

  function accept(file: File | undefined) {
    if (!file) return

    if (!['csv', 'xlsx', 'xls'].includes(file.name.toLowerCase().split('.').pop() ?? '')) {
      setRejection(`"${file.name}" is not a supported ACV file. Use CSV or Excel.`)
      return
    }
    if (file.size === 0) {
      setRejection(`"${file.name}" is empty.`)
      return
    }
    if (file.size > MAX_ACV_FILE_BYTES) {
      setRejection(`"${file.name}" exceeds the 25 MiB upload limit.`)
      return
    }
    setRejection(null)
    onFileSelected(file)
  }

  return (
    <div>
      <button
        type="button"
        disabled={disabled}
        onClick={() => inputRef.current?.click()}
        onDragOver={(event) => { event.preventDefault(); if (!disabled) setIsDraggingOver(true) }}
        onDragLeave={() => setIsDraggingOver(false)}
        onDrop={(event) => { event.preventDefault(); setIsDraggingOver(false); if (!disabled) accept(event.dataTransfer.files[0]) }}
        className={[
          'w-full rounded-lg border-2 border-dashed px-6 py-10 text-center transition',
          'focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-500',
          disabled ? 'cursor-not-allowed opacity-60' : 'cursor-pointer',
          isDraggingOver ? 'border-sky-500 bg-sky-50' : 'border-slate-300 bg-white hover:border-sky-400 hover:bg-slate-50',
        ].join(' ')}
      >
        <p className="text-sm font-medium text-slate-900">{isDraggingOver ? 'Drop to upload' : 'Drop an ACV export here'}</p>
        <p className="mt-1 text-xs text-slate-500">or click to browse one CSV or Excel file · up to 25 MiB</p>
        <input ref={inputRef} type="file" accept=".csv,.xlsx,.xls,text/csv" className="sr-only" onChange={(event) => { accept(event.target.files?.[0]); event.target.value = '' }} />
      </button>
      {rejection !== null && <p role="alert" className="mt-3 text-sm text-red-700">{rejection}</p>}
      {selectedFile !== null && rejection === null && (
        <p className="mt-3 text-sm text-slate-600"><span className="font-medium text-slate-900">{selectedFile.name}</span><span className="text-slate-400"> · {formatSize(selectedFile.size)}</span></p>
      )}
    </div>
  )
}
