import { useCallback, useEffect, useRef, useState } from 'react'
import type { SetStateAction } from 'react'

import type { RailWorkspace } from './types'
import { emptyWorkspace, restoreWorkspace, STORAGE_KEY } from './workspace'

function load() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    return { workspace: raw ? restoreWorkspace(raw) : emptyWorkspace(), error: null, writable: true }
  } catch {
    return {
      workspace: emptyWorkspace(), writable: false,
      error: 'Saved records could not be read. Existing browser data has been left intact. New work is temporary; download reports before leaving this page.',
    }
  }
}

export function useRailWorkspace() {
  const [initial] = useState(load)
  const [workspace, setRenderedWorkspace] = useState<RailWorkspace>(initial.workspace)
  const current = useRef(initial.workspace)
  const [storageError, setStorageError] = useState<string | null>(initial.error)
  const conflicted = useRef(false)

  const setWorkspace = useCallback((update: SetStateAction<RailWorkspace>) => {
    const next = typeof update === 'function' ? update(current.current) : update
    current.current = next
    setRenderedWorkspace(next)
    if (!initial.writable || conflicted.current) return
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(next))
      setStorageError(null)
    } catch {
      setStorageError('Browser storage is unavailable or full. Recent changes are only in this tab; download reports before leaving.')
    }
  }, [initial.writable])

  useEffect(() => {
    function onStorage(event: StorageEvent) {
      if (event.key !== STORAGE_KEY && event.key !== null) return
      conflicted.current = true
      setStorageError('Records changed in another tab. Saving here is paused to avoid overwriting them. Download any unsaved reports, then reload this tab.')
    }
    window.addEventListener('storage', onStorage)
    return () => window.removeEventListener('storage', onStorage)
  }, [])

  return { workspace, setWorkspace, storageError }
}
