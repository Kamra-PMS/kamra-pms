#!/usr/bin/env node
/** Pure regression checks for the room counts on the booking screens. */
import assert from "node:assert/strict"
import fs from "node:fs"
import ts from "typescript"

const load = (path) => {
  const code = ts.transpileModule(fs.readFileSync(new URL(path, import.meta.url), "utf8"), {
    compilerOptions: {
      module: ts.ModuleKind.CommonJS,
      target: ts.ScriptTarget.ES2022,
      esModuleInterop: true,
    },
  }).outputText
  const mod = {}
  new Function("exports", code)(mod)
  return mod
}
const { saleState, sellableRooms, freeCounts } = load("../src/lib/roomsToSell.ts")
const { pickDefaultRoomType } = load("../src/lib/bookingDefaults.ts")

const open = { free: 2, without_room: false }
const noRoom = { free: 0, without_room: true }
const sold = { free: 0, without_room: false }

assert.equal(saleState(open), "left")
assert.equal(saleState(noRoom), "without_room", "a save is still accepted")
assert.equal(saleState(sold), "sold_out")
assert.equal(saleState(undefined), null, "nothing is claimed before the answer")

const rooms = [{ name: "101" }, { name: "102" }]
assert.deepEqual(sellableRooms(rooms, open), rooms)
assert.deepEqual(
  sellableRooms(rooms, { free: 1, without_room: false }),
  rooms,
  "one left: the desk still picks which room",
)
assert.deepEqual(sellableRooms(rooms, sold), [], "sold to stays with no room number")
assert.deepEqual(sellableRooms(rooms, noRoom), [], "a walk-in needs a room now")
assert.deepEqual(sellableRooms(rooms, undefined), rooms, "unknown: leave the list")

const types = [{ name: "cheap" }, { name: "mid" }]
assert.equal(
  pickDefaultRoomType(types, freeCounts({ cheap: sold, mid: open })),
  "mid",
  "skip a sold type",
)
assert.equal(
  pickDefaultRoomType(types, freeCounts({})),
  "cheap",
  "no answer: still pick a type",
)

console.log("rooms-to-sell-check: ok")
