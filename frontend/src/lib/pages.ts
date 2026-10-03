// "p. 12" for one page, "p. 12-13" for a range.
export function formatPages(start: number, end: number): string {
  return start === end ? `p. ${start}` : `p. ${start}-${end}`
}
