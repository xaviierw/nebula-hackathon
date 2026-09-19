import { reviewSteps } from '../review'
import type { ChecklistStep, RailLabel } from '../types'

export function RailReviewChecklist({ prediction, checked, onChange }: {
  prediction: RailLabel
  checked: ChecklistStep[]
  onChange: (checked: ChecklistStep[]) => void
}) {
  const isNormal = prediction === 'Normal'
  const steps = reviewSteps(prediction)

  return (
    <section className="rounded-lg border border-sky-200 bg-sky-50 p-5">
      <fieldset>
        <legend className="text-base font-semibold text-sky-950">Review checklist</legend>
        <p className="mt-1 text-sm text-sky-900">
          {isNormal
            ? 'Use this finding alongside your routine monitoring information.'
            : 'Use these steps to prepare the finding for engineering review.'}
        </p>
        <div className="mt-4 space-y-4">
          {steps.map((step) => (
            <label key={step.id} className="flex cursor-pointer items-start gap-3">
              <input
                type="checkbox"
                checked={checked.includes(step.id)}
                onChange={(event) => {
                  const isChecked = event.target.checked
                  onChange(isChecked ? [...checked, step.id] : checked.filter((id) => id !== step.id))
                }}
                className="mt-1 size-4 shrink-0 accent-sky-700 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sky-600"
              />
              <span>
                <span className="block text-sm font-semibold text-sky-950">{step.title}</span>
                <span className="mt-1 block text-sm leading-relaxed text-sky-900">{step.description}</span>
              </span>
            </label>
          ))}
        </div>
      </fieldset>
      <p role="status" className="mt-4 text-xs font-medium text-sky-900">
        {checked.length} of {steps.length} preparation steps checked
      </p>
      <p className="mt-1 text-xs leading-relaxed text-sky-800">
        Selections are saved with this recording's review record in this browser.
        Checking a step does not send a maintenance request.
      </p>
    </section>
  )
}
