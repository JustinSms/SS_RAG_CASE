import { expect, test } from "vitest"
import { hideOpenCitation, splitAnswer } from "./citations"

test("splits text and citation groups", () => {
  expect(splitAnswer("Thirty days. [c1] And ten. [c2, c3]")).toEqual([
    "Thirty days. ",
    { ids: ["c1"] },
    " And ten. ",
    { ids: ["c2", "c3"] },
  ])
})

test("leaves other brackets and plain text alone", () => {
  expect(splitAnswer("See [1].")).toEqual(["See [1]."])
})

test("hides a tag that is still arriving, but not finished ones", () => {
  expect(hideOpenCitation("Thirty days. [c")).toBe("Thirty days. ")
  expect(hideOpenCitation("Thirty days. [c12, c")).toBe("Thirty days. ")
  expect(hideOpenCitation("Thirty days. [")).toBe("Thirty days. ")
  expect(hideOpenCitation("Thirty days. [c1]")).toBe("Thirty days. [c1]")
  expect(hideOpenCitation("See [1")).toBe("See ")
})
