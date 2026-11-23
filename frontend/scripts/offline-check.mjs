#!/usr/bin/env node
/** Pure checks for working through an outage (#228): the read cache, the
 *  queue of safe writes and its replay. */
import assert from "node:assert/strict"
import fs from "node:fs"
import ts from "typescript"

const filename = new URL("../src/lib/offline.ts", import.meta.url)
const code = ts.transpileModule(fs.readFileSync(filename, "utf8"), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
}).outputText
const off = {}
new Function("exports", code)(off)

function memory() {
  const m = new Map()
  return {
    getItem: (k) => (m.has(k) ? m.get(k) : null),
    setItem: (k, v) => m.set(k, String(v)),
    removeItem: (k) => m.delete(k),
    key: (i) => [...m.keys()][i] ?? null,
    get length() { return m.size },
  }
}
const net = Object.assign(new Error("offline"), { network: true })
const isNet = (e) => Boolean(e.network)
const msg = (e) => e.message

// reads: only the listed screens, per user and arguments
const s = memory()
const board = { rooms: [{ name: "R101", housekeeping_status: "Dirty" }] }
off.saveRead(s, "ana", "kamra.api.room_board", { property: "P" }, board, 1000)
off.saveRead(s, "ana", "kamra.api.take_payment", { folio: "F" }, { ok: 1 }, 1000)
assert.deepEqual(off.loadRead(s, "ana", "kamra.api.room_board", { property: "P" }), { at: 1000, data: board })
assert.equal(off.loadRead(s, "ben", "kamra.api.room_board", { property: "P" }), null)
assert.equal(off.loadRead(s, "ana", "kamra.api.take_payment", { folio: "F" }), null)

// writes: only safe ones queue, each with the status the user saw
assert.equal(off.enqueue(s, "ana", "kamra.api.take_payment", { folio: "F" }, 1), null)
off.enqueue(s, "ana", "kamra.api.set_housekeeping_status", { room: "R101", status: "Clean" }, 2000)
assert.equal(off.queued(s)[0].params.expected, "Dirty")
// a second change to the same room replaces the first, keeps what was seen
off.enqueue(s, "ana", "kamra.api.set_housekeeping_status", { room: "R101", status: "Inspected" }, 3000)
assert.equal(off.queued(s).length, 1)
assert.deepEqual(off.queued(s)[0].params, { room: "R101", status: "Inspected", expected: "Dirty" })
off.enqueue(s, "ana", "kamra.api.hk_update_task", { task: "T1", status: "Done" }, 4000)

// replay: network failure keeps everything for later
let r = await off.replay(s, async () => { throw net }, isNet, msg)
assert.deepEqual(r, { sent: 0, failed: 0, left: 2 })

// a refusal (someone changed it meanwhile) is listed, never retried
const calls = []
r = await off.replay(s, async (m, p) => {
  calls.push(m)
  if (m === "kamra.api.set_housekeeping_status") throw new Error("Room R101 is Out of Order now")
}, isNet, msg)
assert.deepEqual(r, { sent: 1, failed: 1, left: 0 })
assert.deepEqual(calls, ["kamra.api.set_housekeeping_status", "kamra.api.hk_update_task"])
assert.equal(off.failed(s)[0].error, "Room R101 is Out of Order now")
r = await off.replay(s, async () => assert.fail("nothing left to send"), isNet, msg)
assert.deepEqual(r, { sent: 0, failed: 0, left: 0 })

// a failure midway keeps the rest in order
off.enqueue(s, "ana", "kamra.api.hk_update_task", { task: "T2", status: "Done" }, 5000)
off.enqueue(s, "ana", "kamra.api.hk_update_task", { task: "T3", status: "Done" }, 6000)
let n = 0
r = await off.replay(s, async () => { if (n++) throw net }, isNet, msg)
assert.deepEqual(r, { sent: 1, failed: 0, left: 1 })
assert.equal(off.queued(s)[0].params.task, "T3")

// sign-out leaves nothing behind
off.clearAll(s)
assert.equal(s.length, 0)
console.log("offline checks passed")
