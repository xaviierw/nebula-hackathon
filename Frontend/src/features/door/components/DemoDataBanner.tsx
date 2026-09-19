/**
 * Marks the results as canned.
 *
 * This is not decoration. The fixture is real pipeline output, so the results
 * table looks entirely convincing - which is exactly the risk. Without this
 * banner a screen recording of placeholder data could end up submitted as a
 * demo of a working model. Delete it in the same commit that deletes the
 * fixture, and not before.
 */
export function DemoDataBanner() {
  return (
    <div
      role="status"
      className="flex items-start gap-3 rounded-lg border border-amber-300 bg-amber-50 px-4 py-3"
    >
      <span aria-hidden="true" className="text-base leading-none text-amber-600">
        ⚠
      </span>
      <p className="text-sm leading-relaxed text-amber-900">
        <span className="font-semibold">Sample results — the model is not connected yet.</span>{' '}
        These are stored figures from an earlier run, shown to demonstrate the layout. Uploading
        a file does not analyse it.
      </p>
    </div>
  )
}
