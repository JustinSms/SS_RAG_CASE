// The answer holds ids like [c3] or [c3, c7].
const CITATION = /\[\s*(c\d+(?:\s*,\s*c\d+)*)\s*\]/g

// Prefix of the link target a citation becomes, so the markdown renderer can swap it for a chip.
export const CITATION_SCHEME = "cite:"

// Turn each tag into a markdown link like [c3, c7] -> [c3](cite:c3,c7), so the answer can be rendered as markdown.
export function citationsToLinks(answer: string): string {
  return answer.replace(CITATION, (_, ids: string) => {
    const list = ids.split(",").map((id) => id.trim())
    return `[${list.join(" ")}](${CITATION_SCHEME}${list.join(",")})`
  })
}

// While the answer streams, the end may hold a tag that is not finished yet ("[c1" or "[c1, c"). Hide it.
const OPEN_CITATION = /\[\s*c?\d*(?:\s*,\s*c?\d*)*\s*$/

export function hideOpenCitation(text: string): string {
  return text.replace(OPEN_CITATION, "")
}
