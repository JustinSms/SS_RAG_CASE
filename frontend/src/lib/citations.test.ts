import { expect, test } from "vitest"
import { citationsToLinks, hideOpenCitation } from "./citations"

test("turns citation tags into links", () => {
  expect(citationsToLinks("Thirty days. [c1] And ten. [c2, c3]")).toBe(
    "Thirty days. [c1](cite:c1) And ten. [c2 c3](cite:c2,c3)",
  )
})

test("leaves other brackets and plain text alone", () => {
  expect(citationsToLinks("See [1].")).toBe("See [1].")
})

test("hides a tag that is still arriving, but not finished ones", () => {
  expect(hideOpenCitation("Thirty days. [c")).toBe("Thirty days. ")
  expect(hideOpenCitation("Thirty days. [c12, c")).toBe("Thirty days. ")
  expect(hideOpenCitation("Thirty days. [")).toBe("Thirty days. ")
  expect(hideOpenCitation("Thirty days. [c1]")).toBe("Thirty days. [c1]")
  expect(hideOpenCitation("See [1")).toBe("See ")
})
