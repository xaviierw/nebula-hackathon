import type { RailEvidence, VibrationMeasurements } from '../types'

const MEASUREMENTS: {
  key: keyof VibrationMeasurements
  title: string
  description: string
}[] = [
  {
    key: 'rms_median',
    title: 'Typical vibration strength',
    description: 'The middle sensor value on each side, after calculating the vibration strength (RMS) of each sensor over the recording.',
  },
  {
    key: 'rms_max',
    title: 'Strongest sensor vibration',
    description: 'The highest vibration strength (RMS) among the sensors on each side over the recording.',
  },
  {
    key: 'abs_peak_max',
    title: 'Largest acceleration peak',
    description: 'The largest absolute vibration acceleration recorded by any sensor on each side, even if it occurred only briefly.',
  },
]

const numberFormat = new Intl.NumberFormat('en', { maximumSignificantDigits: 4 })

export function RailEvidencePanel({ evidence }: { evidence: RailEvidence }) {
  return (
    <details className="group rounded-lg border border-slate-200 bg-white">
      <summary className="cursor-pointer rounded-lg px-5 py-4 text-sm font-semibold text-slate-900 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sky-600">
        What informed this result?
        <span className="mt-1 block pl-4 text-xs font-normal text-slate-500">
          Explore the measurements and how the recording was analysed.
        </span>
      </summary>

      <div className="space-y-6 border-t border-slate-200 p-5">
        <div>
          <h3 className="text-sm font-semibold text-slate-900">From recording to prediction</h3>
          <ol className="mt-3 list-decimal space-y-2 pl-5 text-sm leading-relaxed text-slate-600">
            <li>
              Check the recording has the expected columns, sample count and complete numeric measurements.
            </li>
            <li>
              Summarise vibration strength and sudden peaks from{' '}
              {evidence.vibration_sensors_per_side} sensors on each side, then compare the sides.
            </li>
            <li>
              A model trained on labelled recordings considers {evidence.feature_count} measurements
              together to predict Normal, Side I or Side II.
            </li>
          </ol>
        </div>

        <div className="rounded-md bg-slate-50 p-4">
          <p className="text-xs font-semibold text-slate-700">Recording format checks passed</p>
          <dl className="mt-3 grid grid-cols-2 gap-4 text-sm sm:grid-cols-4">
            <div>
              <dt className="text-xs text-slate-500">Recording duration</dt>
              <dd className="mt-1 font-semibold text-slate-900">{evidence.duration_seconds} second</dd>
            </div>
            <div>
              <dt className="text-xs text-slate-500">Samples per sensor</dt>
              <dd className="mt-1 font-semibold text-slate-900">{evidence.samples_per_sensor.toLocaleString('en')}</dd>
            </div>
            <div>
              <dt className="text-xs text-slate-500">Sensor columns</dt>
              <dd className="mt-1 font-semibold text-slate-900">{evidence.column_count}</dd>
            </div>
            <div>
              <dt className="text-xs text-slate-500">Vibration sensors used</dt>
              <dd className="mt-1 font-semibold text-slate-900">{evidence.vibration_sensors_per_side * 2}</dd>
            </div>
          </dl>
        </div>

        <div>
          <h3 className="text-sm font-semibold text-slate-900">Measurements from this recording</h3>
          <p className="mt-1 text-sm leading-relaxed text-slate-600">
            These are selected measurements supplied to the model. It also considers the shape of
            vibration spikes and differences between the sides. Higher vibration alone does not
            determine the prediction.
          </p>

          <div className="mt-4 space-y-5">
            {MEASUREMENTS.map(({ key, title, description }) => {
              const sideI = evidence.side_i[key]
              const sideII = evidence.side_ii[key]
              const maximum = Math.max(sideI, sideII)
              return (
                <div key={key} className="rounded-lg border border-slate-200 p-4">
                  <h4 className="text-sm font-semibold text-slate-900">{title}</h4>
                  <p className="mt-1 text-xs leading-relaxed text-slate-500">{description}</p>
                  <dl className="mt-4 space-y-3">
                    <MeasurementBar label="Side I" value={sideI} maximum={maximum} colour="bg-sky-600" />
                    <MeasurementBar label="Side II" value={sideII} maximum={maximum} colour="bg-slate-500" />
                  </dl>
                </div>
              )
            })}
          </div>
          <p className="mt-3 text-xs leading-relaxed text-slate-500">
            Each pair uses its own scale. Bars compare the two sides in this recording; they do
            not show defect severity or how much a measurement influenced the prediction.
          </p>
        </div>

        <details className="border-t border-slate-200 pt-4">
          <summary className="cursor-pointer text-sm font-medium text-sky-800 focus-visible:outline-2 focus-visible:outline-sky-600">
            Understanding the terms
          </summary>
          <dl className="mt-3 space-y-3 text-sm leading-relaxed text-slate-600">
            <div>
              <dt className="font-semibold text-slate-800">Corrugation</dt>
              <dd>Repeated, wave-like wear on a rail's running surface. This model looks for associated vibration patterns.</dd>
            </div>
            <div>
              <dt className="font-semibold text-slate-800">Side I and Side II</dt>
              <dd>Side I uses axle-box positions 1, 3, 5 and 7 on each car; Side II uses 2, 4, 6 and 8. These labels identify the side, not a geographic location.</dd>
            </div>
            <div>
              <dt className="font-semibold text-slate-800">RMS (root mean square)</dt>
              <dd>A way to summarise vibration strength across the recording, accounting for movement in both directions.</dd>
            </div>
            <div>
              <dt className="font-semibold text-slate-800">m/s²</dt>
              <dd>Metres per second squared: a unit of acceleration, used here for vibration measurements.</dd>
            </div>
          </dl>
        </details>
      </div>
    </details>
  )
}

function MeasurementBar({
  label, value, maximum, colour,
}: { label: string; value: number; maximum: number; colour: string }) {
  const width = maximum > 0 ? (value / maximum) * 100 : 0
  return (
    <div>
      <div className="mb-1 flex items-baseline justify-between gap-3 text-xs">
        <dt className="font-medium text-slate-700">{label}</dt>
        <dd className="font-medium tabular-nums text-slate-900">{numberFormat.format(value)} m/s²</dd>
      </div>
      <div aria-hidden="true" className="h-2 rounded-full bg-slate-100">
        <div className={`h-2 rounded-full ${colour}`} style={{ width: `${width}%` }} />
      </div>
    </div>
  )
}
