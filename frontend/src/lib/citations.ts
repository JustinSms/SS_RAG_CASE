// The answer holds ids like [c3] or [c3, c7]; split it into text and groups of ids.
const CITATION = /\[\s*(c\d+(?:\s*,\s*c\d+)*)\s*\]/g

export type AnswerPart = string | { ids: string[] }

export function splitAnswer(answer: string): AnswerPart[] {
  const parts: AnswerPart[] = []
  let last = 0
  for (const match of answer.matchAll(CITATION)) {
    if (match.index > last) parts.push(answer.slice(last, match.index))
    parts.push({ ids: match[1].split(",").map((id) => id.trim()) })
    last = match.index + match[0].length
  }
  if (last < answer.length) parts.push(answer.slice(last))
  return parts
}
