import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { ShmPage } from '../src/pages/subsystems/ShmPage'
import { buildShmCsv, predictShm } from '../src/features/shm/prediction'
import { apiFetch } from '../src/api/client'

vi.mock('../src/api/client', () => ({ apiFetch: vi.fn(), SessionError: class extends Error {} }))
const result = { prediction: 0.12345678901234566, observations: 581120, weighted_cycle_count: 100,
  model_id: 'artifact', model_version: 'shm-1:artifact', interval: null, warnings: [] }
const file = (name = 'original.csv') => new File(['0\n2\n'], name, { type: 'text/csv' })
const response = (payload = result, status = 200) => new Response(JSON.stringify(payload), { status })
const mockFetch = vi.mocked(apiFetch)
let exported: Blob | undefined
beforeEach(() => {
  mockFetch.mockResolvedValue(response())
  exported = undefined
  vi.stubGlobal('URL', Object.assign(URL, { createObjectURL: vi.fn((blob: Blob) => { exported = blob; return 'blob:test' }), revokeObjectURL: vi.fn() }))
  vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})
})
afterEach(() => { cleanup(); vi.restoreAllMocks() })

function mount() {
  render(<MemoryRouter><ShmPage /></MemoryRouter>)
  return screen.getByLabelText('Choose stress CSV files')
}
function choose(input: HTMLElement, files: File[]) { fireEvent.change(input, { target: { files } }) }
function download() { return screen.getByRole('button', { name: 'Download shm_predictions.csv' }) as HTMLButtonElement }

describe('SHM upload and CSV', () => {
  it('associates the current filename with cached content and exports full precision', async () => {
    const name = 'original, "name".csv'
    mockFetch.mockResolvedValue(response({ ...result, file_id: 'stale.csv' } as typeof result))
    const prediction = await predictShm(file(name))
    expect(prediction.file_id).toBe(name)
    expect(buildShmCsv([prediction])).toBe('file_id,prediction\r\n"original, ""name"".csv",' + String(result.prediction) + '\r\n')
    expect(() => buildShmCsv([prediction, prediction])).toThrow()
    expect(() => buildShmCsv([prediction, { ...prediction, file_id: 'b.csv', model_version: 'shm-2:artifact' }])).toThrow()
    for (const number of [NaN, Infinity, 0, -1]) expect(() => buildShmCsv([{ ...prediction, prediction: number }])).toThrow()
  })

  it('uploads sequentially, tracks progress and downloads only the complete selection', async () => {
    const input = mount()
    let finish!: (value: Response) => void
    mockFetch.mockReturnValueOnce(new Promise(resolve => { finish = resolve }))
    choose(input, [file('a.csv'), file('b.csv')])
    expect(download().disabled).toBe(true)
    fireEvent.click(screen.getByRole('button', { name: 'Estimate fatigue damage' }))
    expect(mockFetch).toHaveBeenCalledTimes(1)
    expect(screen.getByRole('progressbar')).toBeTruthy()
    finish(response())
    await waitFor(() => expect(download().disabled).toBe(false))
    expect(mockFetch).toHaveBeenCalledTimes(2)
    fireEvent.click(download())
    expect(exported).toBeInstanceOf(Blob)
    choose(input, [file('replacement.csv')])
    expect(download().disabled).toBe(true)
  })

  it('keeps per-file errors and prevents partial or mixed-version downloads', async () => {
    const input = mount()
    mockFetch.mockResolvedValueOnce(response()).mockResolvedValueOnce(new Response(JSON.stringify({ message: 'Expected 581,120 observations' }), { status: 400 }))
    choose(input, [file('ok.csv'), file('bad.csv')])
    fireEvent.click(screen.getByRole('button', { name: 'Estimate fatigue damage' }))
    await screen.findByText('Expected 581,120 observations')
    expect(download().disabled).toBe(true)
    mockFetch.mockResolvedValueOnce(response()).mockResolvedValueOnce(response({ ...result, model_version: 'shm-2:artifact' }))
    fireEvent.click(screen.getByRole('button', { name: 'Run again' }))
    await screen.findByText(/model changed during this batch/)
    expect(download().disabled).toBe(true)
  })

  it('supports drag/drop and rejects duplicate filenames', () => {
    const input = mount()
    fireEvent.drop(screen.getByRole('region', { name: 'Upload stress recordings' }), { dataTransfer: { files: [file('dropped.csv')] } })
    expect(screen.getByRole('rowheader', { name: 'dropped.csv' })).toBeTruthy()
    choose(input, [file(), file()])
    expect(screen.getByRole('alert').textContent).toContain('same filename')
    expect(screen.queryByRole('button', { name: 'Download shm_predictions.csv' })).toBeNull()
  })

  it('shows unavailable-backend and shared service errors', async () => {
    mockFetch.mockRejectedValueOnce(new TypeError('Failed to fetch'))
    await expect(predictShm(file())).rejects.toThrow('Cannot reach')
    mockFetch.mockResolvedValueOnce(new Response(JSON.stringify({ message: 'SHM unavailable' }), { status: 503 }))
    await expect(predictShm(file())).rejects.toThrow('SHM unavailable')
  })
})
