/*  What the property sells at a function.

    Two lists. Menu packages are priced per plate and carry their courses,
    so the event order can print what the kitchen actually cooks. Services
    are everything else - the LED wall, the DJ, the podium, the stage, the
    decor, the bar - priced per event, hour, day, pax or unit.

    A service's `chargeable` flag is the default, not the rule: the podium
    and the house mics are usually free, and any function can override it
    either way. Free items still print on the event order and the pack
    list, because someone still has to carry them. */

import { useCallback, useEffect, useMemo, useState } from "react"
import { ChefHat, Plus, Search, Trash2, UtensilsCrossed, Wrench } from "lucide-react"

import {
  banquet,
  type BanquetCatalogue as Cat,
  type BanquetMenu,
  type BanquetMenuCourse,
  type BanquetDish,
  type BanquetService,
  type RecipeRow,
} from "../lib/api"
import { getCurrentProperty } from "../lib/api"
import { listResource, serverError, type Row } from "../lib/resource"
import { useAuth } from "../lib/auth"
import { Button } from "../components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card"
import { Sheet } from "../components/ui/sheet"
import { taxLabel } from "../lib/money"
import {
  CATALOGUE_UOMS,
  Empty,
  ErrorNote,
  Field,
  FOOD_TYPES,
  inputCls,
  inr,
  MEAL_PERIODS,
  Select,
  SERVICE_CATEGORIES,
  SERVICE_STYLES,
} from "./banquet/shared"

const EDIT_ROLES = [
  "Front Desk",
  "Revenue Manager",
  "Finance",
  "Hotel Admin",
  "System Manager",
  "Administrator",
]

type Tab = "menus" | "services" | "dishes"

