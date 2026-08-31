import { useEffect, useId, useState } from "react"
import { updateResource, serverError } from "../lib/resource"
import { Button } from "./ui/button"

const inputCls =
  "rounded-lg border border-zinc-300 bg-white px-2 py-1 text-sm " +
  "focus:outline-2 focus:outline-offset-1 focus:outline-brand-600"

/** Inline nationality edit — updates the Guest profile (shown on folio & GRC). */
export default function EditableNationality(props: {
  guestId: string
  value: string | null
  onSaved?: (nationality: string) => void
  /** inline: folio fact row; row: GRC label/value layout */
  variant?: "inline" | "row"
}) {
  const listId = useId()
  const variant = props.variant ?? "inline"
  const displayed = props.value?.trim() || "—"
  const [editing, setEditing] = useState(false)
  const [val, setVal] = useState(props.value ?? "Indian")
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!editing) setVal(props.value ?? "Indian")
  }, [props.value, editing])

  async function save() {
    const next = val.trim()
    if (!next) return
    setBusy(true)
    setError(null)
    try {
      await updateResource("Guest", props.guestId, { nationality: next })
      props.onSaved?.(next)
      setEditing(false)
    } catch (e) {
      setError(serverError(e))
    } finally {
      setBusy(false)
    }
  }

  function startEdit() {
    setVal(props.value ?? "Indian")
    setError(null)
    setEditing(true)
  }

  const editor = editing ? (
    <span className="flex flex-wrap items-center gap-1 print:hidden">
      <input
        className={inputCls}
        value={val}
        onChange={(e) => setVal(e.target.value)}
        placeholder="Nationality"
        list={listId}
      />
      <datalist id={listId}>
        {["Indian", "American", "British", "Canadian", "Australian", "German", "French", "Japanese", "Chinese", "Singaporean", "UAE", "Other"].map(
          (n) => (
            <option key={n} value={n} />
          ),
        )}
      </datalist>
      <Button
        variant="outline"
        className="!px-2 !py-1 text-xs"
        disabled={busy || !val.trim()}
        onClick={save}
      >
        {busy ? "…" : "Save"}
      </Button>
      <button
        type="button"
        className="text-xs text-zinc-400"
        disabled={busy}
        onClick={() => setEditing(false)}
      >
        ✕
      </button>
      {error && <span className="text-xs text-rose-600">{error}</span>}
    </span>
  ) : (
    <span className="font-medium">
      <span className="print:inline">{displayed}</span>
      <button
        type="button"
        className="ml-2 text-xs font-medium text-brand-700 hover:underline print:hidden"
        onClick={startEdit}
      >
        edit
      </button>
    </span>
  )

  if (variant === "row") {
    return (
      <div className="flex border-b border-zinc-200 py-1.5 text-sm">
        <span className="w-40 shrink-0 text-zinc-500">Nationality</span>
        {editor}
      </div>
    )
  }

  return editor
}
