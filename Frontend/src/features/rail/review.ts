import type { ChecklistStep, RailLabel, RailReview } from './types'

export function emptyReview(): RailReview {
  return {
    status: 'awaiting_review', reviewer: '', runReference: '', location: '', notes: '',
    checkedSteps: [], updatedAt: null, reviewedAt: null,
  }
}

export function finding(prediction: RailLabel): string {
  return prediction === 'Normal'
    ? 'No corrugation pattern identified'
    : `Possible corrugation on ${prediction}`
}

export function nextStep(prediction: RailLabel): string {
  return prediction === 'Normal' ? 'Keep with routine monitoring records' : 'Prepare for engineering review'
}

export function reviewSteps(prediction: RailLabel): { id: ChecklistStep; title: string; description: string }[] {
  return [
    {
      id: 'context', title: 'Confirm the recording context',
      description: 'Identify the train/run and track section using your recording records. This CSV does not provide a geographic location.',
    },
    {
      id: 'evidence', title: 'Review the evidence',
      description: 'Open the measurements above and compare with related recordings where available. Check that they refer to comparable operating conditions.',
    },
    {
      id: 'handoff',
      title: prediction === 'Normal' ? 'Keep the finding with your monitoring records' : 'Prepare an engineering review',
      description: prediction === 'Normal'
        ? 'Retain the prediction with the recording context. If other observations raise concerns, include them in an engineering review.'
        : `Share the ${prediction} finding, recording, measurements and location context with the responsible engineer through your maintenance process.`,
    },
  ]
}
