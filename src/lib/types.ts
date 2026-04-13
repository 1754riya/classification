export type Stage =
  | 'upload' | 'analyzing' | 'analyzed'
  | 'suggesting' | 'suggested'
  | 'imagining' | 'done'

export interface Analysis {
  classification: string
  objects: string[]
  description: string
}

export interface Message {
  role: 'user' | 'assistant'
  text: string
}

export const STEP_INDEX: Record<Stage, number> = {
  upload: 0, analyzing: 1, analyzed: 1,
  suggesting: 2, suggested: 2,
  imagining: 3, done: 3,
}

export const STARTERS = [
  'Which suggestion has the biggest environmental impact?',
  'What is the estimated cost of these improvements?',
  'Which improvement should be prioritized first?',
  'How long would implementation take?',
]
