/**
 * The dataset's timestamps are not parseable by Date.parse or any date library.
 *
 * Format is Year-Month-Day-Hour-Minute-Second-Millisecond, hyphen-separated,
 * with ALL zero-padding stripped:
 *
 *   2023-7-5-0-0-0-0      midnight exactly
 *   2023-7-5-0-0-15-5     00:00:15.005   <- "5" means 5 ms, NOT 500 ms
 *   2023-7-5-0-0-3-760    00:00:03.760
 *
 * That last field is the trap. Reading "5" as 500 ms silently corrupts every
 * duration on the page, and the error is invisible unless you check a row that
 * happens to have a small millisecond value. Everything here goes through
 * parseDoorTime so the rule lives in exactly one place.
 */

const FIELD_COUNT = 7

/** Returns null rather than throwing, so one malformed row cannot blank the page. */
export function parseDoorTime(value: string): Date | null {
  const parts = value.split('-')
  if (parts.length !== FIELD_COUNT) return null

  const numbers = parts.map((part) => Number(part))
  if (numbers.some((entry) => !Number.isFinite(entry))) return null

  const [year, month, day, hour, minute, second, millisecond] = numbers
  return new Date(year, month - 1, day, hour, minute, second, millisecond)
}

function pad(value: number, width = 2): string {
  return String(value).padStart(width, '0')
}

/** "00:22:38" - the clock reading a user would look for in a log. */
export function formatClock(value: string): string {
  const date = parseDoorTime(value)
  if (date === null) return value
  return [date.getHours(), date.getMinutes(), date.getSeconds()].map((n) => pad(n)).join(':')
}

/** "00:00:15.005" - with milliseconds, for the secondary detail line. */
export function formatClockMs(value: string): string {
  const date = parseDoorTime(value)
  if (date === null) return value
  return formatClock(value) + '.' + pad(date.getMilliseconds(), 3)
}

/** Length of one cycle, e.g. "3.76 s". */
export function formatDuration(startTime: string, endTime: string): string {
  const start = parseDoorTime(startTime)
  const end = parseDoorTime(endTime)
  if (start === null || end === null) return '—'
  return ((end.getTime() - start.getTime()) / 1000).toFixed(2) + ' s'
}

/** Total span of a recording, e.g. "23m 49s". */
export function formatSpan(startTime: string, endTime: string): string {
  const start = parseDoorTime(startTime)
  const end = parseDoorTime(endTime)
  if (start === null || end === null) return '—'

  const totalSeconds = Math.round((end.getTime() - start.getTime()) / 1000)
  const minutes = Math.floor(totalSeconds / 60)
  const seconds = totalSeconds % 60
  return minutes > 0 ? minutes + 'm ' + seconds + 's' : seconds + 's'
}
