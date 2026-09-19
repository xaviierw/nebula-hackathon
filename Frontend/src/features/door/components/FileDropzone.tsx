import { useRef, useState } from 'react'

/**
 * Drag-and-drop with a real click-to-browse fallback.
 *
 * The visible control is a <button> wrapping a visually hidden <input type="file">,
 * so the whole thing is reachable by Tab and activates on Enter or Space. Making
 * the dropzone a bare <div onClick> would look identical and be unusable without
 * a mouse.
 *
 * Validation here is only the extension - the real check (does this file have the
 * 17 expected columns?) belongs to the backend, which already produces a readable
 * message for it.
 */

function formatSize(bytes: number): string {
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(0) + ' KB'
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
}

interface FileDropzoneProps {
  onFileSelected: (file: File) => void
  selectedFile: File | null
  disabled?: boolean
}

export function FileDropzone({ onFileSelected, selectedFile, disabled = false }: FileDropzoneProps) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [isDraggingOver, setIsDraggingOver] = useState(false)
  const [rejection, setRejection] = useState<string | null>(null)

  function accept(file: File | undefined) {
    if (!file) return

    if (!file.name.toLowerCase().endsWith('.csv')) {
      setRejection(`“${file.name}” is not a CSV file. Door recordings are saved as .csv.`)
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
        onDragOver={(event) => {
          event.preventDefault()
          if (!disabled) setIsDraggingOver(true)
        }}
        onDragLeave={() => setIsDraggingOver(false)}
        onDrop={(event) => {
          event.preventDefault()
          setIsDraggingOver(false)
          if (!disabled) accept(event.dataTransfer.files[0])
        }}
        className={[
          'w-full rounded-lg border-2 border-dashed px-6 py-10 text-center transition',
          'focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-500',
          disabled ? 'cursor-not-allowed opacity-60' : 'cursor-pointer',
          isDraggingOver
            ? 'border-sky-500 bg-sky-50'
            : 'border-slate-300 bg-white hover:border-sky-400 hover:bg-slate-50',
        ].join(' ')}
      >
        <p className="text-sm font-medium text-slate-900">
          {isDraggingOver ? 'Drop to upload' : 'Drop a door recording here'}
        </p>
        <p className="mt-1 text-xs text-slate-500">or click to browse — CSV files only</p>

        <input
          ref={inputRef}
          type="file"
          accept=".csv,text/csv"
          className="sr-only"
          onChange={(event) => {
            accept(event.target.files?.[0])
            // Reset so re-picking the same file fires change again.
            event.target.value = ''
          }}
        />
      </button>

      {rejection !== null && (
        <p role="alert" className="mt-3 text-sm text-red-700">
          {rejection}
        </p>
      )}

      {selectedFile !== null && rejection === null && (
        <p className="mt-3 text-sm text-slate-600">
          <span className="font-medium text-slate-900">{selectedFile.name}</span>
          <span className="text-slate-400"> · {formatSize(selectedFile.size)}</span>
        </p>
      )}
    </div>
  )
}
