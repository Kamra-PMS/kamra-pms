import { useCallback, useEffect, useState } from "react"
import { Plus, Trash2 } from "lucide-react"
import { Sheet } from "./ui/sheet"
import { getCurrentProperty } from "../lib/api"
import {
  createResource,
  deleteResource,
  listResource,
  serverError,
  updateResource,
  type Row,
} from "../lib/resource"
import { Badge } from "./ui/badge"
import { Button } from "./ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "./ui/card"

export interface FieldSpec {
  field: string
  label: string
  type: "data" | "int" | "float" | "currency" | "select" | "check" | "date" | "link" | "readonly"
  options?: string[] // for select
  linkDoctype?: string // for link
  required?: boolean
}

export interface ScreenConfig {
  doctype: string
  title: string
  description?: string
  columns: { field: string; label: string; badge?: boolean }[]
  form: FieldSpec[]
  propertyScoped?: boolean
  allowCreate?: boolean
  allowDelete?: boolean
  orderBy?: string
}

const inputCls =
  "w-full rounded-lg border border-zinc-300 bg-white px-3 py-1.5 text-sm " +
  "focus:outline-2 focus:outline-offset-1 focus:outline-brand-600 " +
  "disabled:bg-zinc-50 disabled:text-zinc-400"

function FieldInput(props: {
  spec: FieldSpec
  value: unknown
  onChange: (v: unknown) => void
  linkOptions: Record<string, string[]>
}) {
  const { spec, value, onChange } = props
  switch (spec.type) {
    case "select":
      return (
        <select
          className={inputCls}
          value={String(value ?? "")}
          onChange={(e) => onChange(e.target.value)}
        >
          <option value="">—</option>
          {spec.options?.map((o) => (
            <option key={o} value={o}>
              {o}
            </option>
          ))}
        </select>
      )
    case "link":
      return (
        <select
          className={inputCls}
          value={String(value ?? "")}
          onChange={(e) => onChange(e.target.value)}
        >
          <option value="">—</option>
          {(props.linkOptions[spec.linkDoctype ?? ""] ?? []).map((o) => (
            <option key={o} value={o}>
              {o}
            </option>
          ))}
        </select>
      )
    case "check":
      return (
        <input
          type="checkbox"
          className="size-4 accent-brand-600"
          checked={Boolean(Number(value ?? 0))}
          onChange={(e) => onChange(e.target.checked ? 1 : 0)}
        />
      )
    case "date":
      return (
        <input
          type="date"
          className={inputCls}
          value={String(value ?? "")}
          onChange={(e) => onChange(e.target.value)}
        />
      )
    case "int":
    case "float":
    case "currency":
      return (
        <input
          type="number"
          className={inputCls}
          value={value === null || value === undefined ? "" : Number(value)}
          onChange={(e) =>
            onChange(e.target.value === "" ? null : Number(e.target.value))
          }
        />
      )
    case "readonly":
      return (
        <input className={inputCls} disabled value={String(value ?? "")} />
      )
    default:
      return (
        <input
          className={inputCls}
          value={String(value ?? "")}
          onChange={(e) => onChange(e.target.value)}
        />
      )
  }
}

