/**
 * Explains the subsystem before the user uploads anything.
 *
 * The claims here are deliberately bounded by Backend/Door/audit/dataset_limitations.md:
 *
 *   - no door or car is named, because no identifier column exists in the data
 *   - nothing claims early or slight wear detection: the mildest fault in
 *     training sits 19 sigma (Open) / 54 sigma (Close) from normal, so this
 *     finds obvious resistance, not the beginnings of it
 *   - no accuracy headline. The model scores 1.0 in cross-validation, but the
 *     normal cycles vary by ~1% across 40 repetitions, which the audit calls
 *     "consistent with simulated or fault-injected data rather than recorded
 *     operation". Printing "100% accurate" would be the biggest overclaim
 *     available to this project.
 */
export function DoorIntro() {
  return (
    <section className="rounded-lg border border-slate-200 bg-white p-5">
      <h2 className="text-sm font-semibold text-slate-900">How it works</h2>

      <p className="mt-3 text-sm leading-relaxed text-slate-600">
        Grit in the slide rail, a rubber seal catching, or a warped door leaf all push back
        against the motor. The motor answers by drawing more current — so current is a direct
        readout of how hard the door is having to work.
      </p>

      <p className="mt-3 text-sm leading-relaxed text-slate-600">
        Upload a recording and this finds every open and close cycle inside it, then measures
        the current through the <span className="font-medium text-slate-800">middle of each
        stroke</span> — past the startup surge, before the braking — and compares it against
        what a healthy door of that type needs.
      </p>

      <p className="mt-4 border-t border-slate-100 pt-3 text-xs leading-relaxed text-slate-500">
        Flags cycles where the motor drew abnormally high current, validated against 110
        labelled training cycles. Results are identified by timestamp: the recordings carry no
        door, car or train number.
      </p>
    </section>
  )
}
