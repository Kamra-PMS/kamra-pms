/* What a generic form sends when it saves. */

export interface PayloadField {
  field: string
  type: string
  /** Sent only when the user changed it: another action (a delivery) may have
   *  written a newer value while the form was open. */
  onlyIfChanged?: boolean
  /** A field of the saved record: while it is set, this input is read-only. */
  lockedBy?: string
}

/** Whether the record says this field can no longer change. `loaded` is null for a new record. */
export function isLocked(field: PayloadField, loaded: Record<string, unknown> | null): boolean {
  return !!field.lockedBy && !!Number(loaded?.[field.lockedBy] ?? 0)
}

const same = (a: unknown, b: unknown) =>
  a === b || (!(a == null || a === "" || b == null || b === "") && Number(a) === Number(b))

/** The form's own fields only - never the raw list row or full document.
 *  `loaded` is the record as the form opened it, null for a new one. */
export function formPayload(
  fields: PayloadField[], draft: Record<string, unknown>,
  loaded: Record<string, unknown> | null,
): Record<string, unknown> {
  const payload: Record<string, unknown> = {}
  for (const f of fields) {
    if (f.type === "readonly") continue
    // an empty secret keeps the stored one
    if (f.type === "password" && !draft[f.field]) continue
    if (!(f.field in draft)) continue
    if (f.onlyIfChanged && loaded && same(draft[f.field], loaded[f.field])) continue
    payload[f.field] = draft[f.field]
  }
  return payload
}