export function ResourceScreen({ config }: { config: ScreenConfig }) {
  const [rows, setRows] = useState<Row[]>([])
  const [editing, setEditing] = useState<Row | "new" | null>(null)
  const [draft, setDraft] = useState<Record<string, unknown>>({})
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [linkOptions, setLinkOptions] = useState<Record<string, string[]>>({})

  const fields = Array.from(
    new Set(["name", ...config.columns.map((c) => c.field)]),
  )

  const load = useCallback(() => {
    listResource(config.doctype, {
      fields,
      filters: config.propertyScoped
        ? [["property", "=", getCurrentProperty()]]
        : undefined,
      orderBy: config.orderBy,
    })
      .then((r) => {
        setRows(r)
        setError(null)
      })
      .catch((e) => setError(serverError(e)))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [config.doctype])

  useEffect(load, [load])

  // load link options once per screen
  useEffect(() => {
    const links = config.form.filter((f) => f.type === "link" && f.linkDoctype)
    links.forEach((f) => {
      listResource(f.linkDoctype!, {
        fields: ["name"],
        filters: undefined,
        limit: 100,
        orderBy: "name asc",
      }).then((r) =>
        setLinkOptions((prev) => ({
          ...prev,
          [f.linkDoctype!]: r.map((x) => x.name),
        })),
      )
    })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [config.doctype])

  function openEdit(row: Row | "new") {
    setEditing(row)
    setDraft(row === "new" ? {} : { ...row })
    setError(null)
  }

  async function save() {
    setBusy(true)
    try {
      const payload = { ...draft }
      delete payload.name
      if (config.propertyScoped) payload.property = getCurrentProperty()
      if (editing === "new") {
        await createResource(config.doctype, payload)
      } else if (editing) {
        await updateResource(config.doctype, editing.name, payload)
      }
      setEditing(null)
      load()
    } catch (e) {
      setError(serverError(e))
    } finally {
      setBusy(false)
    }
  }

  async function remove() {
    if (editing === "new" || !editing) return
    setBusy(true)
    try {
      await deleteResource(config.doctype, editing.name)
      setEditing(null)
      load()
    } catch (e) {
      setError(serverError(e))
    } finally {
      setBusy(false)
    }
  }

  return (
    <Card>
      <CardHeader>
        <div>
          <CardTitle>{config.title}</CardTitle>
          {config.description && (
            <p className="mt-0.5 text-xs text-zinc-400">
              {config.description}
            </p>
          )}
        </div>
        {config.allowCreate !== false && (
          <Button onClick={() => openEdit("new")}>
            <Plus className="size-4" aria-hidden />
            New
          </Button>
        )}
      </CardHeader>
      <CardContent>
        {error && !editing && (
          <div className="mb-3 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
            {error}
          </div>
        )}
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-zinc-200 text-left text-xs font-medium uppercase tracking-wider text-zinc-500">
                {config.columns.map((c) => (
                  <th key={c.field} className="py-2 pr-4">
                    {c.label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-100">
              {rows.map((row) => (
                <tr
                  key={row.name}
                  className="cursor-pointer hover:bg-zinc-50"
                  onClick={() => openEdit(row)}
                >
                  {config.columns.map((c) => (
                    <td key={c.field} className="py-2.5 pr-4">
                      {c.badge && row[c.field] ? (
                        <Badge tone="zinc">{String(row[c.field])}</Badge>
                      ) : (
                        String(row[c.field] ?? "—")
                      )}
                    </td>
                  ))}
                </tr>
              ))}
              {rows.length === 0 && (
                <tr>
                  <td
                    colSpan={config.columns.length}
                    className="py-6 text-center text-sm text-zinc-400"
                  >
                    Nothing here yet.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </CardContent>

      {editing && (
        <Sheet
          title={
            editing === "new"
              ? `New ${config.title.replace(/s$/, "")}`
              : String(editing.name)
          }
          description={config.description}
          onClose={() => setEditing(null)}
          footer={
            <div className="flex items-center justify-between">
              {editing !== "new" && config.allowDelete !== false ? (
                <Button
                  variant="ghost"
                  disabled={busy}
                  onClick={remove}
                  aria-label="Delete"
                >
                  <Trash2 className="size-4 text-rose-500" aria-hidden />
                  Delete
                </Button>
              ) : (
                <span />
              )}
              <div className="flex gap-2">
                <Button variant="outline" onClick={() => setEditing(null)}>
                  Cancel
                </Button>
                <Button disabled={busy} onClick={save}>
                  {busy ? "Saving…" : "Save"}
                </Button>
              </div>
            </div>
          }
        >
          <div className="space-y-4">
            {config.form.map((spec) => (
              <label key={spec.field} className="block">
                <span className="mb-1.5 block text-sm font-medium text-zinc-600">
                  {spec.label}
                  {spec.required && <span className="text-rose-500"> *</span>}
                </span>
                <FieldInput
                  spec={spec}
                  value={draft[spec.field]}
                  onChange={(v) => setDraft((d) => ({ ...d, [spec.field]: v }))}
                  linkOptions={linkOptions}
                />
              </label>
            ))}
            {error && (
              <div className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
                {error}
              </div>
            )}
          </div>
        </Sheet>
      )}
    </Card>
  )
}
