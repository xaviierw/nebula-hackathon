import { useRef, useState } from 'react'

export function RailFileDropzone({ onFilesSelected, disabled = false }: {
  onFilesSelected: (files: File[]) => void
  disabled?: boolean
}) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [dragging, setDragging] = useState(false)
  return (
    <div>
      <button type="button" disabled={disabled} onClick={() => inputRef.current?.click()}
        onDragOver={(event) => { event.preventDefault(); if (!disabled) setDragging(true) }}
        onDragLeave={() => setDragging(false)}
        onDrop={(event) => {
          event.preventDefault()
          setDragging(false)
          if (!disabled) onFilesSelected(Array.from(event.dataTransfer.files))
        }}
        className={`w-full rounded-lg border-2 border-dashed px-6 py-8 text-center transition focus-visible:outline-2 focus-visible:outline-sky-500 disabled:cursor-not-allowed disabled:opacity-60 ${dragging ? 'border-sky-500 bg-sky-50' : 'border-slate-300 bg-white hover:border-sky-400'}`}>
        <span className="block text-sm font-semibold text-slate-900">{disabled ? 'Analysing this batch…' : dragging ? 'Drop to add to the queue' : 'Drop one or more rail recordings here'}</span>
        <span className="mt-1 block text-xs text-slate-500">or click to browse · CSV files · up to 100 MB each</span>
      </button>
      <input ref={inputRef} type="file" multiple accept=".csv,text/csv" disabled={disabled} className="hidden"
        onChange={(event) => { onFilesSelected(Array.from(event.target.files ?? [])); event.target.value = '' }} />
    </div>
  )
}
