import { useId } from 'react'

import type { RailLabel } from '../types'

interface RailTrackDiagramProps {
  prediction: RailLabel
}

const SLEEPER_POSITIONS = [150, 225, 300, 375, 450, 525, 600, 675]
const CORRUGATION_POSITIONS = [190, 245, 300, 355, 410, 465, 520, 575]

export function RailTrackDiagram({ prediction }: RailTrackDiagramProps) {
  const titleId = useId()
  const descriptionId = useId()
  const affectedY = prediction === 'Side I' ? 105 : prediction === 'Side II' ? 215 : null
  const isNormal = prediction === 'Normal'

  const title = isNormal
    ? 'Rail track prediction: Normal'
    : `Rail track prediction: possible corrugation on ${prediction}`
  const description = isNormal
    ? 'A top-down track diagram with both Side I and Side II rails shown in green.'
    : `A top-down track diagram with ${prediction} highlighted in red and marked with a repeating corrugation pattern.`

  function railColour(side: Exclude<RailLabel, 'Normal'>): string {
    if (isNormal) return 'stroke-emerald-600'
    return prediction === side ? 'stroke-red-600' : 'stroke-slate-500'
  }

  return (
    <figure className="rounded-lg border border-slate-200 bg-slate-50 p-4 sm:p-5">
      <svg
        viewBox="0 60 760 195"
        role="img"
        aria-labelledby={`${titleId} ${descriptionId}`}
        className="h-auto w-full"
      >
        <title id={titleId}>{title}</title>
        <desc id={descriptionId}>{description}</desc>

        <g aria-hidden="true">
          {SLEEPER_POSITIONS.map((x) => (
            <rect
              key={x}
              x={x - 10}
              y="78"
              width="20"
              height="164"
              rx="5"
              className="fill-slate-300"
            />
          ))}

          <line
            x1="115"
            y1="105"
            x2="710"
            y2="105"
            className={railColour('Side I')}
            strokeWidth="18"
            strokeLinecap="round"
          />
          <line
            x1="115"
            y1="215"
            x2="710"
            y2="215"
            className={railColour('Side II')}
            strokeWidth="18"
            strokeLinecap="round"
          />

          <text
            x="92"
            y="113"
            textAnchor="end"
            className="fill-slate-900 text-[26px] font-bold"
          >
            Side I
          </text>
          <text
            x="92"
            y="223"
            textAnchor="end"
            className="fill-slate-900 text-[26px] font-bold"
          >
            Side II
          </text>

          {affectedY !== null &&
            CORRUGATION_POSITIONS.map((x) => (
              <path
                key={x}
                d={`M ${x - 18} ${affectedY} q 9 -13 18 0 q 9 13 18 0`}
                className="fill-none stroke-red-950"
                strokeWidth="4"
                strokeLinecap="round"
              />
            ))}

        </g>
      </svg>

      <figcaption className="mt-3 text-xs text-slate-500">
        <div className="grid grid-cols-2 gap-3">
          <p><span className="block font-semibold text-slate-700">Side I</span>Positions 1, 3, 5, 7</p>
          <p><span className="block font-semibold text-slate-700">Side II</span>Positions 2, 4, 6, 8</p>
        </div>
        <p className="mt-3 leading-relaxed">
          Schematic viewed from above: highlights the predicted side, not defect size or location.
        </p>
      </figcaption>
    </figure>
  )
}
