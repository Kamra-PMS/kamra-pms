import { useEffect, useMemo, useState } from "react"
import { call, getCurrentProperty } from "../lib/api"
import { cur, fmtAmount } from "../lib/money"
import { useT } from "../lib/i18n"
import TagPills, { type Pill } from "./TagPills"

/* The "Choices" pills on a dish's own form: tick the groups (milk, ice, extras)
   this dish asks about, the same as ticking the dish inside a group under
   Menu -> Choices. Both write the dish's `modifier_groups` rows, so they always
   agree. Only the dish's outlet's groups are offered: a group belongs to one
   outlet, and the server refuses another outlet's.

   The form's save sends `modifier_groups` with the rest of the dish; rows that
   stay ticked keep their name, so saving a dish does not rewrite its history. */

interface Option { name: string; option_name: string; price: number }
interface Group {
  name: string
  group_name: string
  outlet: string
  required: 0 | 1
  multi: 0 | 1
  max_choices: number
  options: Option[]
}
interface Overview { groups: Group[] }
type GroupRow = { name?: string; modifier_group: string } & Record<string, unknown>

/** What a group asks, in a few words: "Must choose one", "Up to 3", "Pick any". */
function rule(g: Group, t: ReturnType<typeof useT>["t"]) {
  const how = g.multi
    ? (g.max_choices ? t("Choose up to {n}", { n: g.max_choices }) : t("Choose any"))
    : t("Choose one")
  return g.required ? `${t("Required")} · ${how}` : `${t("Optional")} · ${how}`
}

export default function ChoiceGroupsField({
  outlet, value, onChange,
}: {
  /** the dish's outlet (the form's own Outlet field); groups are shown for it */
  outlet: string | undefined
  /** the dish's `modifier_groups` rows as the server sent them, or what this field last set */
  value: unknown
  onChange: (rows: GroupRow[]) => void
}) {
  const { t } = useT()
  const [groups, setGroups] = useState<Group[] | null>(null)
  const [denied, setDenied] = useState(false)

  useEffect(() => {
    let live = true
    call<Overview>("kamra.menu_modifiers.modifier_overview", { property: getCurrentProperty() })
      .then((o) => { if (live) setGroups(o.groups) })
      // a user without the menu right gets nothing to tick here, and nothing is sent for it
      .catch(() => { if (live) setDenied(true) })
    return () => { live = false }
  }, [])

  const rows: GroupRow[] = useMemo(() => (Array.isArray(value) ? (value as GroupRow[]) : []), [value])
  const mine = useMemo(() => (groups ?? []).filter((g) => g.outlet === outlet), [groups, outlet])
  const ticked = new Set(rows.map((r) => r.modifier_group))

  // Moving a dish to another outlet leaves the old outlet's groups behind: drop them
  // here, so the save does not fail on "belongs to another outlet".
  useEffect(() => {
    if (!groups || !outlet || rows.length === 0) return
    const ok = new Set(mine.map((g) => g.name))
    const kept = rows.filter((r) => ok.has(r.modifier_group))
    if (kept.length !== rows.length) onChange(kept)
  }, [groups, outlet, mine, rows, onChange])

  if (denied) return null
  const toggle = (g: Group) => {
    if (ticked.has(g.name)) onChange(rows.filter((r) => r.modifier_group !== g.name))
    else onChange([...rows, { modifier_group: g.name }])
  }

  if (!outlet) return <p className="text-xs text-zinc-400">{t("Pick the outlet first, then its choice groups show here.")}</p>
  if (groups === null) return <p className="text-xs text-zinc-400">{t("Loading…")}</p>
  if (mine.length === 0) {
    return <p className="text-xs text-zinc-400">{t("This outlet has no choice groups yet. Make them under Menu → Choices.")}</p>
  }

  // the same pills as Allergens & dietary tags (components/TagPills): picked ones first with a x, the rest as "+ Name"
  const pill = (g: Group): Pill => ({
    key: g.name,
    label: g.group_name,
    title: `${rule(g, t)}: ${g.options.map((o) => o.option_name + (o.price > 0 ? ` +${cur()}${fmtAmount(o.price)}` : "")).join(" · ")}`,
  })
  const byName = new Map(mine.map((g) => [g.name, g]))
  return (
    <TagPills
      selected={rows.flatMap((r) => (byName.has(r.modifier_group) ? [pill(byName.get(r.modifier_group)!)] : []))}
      available={mine.filter((g) => !ticked.has(g.name)).map(pill)}
      onToggle={(name) => {
        const g = byName.get(name)
        if (g) toggle(g)
      }}
      noneSelected={t("None selected")}
    />
  )
}
