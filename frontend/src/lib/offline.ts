/*  Working through a network outage (#228). Pure helpers - no imports - so
    scripts/offline-check.mjs can run them; lib/api.ts wires them into call().

    - Reads: the last answer of a few read-only endpoints (Today, arrivals,
      the room board, the housekeeper's queue) is kept per user, so the desk
      still sees arrivals and room status while the server can't be reached,
      with the time it was synced.
    - Writes: only the safe ones in QUEUED - a room's housekeeping status, a
      housekeeping task's status - are queued offline and sent when back.
      Each carries the status the user saw (`expected`); the server refuses
      the change if someone else changed it meanwhile, and the refusal is
      shown, not retried. Money and everything else stay online-only. */

export interface Store {
  getItem(key: string): string | null
  setItem(key: string, value: string): void
  removeItem(key: string): void
  key(index: number): string | null
  readonly length: number
}

export interface Queued {
  id: string
  method: string
  params: Record<string, unknown>
  /** what it is about, for the list the user sees */
  label: string
  at: number
}

export interface Failed extends Queued {
  error: string
}

const PREFIX = "kamra.offline.v1:"
const QUEUE = `${PREFIX}queue`
const FAILED = `${PREFIX}failed`

/** read-only endpoints whose last answer is kept for an outage */
export const CACHED = new Set([
  "kamra.api.front_desk_snapshot",
  "kamra.dashboards.property_dashboard",
  "kamra.api.room_board",
  "kamra.api.hk_queue",
])

/** safe writes queued offline, and the field of the record they change */
export const QUEUED: Record<string, { key: string; label: (p: Record<string, unknown>) => string }> = {
  "kamra.api.set_housekeeping_status": { key: "room", label: (p) => `${p.room} → ${p.status}` },
  "kamra.api.hk_update_task": { key: "task", label: (p) => `${p.task} → ${p.status}` },
}

const readKey = (user: string, method: string, params: Record<string, unknown>) =>
  `${PREFIX}read:${user}:${method}:${JSON.stringify(params)}`

function parse<T>(raw: string | null, fallback: T): T {
  try {
    return raw ? (JSON.parse(raw) as T) : fallback
  } catch {
    return fallback
  }
}

export function saveRead(store: Store, user: string, method: string,
                         params: Record<string, unknown>, data: unknown, now: number): void {
  if (!CACHED.has(method)) return
  try {
    store.setItem(readKey(user, method, params), JSON.stringify({ at: now, data }))
  } catch {
    /* storage full or blocked: the outage view is a convenience */
  }
}

export function loadRead<T>(store: Store, user: string, method: string,
                            params: Record<string, unknown>): { at: number; data: T } | null {
  if (!CACHED.has(method)) return null
  return parse(store.getItem(readKey(user, method, params)), null)
}

/** The status the user last saw for the record a queued write changes, from
 *  the cached reads: the conflict check on replay compares against it. */
export function seenStatus(store: Store, user: string, method: string,
                           params: Record<string, unknown>): string | undefined {
  const id = method === "kamra.api.set_housekeeping_status" ? params.room : params.task
  for (let i = 0; i < store.length; i++) {
    const k = store.key(i)
    if (!k?.startsWith(`${PREFIX}read:${user}:`)) continue
    const data = parse<{ data?: { rooms?: unknown[]; tasks?: unknown[] } } | null>(store.getItem(k), null)?.data
    const rows = (method === "kamra.api.set_housekeeping_status" ? data?.rooms : data?.tasks) ?? []
    for (const r of rows as Record<string, unknown>[]) {
      if (r?.name === id) {
        const s = method === "kamra.api.set_housekeeping_status" ? r.housekeeping_status : r.status
        if (typeof s === "string") return s
      }
    }
  }
  return undefined
}

export const queued = (store: Store): Queued[] => parse(store.getItem(QUEUE), [])
export const failed = (store: Store): Failed[] => parse(store.getItem(FAILED), [])

/** Queue a safe write. A later change to the same room or task replaces
 *  the earlier one (only the last status matters) but keeps what the user
 *  first saw, so the conflict check still compares with the server's
 *  status from before the outage. */
export function enqueue(store: Store, user: string, method: string,
                        params: Record<string, unknown>, now: number): Queued | null {
  const spec = QUEUED[method]
  if (!spec) return null
  const list = queued(store)
  const same = list.find((q) => q.method === method && q.params[spec.key] === params[spec.key])
  const expected = same ? same.params.expected : seenStatus(store, user, method, params)
  const item: Queued = {
    id: same?.id ?? `${now}-${Math.random().toString(36).slice(2, 8)}`,
    method,
    params: { ...params, ...(expected !== undefined ? { expected } : {}) },
    label: spec.label(params),
    at: now,
  }
  const next = list.filter((q) => q !== same)
  next.push(item)
  store.setItem(QUEUE, JSON.stringify(next))
  return item
}

/** Send what was queued, oldest first. A network failure stops and keeps
 *  the rest for next time; a refusal (a conflict, a permission) drops the
 *  item into `failed` with the server's words - it is never retried. */
export async function replay(
  store: Store,
  send: (method: string, params: Record<string, unknown>) => Promise<unknown>,
  isNetwork: (e: unknown) => boolean,
  message: (e: unknown) => string,
): Promise<{ sent: number; failed: number; left: number }> {
  let sent = 0
  let refused = 0
  for (const item of queued(store)) {
    try {
      await send(item.method, item.params)
      sent++
    } catch (e) {
      if (isNetwork(e)) break
      refused++
      store.setItem(FAILED, JSON.stringify([...failed(store), { ...item, error: message(e) }]))
    }
    store.setItem(QUEUE, JSON.stringify(queued(store).filter((q) => q.id !== item.id)))
  }
  return { sent, failed: refused, left: queued(store).length }
}

export const clearFailed = (store: Store) => store.removeItem(FAILED)

/** Sign-out: nothing of this user's stays on a shared desk computer. */
export function clearAll(store: Store): void {
  const keys: string[] = []
  for (let i = 0; i < store.length; i++) {
    const k = store.key(i)
    if (k?.startsWith(PREFIX)) keys.push(k)
  }
  keys.forEach((k) => store.removeItem(k))
}
