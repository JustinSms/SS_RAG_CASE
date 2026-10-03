import { expect, test } from "vitest"
import { splitAnswer } from "./citations"

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