export default function BanquetCatalogue() {
  const { roles } = useAuth()
  const canEdit = roles.some((r) => EDIT_ROLES.includes(r))
  const [cat, setCat] = useState<Cat | null>(null)
  const [dishes, setDishes] = useState<BanquetDish[] | null>(null)
  const [tab, setTab] = useState<Tab>("menus")
  const [query, setQuery] = useState("")
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [menuDraft, setMenuDraft] = useState<Partial<BanquetMenu> | null>(null)
  const [svcDraft, setSvcDraft] = useState<Partial<BanquetService> | null>(null)
  const [dishDraft, setDishDraft] = useState<Partial<BanquetDish> | null>(null)

  const load = useCallback(() => {
    banquet
      .catalogue()
      .then(setCat)
      .catch((e) => setError(serverError(e)))
    banquet.dishes().then(setDishes).catch(() => {})
  }, [])
  useEffect(load, [load])

  const act = async (work: () => Promise<unknown>) => {
    setBusy(true)
    setError(null)
    try {
      await work()
      load()
    } catch (e) {
      setError(serverError(e))
    } finally {
      setBusy(false)
    }
  }

  const menus = useMemo(
    () =>
      (cat?.menus ?? []).filter((m) =>
        (m.menu_name + m.meal_period + (m.cuisine ?? ""))
          .toLowerCase()
          .includes(query.toLowerCase()),
      ),
    [cat, query],
  )
  const services = useMemo(
    () =>
      (cat?.services ?? []).filter((s) =>
        (s.item_name + s.category).toLowerCase().includes(query.toLowerCase()),
      ),
    [cat, query],
  )

  return (
    <Card>
      <CardHeader>
        <div>
          <CardTitle>Banquet catalogue</CardTitle>
          <p className="mt-0.5 text-xs text-zinc-400">
            The menus and services every quote is built from.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-1.5">
          <div className="relative">
            <Search className="pointer-events-none absolute left-2.5 top-1/2 size-3.5 -translate-y-1/2 text-zinc-400" />
            <input
              className={inputCls + " !w-44 pl-8"}
              placeholder="Search…"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
          </div>
          {canEdit && (
            <Button
              onClick={() => {
                if (tab === "menus")
                  setMenuDraft({
                    menu_name: "",
                    meal_period: "Dinner",
                    food_type: "Veg",
                    service_style: "Buffet",
                    rate_per_pax: 0,
                    gst_rate: 5,
                    courses: [],
                  })
                else if (tab === "dishes")
                  setDishDraft({
                    dish_name: "",
                    course_type: "Main Course",
                    food_type: "Veg",
                    kitchen: "Main Kitchen",
                    portion_per_pax: 1,
                    recipe: [],
                  })
                else
                  setSvcDraft({
                    item_name: "",
                    category: "Audio Visual",
                    uom: "Per Event",
                    rate: 0,
                    gst_rate: 18,
                    chargeable: 1,
                    on_pack_list: 1,
                    is_alcohol: 0,
                  })
              }}
            >
              <Plus className="size-4" />
              {tab === "menus"
                ? "New menu"
                : tab === "dishes"
                  ? "New dish"
                  : "New service"}
            </Button>
          )}
        </div>
      </CardHeader>
      <CardContent>
        <ErrorNote error={error} />
        <div className="mb-4 flex gap-1 border-b border-zinc-200">
          {(
            [
              ["menus", `Menus (${cat?.menus.length ?? 0})`, UtensilsCrossed],
              ["services", `Services (${cat?.services.length ?? 0})`, Wrench],
              ["dishes", `Dishes (${dishes?.length ?? 0})`, ChefHat],
            ] as [Tab, string, typeof Wrench][]
          ).map(([id, label, Icon]) => (
            <button
              key={id}
              onClick={() => setTab(id)}
              className={
                "-mb-px inline-flex items-center gap-1.5 border-b-2 px-3 py-2 text-sm font-medium " +
                (tab === id
                  ? "border-brand-600 text-brand-700"
                  : "border-transparent text-zinc-500 hover:text-zinc-800")
              }
            >
              <Icon className="size-4" />
              {label}
            </button>
          ))}
        </div>

        {tab === "dishes" && (
          <DishLibrary
            dishes={dishes}
            canEdit={canEdit}
            busy={busy}
            onChanged={load}
            onEdit={setDishDraft}
            onDelete={(name) => act(() => banquet.deleteDish(name))}
          />
        )}

        {tab === "menus" &&
          (menus.length === 0 ? (
            <Empty>
              {cat === null
                ? "Loading…"
                : "No menu packages yet - add the ones you actually sell."}
            </Empty>
          ) : (
            <ul className="grid gap-3 lg:grid-cols-2">
              {menus.map((m) => (
                <li
                  key={m.name}
                  className="rounded-xl border border-zinc-200 px-4 py-3"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <p className="font-medium">
                        {m.menu_name}
                        {m.menu_code && (
                          <span className="ml-2 font-mono text-xs font-normal text-zinc-400">
                            {m.menu_code}
                          </span>
                        )}
                      </p>
                      <p className="text-xs text-zinc-400">
                        {m.meal_period} · {m.food_type} · {m.service_style}
                        {m.cuisine ? ` · ${m.cuisine}` : ""}
                        {m.min_pax ? ` · min ${m.min_pax} pax` : ""}
                      </p>
                    </div>
                    <div className="shrink-0 text-right">
                      <p className="tabular-nums">
                        {inr(m.rate_per_pax)}
                        <span className="text-xs text-zinc-400">/pax</span>
                      </p>
                      <p className="text-xs text-zinc-400">
                        {taxLabel()} {m.gst_rate}%
                      </p>
                    </div>
                  </div>
                  {m.courses.length > 0 && (
                    <ul className="mt-2 space-y-0.5">
                      {m.courses.map((c) => (
                        <li key={c.name} className="flex gap-2 text-xs">
                          <span className="w-28 shrink-0 font-medium text-zinc-500">
                            {c.course}
                          </span>
                          <span className="text-zinc-500">{c.dishes}</span>
                        </li>
                      ))}
                    </ul>
                  )}
                  {canEdit && (
                    <div className="mt-2 flex gap-2">
                      <Button
                        variant="outline"
                        className="!px-2 !py-1 !text-xs"
                        onClick={() => setMenuDraft(m)}
                      >
                        Edit
                      </Button>
                      <Button
                        variant="ghost"
                        className="!px-2 !py-1 !text-xs !text-rose-600"
                        disabled={busy}
                        onClick={() => act(() => banquet.deleteMenu(m.name))}
                      >
                        <Trash2 className="size-3.5" />
                      </Button>
                    </div>
                  )}
                </li>
              ))}
            </ul>
          ))}

        {tab === "services" &&
          (services.length === 0 ? (
            <Empty>
              {cat === null
                ? "Loading…"
                : "Nothing here yet - projectors, LED walls, DJ, podium, stage, decor, bar."}
            </Empty>
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-zinc-200 text-left text-xs uppercase tracking-wider text-zinc-400">
                  <th className="py-2 pr-3 font-medium">Item</th>
                  <th className="py-2 pr-3 font-medium">Category</th>
                  <th className="py-2 pr-3 font-medium">Charged</th>
                  <th className="py-2 pr-3 text-right font-medium">Rate</th>
                  <th className="py-2 pr-3 text-right font-medium">
                    {taxLabel()}
                  </th>
                  <th className="py-2 pr-3 font-medium">By default</th>
                  {canEdit && <th className="py-2 w-24" />}
                </tr>
              </thead>
              <tbody>
                {services.map((s) => (
                  <tr key={s.name} className="border-b border-zinc-100">
                    <td className="py-2 pr-3">
                      <span className="font-medium">{s.item_name}</span>
                      {s.description && (
                        <p className="text-xs text-zinc-400">{s.description}</p>
                      )}
                    </td>
                    <td className="py-2 pr-3 text-zinc-500">{s.category}</td>
                    <td className="py-2 pr-3 text-zinc-500">{s.uom}</td>
                    <td className="py-2 pr-3 text-right tabular-nums">
                      {inr(s.rate)}
                    </td>
                    <td className="py-2 pr-3 text-right tabular-nums text-zinc-500">
                      {s.gst_rate}%
                    </td>
                    <td className="py-2 pr-3 text-xs">
                      <span
                        className={
                          s.chargeable ? "text-zinc-500" : "text-emerald-700"
                        }
                      >
                        {s.chargeable ? "Chargeable" : "Complimentary"}
                      </span>
                      {s.is_alcohol ? (
                        <span className="ml-1.5 text-amber-700">alcohol</span>
                      ) : null}
                      {s.on_pack_list ? (
                        <span className="ml-1.5 text-zinc-400">packed</span>
                      ) : null}
                    </td>
                    {canEdit && (
                      <td className="py-2">
                        <div className="flex gap-1">
                          <Button
                            variant="outline"
                            className="!px-2 !py-1 !text-xs"
                            onClick={() => setSvcDraft(s)}
                          >
                            Edit
                          </Button>
                          <Button
                            variant="ghost"
                            className="!px-2 !py-1 !text-xs !text-rose-600"
                            disabled={busy}
                            onClick={() =>
                              act(() => banquet.deleteService(s.name))
                            }
                          >
                            <Trash2 className="size-3.5" />
                          </Button>
                        </div>
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          ))}
      </CardContent>

      {menuDraft && (
        <MenuSheet
          draft={menuDraft}
          busy={busy}
          onClose={() => setMenuDraft(null)}
          onSave={async (payload) => {
            await act(() => banquet.saveMenu(payload))
            setMenuDraft(null)
          }}
        />
      )}
      {dishDraft && (
        <DishSheet
          draft={dishDraft}
          busy={busy}
          onClose={() => setDishDraft(null)}
          onSave={async (payload) => {
            await act(() => banquet.saveDish(payload))
            setDishDraft(null)
          }}
        />
      )}
      {svcDraft && (
        <ServiceSheet
          draft={svcDraft}
          busy={busy}
          onClose={() => setSvcDraft(null)}
          onSave={async (payload) => {
            await act(() => banquet.saveService(payload))
            setSvcDraft(null)
          }}
        />
      )}
    </Card>
  )
}

/* ── the menu editor ──────────────────────────────────────────────────── */

function MenuSheet({
  draft,
  busy,
  onClose,
  onSave,
}: {
  draft: Partial<BanquetMenu>
  busy: boolean
  onClose: () => void
  onSave: (payload: Record<string, unknown>) => void
}) {
  const [m, setM] = useState<Partial<BanquetMenu>>(draft)
  const [courses, setCourses] = useState<Partial<BanquetMenuCourse>[]>(
    draft.courses ?? [],
  )
  const set = (k: keyof BanquetMenu, v: unknown) =>
    setM((x) => ({ ...x, [k]: v }))
  const editCourse = (i: number, patch: Partial<BanquetMenuCourse>) =>
    setCourses((cs) => cs.map((c, x) => (x === i ? { ...c, ...patch } : c)))

  return (
    <Sheet
      title={draft.name ? "Edit menu package" : "New menu package"}
      description="Priced per plate. The courses print on the event order, so the kitchen reads the same sheet the customer signed."
      onClose={onClose}
      wide
      footer={
        <div className="flex justify-end gap-2">
          <Button variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button
            disabled={busy || !(m.menu_name ?? "").trim()}
            onClick={() =>
              onSave({
                name: draft.name ?? null,
                menu_name: m.menu_name,
                menu_code: m.menu_code ?? null,
                meal_period: m.meal_period,
                food_type: m.food_type,
                service_style: m.service_style,
                cuisine: m.cuisine ?? null,
                rate_per_pax: Number(m.rate_per_pax) || 0,
                min_pax: Number(m.min_pax) || 0,
                gst_rate: Number(m.gst_rate) || 0,
                inclusions: m.inclusions ?? null,
                exclusions: m.exclusions ?? null,
                courses: courses.filter((c) => (c.course ?? "").trim()),
              })
            }
          >
            Save menu
          </Button>
        </div>
      }
    >
      <div className="space-y-4">
        <div className="grid gap-3 sm:grid-cols-3">
          <Field label="Menu name" className="sm:col-span-2">
            <input
              className={inputCls}
              placeholder="Silver Veg Buffet"
              value={m.menu_name ?? ""}
              onChange={(e) => set("menu_name", e.target.value)}
            />
          </Field>
          <Field label="Code" hint="Prints on the event order">
            <input
              className={inputCls}
              placeholder="SVB"
              value={m.menu_code ?? ""}
              onChange={(e) => set("menu_code", e.target.value)}
            />
          </Field>
          <Field label="Meal">
            <Select
              value={m.meal_period ?? "Dinner"}
              onChange={(v) => set("meal_period", v)}
              options={MEAL_PERIODS}
            />
          </Field>
          <Field label="Food type">
            <Select
              value={m.food_type ?? "Veg"}
              onChange={(v) => set("food_type", v)}
              options={FOOD_TYPES}
            />
          </Field>
          <Field label="Served as">
            <Select
              value={m.service_style ?? "Buffet"}
              onChange={(v) => set("service_style", v)}
              options={SERVICE_STYLES}
            />
          </Field>
          <Field label="Cuisine">
            <input
              className={inputCls}
              placeholder="North Indian"
              value={m.cuisine ?? ""}
              onChange={(e) => set("cuisine", e.target.value)}
            />
          </Field>
          <Field label="Rate per pax">
            <input
              type="number"
              className={inputCls}
              value={m.rate_per_pax ?? 0}
              onChange={(e) => set("rate_per_pax", e.target.value)}
            />
          </Field>
          <Field
            label="Minimum pax"
            hint="Below this it still bills for the minimum"
          >
            <input
              type="number"
              className={inputCls}
              value={m.min_pax ?? 0}
              onChange={(e) => set("min_pax", e.target.value)}
            />
          </Field>
          <Field label={`${taxLabel()} %`}>
            <input
              type="number"
              className={inputCls}
              value={m.gst_rate ?? 5}
              onChange={(e) => set("gst_rate", e.target.value)}
            />
          </Field>
        </div>

        <div>
          <div className="mb-2 flex items-center justify-between">
            <p className="text-xs font-medium text-zinc-500">Courses</p>
            <Button
              variant="outline"
              className="!px-2 !py-1 !text-xs"
              onClick={() =>
                setCourses((cs) => [
                  ...cs,
                  { course: "", dishes: "", choice_of: 0, is_live_counter: 0 },
                ])
              }
            >
              <Plus className="size-3.5" />
              Course
            </Button>
          </div>
          {courses.length === 0 ? (
            <p className="text-sm text-zinc-400">
              No courses yet - Starters, Main course, Live counter, Desserts.
            </p>
          ) : (
            <div className="space-y-2">
              {courses.map((c, i) => (
                <div
                  key={i}
                  className="grid gap-2 rounded-lg border border-zinc-200 px-3 py-2 sm:grid-cols-[10rem_1fr_5rem_auto_auto]"
                >
                  <input
                    className={inputCls}
                    placeholder="Starters (Veg)"
                    value={c.course ?? ""}
                    onChange={(e) => editCourse(i, { course: e.target.value })}
                  />
                  <input
                    className={inputCls}
                    placeholder="Paneer tikka, Hara bhara kebab, Corn seekh"
                    value={c.dishes ?? ""}
                    onChange={(e) => editCourse(i, { dishes: e.target.value })}
                  />
                  <input
                    type="number"
                    className={inputCls}
                    placeholder="Pick"
                    title="0 = all served. N = the guest chooses N."
                    value={c.choice_of ?? 0}
                    onChange={(e) =>
                      editCourse(i, { choice_of: Number(e.target.value) })
                    }
                  />
                  <label className="flex items-center gap-1.5 text-xs text-zinc-500">
                    <input
                      type="checkbox"
                      className="size-4 accent-brand-600"
                      checked={Boolean(c.is_live_counter)}
                      onChange={(e) =>
                        editCourse(i, {
                          is_live_counter: e.target.checked ? 1 : 0,
                        })
                      }
                    />
                    Live
                  </label>
                  <button
                    className="text-zinc-300 hover:text-rose-600"
                    onClick={() =>
                      setCourses((cs) => cs.filter((_, x) => x !== i))
                    }
                    aria-label="Remove course"
                  >
                    <Trash2 className="size-4" />
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="grid gap-3 sm:grid-cols-2">
          <Field label="What the plate price covers">
            <textarea
              rows={2}
              className={inputCls}
              placeholder="Crockery, service staff, two soft drinks per head"
              value={m.inclusions ?? ""}
              onChange={(e) => set("inclusions", e.target.value)}
            />
          </Field>
          <Field label="What it doesn't">
            <textarea
              rows={2}
              className={inputCls}
              placeholder="Alcohol, live counters, taxes"
              value={m.exclusions ?? ""}
              onChange={(e) => set("exclusions", e.target.value)}
            />
          </Field>
        </div>
      </div>
    </Sheet>
  )
}

/* ── the service editor ───────────────────────────────────────────────── */

function ServiceSheet({
  draft,
  busy,
  onClose,
  onSave,
}: {
  draft: Partial<BanquetService>
  busy: boolean
  onClose: () => void
  onSave: (payload: Record<string, unknown>) => void
}) {
  const [s, setS] = useState<Partial<BanquetService>>(draft)
  const set = (k: keyof BanquetService, v: unknown) =>
    setS((x) => ({ ...x, [k]: v }))

  return (
    <Sheet
      title={draft.name ? "Edit service" : "New service"}
      description="Everything that isn't food: AV, decor, entertainment, furniture, staffing, bar."
      onClose={onClose}
      footer={
        <div className="flex justify-end gap-2">
          <Button variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button
            disabled={busy || !(s.item_name ?? "").trim()}
            onClick={() =>
              onSave({
                name: draft.name ?? null,
                item_name: s.item_name,
                category: s.category,
                uom: s.uom,
                rate: Number(s.rate) || 0,
                gst_rate: Number(s.gst_rate) || 0,
                chargeable: s.chargeable ? 1 : 0,
                is_alcohol: s.is_alcohol ? 1 : 0,
                on_pack_list: s.on_pack_list ? 1 : 0,
                description: s.description ?? null,
              })
            }
          >
            Save service
          </Button>
        </div>
      }
    >
      <div className="space-y-3">
        <Field label="What is it">
          <input
            className={inputCls}
            placeholder="LED wall 12×8"
            value={s.item_name ?? ""}
            onChange={(e) => set("item_name", e.target.value)}
          />
        </Field>
        <div className="grid grid-cols-2 gap-3">
          <Field label="Category">
            <Select
              value={s.category ?? "Audio Visual"}
              onChange={(v) => set("category", v)}
              options={SERVICE_CATEGORIES}
            />
          </Field>
          <Field label="Charged">
            <Select
              value={s.uom ?? "Per Event"}
              onChange={(v) => set("uom", v)}
              options={CATALOGUE_UOMS}
            />
          </Field>
          <Field label="Rate">
            <input
              type="number"
              className={inputCls}
              value={s.rate ?? 0}
              onChange={(e) => set("rate", e.target.value)}
            />
          </Field>
          <Field label={`${taxLabel()} %`}>
            <input
              type="number"
              className={inputCls}
              value={s.gst_rate ?? 18}
              onChange={(e) => set("gst_rate", e.target.value)}
            />
          </Field>
        </div>
        <Field label="Description">
          <textarea
            rows={2}
            className={inputCls}
            value={s.description ?? ""}
            onChange={(e) => set("description", e.target.value)}
          />
        </Field>
        <div className="space-y-2 rounded-lg border border-zinc-200 px-3 py-2">
          <Toggle
            checked={Boolean(s.chargeable)}
            onChange={(v) => set("chargeable", v ? 1 : 0)}
            label="Chargeable by default"
            hint="Off = thrown in as standard. It still prints on the event order and the pack list; any function can override it."
          />
          <Toggle
            checked={Boolean(s.on_pack_list)}
            onChange={(v) => set("on_pack_list", v ? 1 : 0)}
            label="Goes on the pack list"
            hint="A physical thing someone has to carry to the hall."
          />
          <Toggle
            checked={Boolean(s.is_alcohol)}
            onChange={(v) => set("is_alcohol", v ? 1 : 0)}
            label="Alcohol"
            hint="Alcohol never rides a company or group folio - it settles separately."
          />
        </div>
      </div>
    </Sheet>
  )
}

function Toggle({
  checked,
  onChange,
  label,
  hint,
}: {
  checked: boolean
  onChange: (v: boolean) => void
  label: string
  hint: string
}) {
  return (
    <label className="flex items-start gap-2">
      <input
        type="checkbox"
        className="mt-0.5 size-4 accent-brand-600"
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
      />
      <span>
        <span className="block text-sm font-medium text-zinc-700">{label}</span>
        <span className="block text-xs text-zinc-400">{hint}</span>
      </span>
    </label>
  )
}

/* ── the dish library ─────────────────────────────────────────────────── */

/** The buy side. A dish with no recipe is free, and so is the margin it
 *  reports — which is exactly how a banquet ends up losing money on paper
 *  it thought it made. Recipes here cost from the same ingredient master
 *  the restaurant uses, so one price change moves both kitchens. */
function DishLibrary({
  dishes,
  canEdit,
  busy,
  onChanged,
  onEdit,
  onDelete,
}: {
  dishes: BanquetDish[] | null
  canEdit: boolean
  busy: boolean
  onChanged: () => void
  onEdit: (d: BanquetDish) => void
  onDelete: (name: string) => void
}) {
  const [error, setError] = useState<string | null>(null)
  const [working, setWorking] = useState(false)
  const [changes, setChanges] = useState<string | null>(null)

  if (!dishes) return <Empty>Loading…</Empty>

  const uncosted = dishes.filter((d) => !d.cost_per_portion)
  const byCourse = dishes.reduce<Record<string, BanquetDish[]>>((acc, d) => {
    ;(acc[d.course_type] ??= []).push(d)
    return acc
  }, {})

  async function recost() {
    setWorking(true)
    setError(null)
    try {
      const out = await banquet.recostDishes()
      setChanges(
        out.recosted
          ? `${out.recosted} dish${out.recosted === 1 ? "" : "es"} re-costed.`
          : "Every dish already matches today's prices.",
      )
      onChanged()
    } catch (e) {
      setError(serverError(e))
    } finally {
      setWorking(false)
    }
  }

  return (
    <div className="space-y-4">
      <ErrorNote error={error} />
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm text-zinc-500">
          {dishes.length} dish{dishes.length === 1 ? "" : "es"}
          {uncosted.length > 0 && (
            <span className="text-amber-700">
              {" "}
              · {uncosted.length} with no recipe, so they cost nothing
            </span>
          )}
        </p>
        {canEdit && (
          <Button
            variant="outline"
            disabled={busy || working}
            onClick={recost}
            title="Recomputes every dish as the sum of its recipe: each ingredient's quantity per portion times that ingredient's current cost per unit."
          >
            Re-cost from today&apos;s ingredient prices
          </Button>
        )}
      </div>

      {/* the number on every card is arithmetic, not an estimate - say so */}
      <p className="rounded-lg bg-zinc-50 px-3 py-2 text-xs text-zinc-500">
        A dish costs the sum of its recipe: for each ingredient,{" "}
        <span className="font-medium text-zinc-700">
          quantity per portion x that ingredient&apos;s cost per unit
        </span>
        . Re-costing walks every dish and recomputes it at today&apos;s
        ingredient prices, so a quote is never priced off last season&apos;s
        onions.
      </p>
      {changes && (
        <p className="text-xs text-emerald-700">{changes}</p>
      )}

      {dishes.length === 0 ? (
        <Empty>
          No dishes yet. Add them here, give each one a recipe, and every menu
          built from them knows what it costs to serve.
        </Empty>
      ) : (
        <div className="space-y-5">
          {Object.entries(byCourse).map(([course, rows]) => (
            <div key={course}>
              <h3 className="mb-2 text-xs font-semibold uppercase tracking-wider text-zinc-400">
                {course}
              </h3>
              <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
                {rows.map((d) => (
                  <div
                    key={d.name}
                    className="rounded-lg border border-zinc-200 px-3 py-2"
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div className="min-w-0">
                        <p className="flex items-center gap-1.5 font-medium">
                          <span
                            className={
                              "size-2 shrink-0 rounded-full " +
                              (d.food_type === "Non-Veg"
                                ? "bg-rose-500"
                                : d.food_type === "Egg"
                                  ? "bg-amber-500"
                                  : "bg-emerald-500")
                            }
                          />
                          {d.dish_name}
                        </p>
                        <p className="text-xs text-zinc-400">
                          {d.kitchen}
                          {d.portion_per_pax !== 1
                            ? ` · ${d.portion_per_pax}/pax`
                            : ""}
                          {d.allergens ? ` · ${d.allergens}` : ""}
                        </p>
                      </div>
                      <div className="shrink-0 text-right">
                        {d.cost_per_portion ? (
                          <p className="tabular-nums">
                            {inr(d.cost_per_portion)}
                            <span className="text-xs text-zinc-400">
                              /portion
                            </span>
                          </p>
                        ) : (
                          <p className="text-xs text-amber-700">no recipe</p>
                        )}
                      </div>
                    </div>
                    <div className="mt-1 flex items-center justify-between gap-2">
                      <p className="text-xs text-zinc-400">
                        {d.recipe.length
                          ? `${d.recipe.length} ingredient${d.recipe.length === 1 ? "" : "s"}`
                          : "no recipe"}
                      </p>
                      {canEdit && (
                        <span className="flex gap-1">
                          <button
                            className="text-xs font-medium text-brand-700 hover:underline"
                            onClick={() => onEdit(d)}
                          >
                            Edit
                          </button>
                          <button
                            className="text-zinc-300 hover:text-rose-600"
                            aria-label={`Delete ${d.dish_name}`}
                            disabled={busy}
                            onClick={() => onDelete(d.name)}
                          >
                            <Trash2 className="size-3.5" />
                          </button>
                        </span>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

/* ── the dish editor ──────────────────────────────────────────────────── */

/** A dish is only worth what its recipe says. This is where that recipe
 *  gets written, and the cost adds up line by line as you type — so the
 *  person entering it can see immediately whether the number looks right,
 *  rather than discovering at month end that the paneer was priced per
 *  gram. */
function DishSheet({
  draft,
  busy,
  onClose,
  onSave,
}: {
  draft: Partial<BanquetDish>
  busy: boolean
  onClose: () => void
  onSave: (payload: Record<string, unknown>) => void
}) {
  const [d, setD] = useState<Partial<BanquetDish>>(draft)
  const [recipe, setRecipe] = useState<Partial<RecipeRow>[]>(draft.recipe ?? [])
  const [ingredients, setIngredients] = useState<Row[]>([])
  const set = (k: keyof BanquetDish, v: unknown) =>
    setD((x) => ({ ...x, [k]: v }))

  useEffect(() => {
    listResource("Ingredient", {
      fields: ["name", "ingredient_name", "uom", "cost_per_unit"],
      filters: [["property", "=", getCurrentProperty()], ["is_active", "=", 1]],
      orderBy: "ingredient_name asc",
      limit: 500,
    })
      .then(setIngredients)
      .catch(() => {})
  }, [])

  const priceOf = (name?: string) =>
    Number(ingredients.find((i) => i.name === name)?.cost_per_unit ?? 0)
  const uomOf = (name?: string) =>
    String(ingredients.find((i) => i.name === name)?.uom ?? "")

  const cost = recipe.reduce(
    (sum, r) => sum + Number(r.qty || 0) * priceOf(r.ingredient),
    0,
  )

  return (
    <Sheet
      title={draft.name ? `Edit ${draft.dish_name}` : "New dish"}
      description="What it is, which section cooks it, and what one portion costs to make."
      onClose={onClose}
      wide
      footer={
        <div className="flex flex-wrap items-center justify-between gap-3">
          <span className="text-sm text-zinc-500">
            {recipe.length
              ? `Costs ${inr(cost)} a portion`
              : "No recipe yet — this dish will cost nothing"}
          </span>
          <div className="flex gap-2">
            <Button variant="outline" onClick={onClose}>
              Cancel
            </Button>
            <Button
              disabled={busy || !(d.dish_name ?? "").trim()}
              onClick={() =>
                onSave({
                  name: draft.name ?? null,
                  dish_name: d.dish_name,
                  course_type: d.course_type,
                  food_type: d.food_type,
                  kitchen: d.kitchen,
                  portion_per_pax: Number(d.portion_per_pax) || 1,
                  allergens: d.allergens ?? null,
                  description: d.description ?? null,
                  recipe: recipe
                    .filter((r) => r.ingredient && Number(r.qty) > 0)
                    .map((r) => ({
                      ingredient: r.ingredient,
                      qty: Number(r.qty),
                      note: r.note ?? null,
                    })),
                })
              }
            >
              Save dish
            </Button>
          </div>
        </div>
      }
    >
      <div className="space-y-4">
        <div className="grid gap-3 sm:grid-cols-3">
          <Field label="Dish name" className="sm:col-span-2">
            <input
              className={inputCls}
              placeholder="Paneer Tikka"
              value={d.dish_name ?? ""}
              onChange={(e) => set("dish_name", e.target.value)}
            />
          </Field>
          <Field label="Course">
            <Select
              value={d.course_type ?? "Main Course"}
              onChange={(v) => set("course_type", v)}
              options={DISH_COURSES}
            />
          </Field>
          <Field label="Veg / non-veg">
            <Select
              value={d.food_type ?? "Veg"}
              onChange={(v) => set("food_type", v)}
              options={["Veg", "Non-Veg", "Jain", "Vegan", "Egg"]}
            />
          </Field>
          <Field label="Which section cooks it" hint="Splits the event order">
            <Select
              value={d.kitchen ?? "Main Kitchen"}
              onChange={(v) => set("kitchen", v)}
              options={KITCHENS}
            />
          </Field>
          <Field
            label="Portions per head"
            hint="0.5 means one portion feeds two"
          >
            <input
              type="number"
              step="0.1"
              className={inputCls}
              value={d.portion_per_pax ?? 1}
              onChange={(e) => set("portion_per_pax", e.target.value)}
            />
          </Field>
          <Field label="Allergens" className="sm:col-span-2">
            <input
              className={inputCls}
              placeholder="Nuts, dairy"
              value={d.allergens ?? ""}
              onChange={(e) => set("allergens", e.target.value)}
            />
          </Field>
        </div>

        <div>
          <div className="mb-2 flex items-center justify-between">
            <div>
              <p className="text-xs font-medium text-zinc-500">
                Recipe — one portion
              </p>
              <p className="text-[11px] text-zinc-400">
                Quantities are per portion, in each ingredient&apos;s own unit.
              </p>
            </div>
            <Button
              variant="outline"
              className="!px-2 !py-1 !text-xs"
              onClick={() =>
                setRecipe((rs) => [...rs, { ingredient: "", qty: 0 }])
              }
            >
              <Plus className="size-3.5" />
              Ingredient
            </Button>
          </div>

          {ingredients.length === 0 ? (
            <p className="rounded-lg bg-amber-50 px-3 py-2 text-sm text-amber-800">
              No ingredients on this property yet. Add them under Kitchen
              Inventory first — a dish can only cost what its ingredients
              cost.
            </p>
          ) : recipe.length === 0 ? (
            <p className="text-sm text-zinc-400">
              No recipe yet. Without one the dish costs nothing, and every
              quote built on it will look more profitable than it is.
            </p>
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-zinc-200 text-left text-xs uppercase tracking-wider text-zinc-400">
                  <th className="py-1.5 font-medium">Ingredient</th>
                  <th className="w-24 py-1.5 text-right font-medium">Qty</th>
                  <th className="w-28 py-1.5 text-right font-medium">Price</th>
                  <th className="w-24 py-1.5 text-right font-medium">Cost</th>
                  <th className="w-8" />
                </tr>
              </thead>
              <tbody>
                {recipe.map((r, i) => (
                  <tr key={i} className="border-b border-zinc-100">
                    <td className="py-1.5 pr-2">
                      <select
                        className={inputCls + " !py-1"}
                        value={r.ingredient ?? ""}
                        onChange={(e) =>
                          setRecipe((rs) =>
                            rs.map((x, n) =>
                              n === i ? { ...x, ingredient: e.target.value } : x,
                            ),
                          )
                        }
                      >
                        <option value="">Choose…</option>
                        {ingredients.map((ing) => (
                          <option key={ing.name} value={ing.name}>
                            {String(ing.ingredient_name)}
                          </option>
                        ))}
                      </select>
                    </td>
                    <td className="py-1.5 pr-2">
                      <input
                        type="number"
                        step="0.001"
                        className={inputCls + " !py-1 text-right"}
                        value={r.qty ?? ""}
                        onChange={(e) =>
                          setRecipe((rs) =>
                            rs.map((x, n) =>
                              n === i
                                ? { ...x, qty: Number(e.target.value) }
                                : x,
                            ),
                          )
                        }
                      />
                    </td>
                    <td className="py-1.5 pr-2 text-right text-xs tabular-nums text-zinc-400">
                      {r.ingredient
                        ? `${inr(priceOf(r.ingredient))}/${uomOf(r.ingredient)}`
                        : "—"}
                    </td>
                    <td className="py-1.5 pr-2 text-right tabular-nums">
                      {inr(Number(r.qty || 0) * priceOf(r.ingredient))}
                    </td>
                    <td className="py-1.5 text-right">
                      <button
                        className="text-zinc-300 hover:text-rose-600"
                        aria-label="Remove ingredient"
                        onClick={() =>
                          setRecipe((rs) => rs.filter((_, n) => n !== i))
                        }
                      >
                        <Trash2 className="size-4" />
                      </button>
                    </td>
                  </tr>
                ))}
                <tr>
                  <td colSpan={3} className="py-2 text-right font-medium">
                    One portion costs
                  </td>
                  <td className="py-2 text-right font-semibold tabular-nums">
                    {inr(cost)}
                  </td>
                  <td />
                </tr>
              </tbody>
            </table>
          )}
        </div>
      </div>
    </Sheet>
  )
}

const DISH_COURSES = [
  "Welcome Drink",
  "Starters",
  "Soup",
  "Salad",
  "Main Course",
  "Breads",
  "Rice",
  "Accompaniments",
  "Live Counter",
  "Dessert",
  "Beverage",
  "Other",
]
const KITCHENS = [
  "Main Kitchen",
  "Tandoor",
  "Chinese",
  "Continental",
  "Bakery",
  "Cold Kitchen",
  "Live Counter",
  "Outsourced",
]
