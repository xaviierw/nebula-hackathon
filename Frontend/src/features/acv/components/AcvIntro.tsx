/**
 * Explains the ACV task using the problem statement's defined signal and output.
 */
export function AcvIntro() {
  return (
    <section className="rounded-lg border border-slate-200 bg-white p-5">
      <h2 className="text-sm font-semibold text-slate-900">How it works</h2>

      <p className="mt-3 text-sm leading-relaxed text-slate-600">
        A refrigerant leak makes an air-conditioning unit less able to remove heat from the
        cabin. The system answers through its temperatures and controls, so cabin temperature,
        ambient temperature, and control-mode telemetry together show how well each car is
        cooling.
      </p>

      <p className="mt-3 text-sm leading-relaxed text-slate-600">
        Upload one train-car export and this compares the cars under the conditions recorded in
        that file. It ranks every car from most to least likely to have a refrigerant leak, using
        the exact car identifiers from the source columns.
      </p>

      <p className="mt-4 border-t border-slate-100 pt-3 text-xs leading-relaxed text-slate-500">
        ACV is a fault-localisation task, not a guaranteed diagnosis. The result is saved as
        <span className="font-medium text-slate-700"> acv_predictions.csv</span> with the source
        file name and the complete ranked-car order for submission.
      </p>
    </section>
  )
}
