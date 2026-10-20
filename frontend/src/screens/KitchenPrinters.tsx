/** F&B kitchen printers: add each printer, how it connects, paper/copies,
 *  fallback, and which outlets × stations it prints KOTs for. */

import { useCallback, useEffect, useState } from "react"
import { Link } from "react-router-dom"
import { Printer } from "lucide-react"
import { call, getCurrentProperty } from "../lib/api"
import { useAuth } from "../lib/auth"
import { useT } from "../lib/i18n"
import { serverError } from "../lib/resource"
import { Button } from "../components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card"

const WRITE_ROLES = ["Finance", "Hotel Admin", "System Manager", "Administrator"]
const STATIONS = ["Kitchen", "Tandoor", "Grill", "Fryer", "Bar"]

const inputCls =
  "w-full rounded-lg border border-zinc-300 bg-white px-3 py-1.5 text-sm " +
  "focus:outline-2 focus:outline-offset-1 focus:outline-brand-600"

interface KitchenPrinter {
  name: string
  printer_name: string
  connection: "Print station" | "Direct IP"
  paper_width: string
  copies: number
  ip_address: string | null
  port: number | null
  fallback_printer: string | null
  disabled: 0 | 1
  prints_kots: 0 | 1
  prints_bills: 0 | 1
  last_seen: string | null
  last_printed: string | null
  last_error: string | null
  queued: number
  failed_today: number
  online: boolean | null
  routes: { outlet: string; prep_station: string }[]
}

type PrinterDraft = Omit<
  KitchenPrinter,
  "name" | "last_seen" | "last_printed" | "last_error" | "queued" | "failed_today" | "online"
> & { name?: string }

const blankPrinter = (): PrinterDraft => ({
  printer_name: "",
  connection: "Print station",
  paper_width: "80 mm",
  copies: 1,
  ip_address: "",
  port: 9100,
  fallback_printer: null,
  disabled: 0,
  prints_kots: 1,
  prints_bills: 0,
  routes: [],
})

export default function KitchenPrinters() {
  const { t } = useT()
  const { roles } = useAuth()
  const canEdit = roles.some((r) => WRITE_ROLES.includes(r))
  const property = getCurrentProperty()

  const [printers, setPrinters] = useState<KitchenPrinter[]>([])
  const [outlets, setOutlets] = useState<{ name: string; outlet_name: string }[]>([])
  const [form, setForm] = useState<PrinterDraft | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const [note, setNote] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const load = useCallback(() => {
    if (!property) {
      setErr(t("Pick a property first."))
      setPrinters([])
      return
    }
    call<KitchenPrinter[]>("kamra.printing.printers", { property })
      .then((rows) => {
        setPrinters(rows)
        setErr(null)
      })
      .catch((e) => setErr(serverError(e)))
  }, [property, t])

  useEffect(() => {
    load()
    if (!property) return
    call<{ name: string; outlet_name: string }[]>("kamra.pos.outlets", { property })
      .then(setOutlets)
      .catch((e) => setErr(serverError(e)))
    const tm = setInterval(load, 15_000)
    return () => clearInterval(tm)
  }, [load, property])

  const outletName = (o: string) =>
    outlets.find((x) => x.name === o)?.outlet_name || o
  const has = (o: string, st: string) =>
    !!form?.routes.some((r) => r.outlet === o && r.prep_station === st)

  function toggle(o: string, st: string) {
    if (!form || !canEdit) return
    let routes = form.routes
    if (st === "") {
      routes = has(o, "")
        ? routes.filter((r) => r.outlet !== o)
        : [...routes.filter((r) => r.outlet !== o), { outlet: o, prep_station: "" }]
    } else {
      routes = routes.filter((r) => !(r.outlet === o && r.prep_station === ""))
      routes = has(o, st)
        ? routes.filter((r) => !(r.outlet === o && r.prep_station === st))
        : [...routes, { outlet: o, prep_station: st }]
    }
    setForm({ ...form, routes })
  }

  async function save() {
    if (!form || !property || !canEdit) return
    setBusy(true)
    setErr(null)
    try {
      const { name, ...printer } = form
      await call("kamra.printing.save_printer", {
        property,
        name: name || null,
        printer: JSON.stringify(printer),
      })
      setForm(null)
      setNote(t("Printer saved."))
      load()
    } catch (e) {
      setErr(serverError(e))
    } finally {
      setBusy(false)
    }
  }

  async function remove(p: KitchenPrinter) {
    if (!canEdit) return
    setErr(null)
    try {
      await call("kamra.printing.delete_printer", { name: p.name })
      setNote(t("Printer removed."))
      load()
    } catch (e) {
      setErr(serverError(e))
    }
  }

  async function test(p: KitchenPrinter) {
    if (!canEdit) return
    setErr(null)
    try {
      await call("kamra.printing.test_print", { name: p.name })
      setNote(
        p.connection === "Print station"
          ? t("Test page sent. It prints on the kitchen screen set to print for {printer}.", {
              printer: p.printer_name,
            })
          : t("Test page sent to {ip}.", { ip: p.ip_address || "" }),
      )
      setTimeout(load, 4000)
    } catch (e) {
      setErr(serverError(e))
    }
  }

  const status = (p: KitchenPrinter) => {
    if (p.disabled) return { tone: "bg-zinc-300", text: t("Disabled") }
    if (p.last_error && p.failed_today) return { tone: "bg-rose-500", text: p.last_error }
    if (p.connection === "Print station") {
      return p.online
        ? { tone: "bg-emerald-500", text: t("A kitchen screen is printing for it") }
        : { tone: "bg-amber-500", text: t("No kitchen screen is printing for it right now") }
    }
    return p.last_printed
      ? { tone: "bg-emerald-500", text: t("Last printed {at}", { at: p.last_printed.slice(0, 16) }) }
      : { tone: "bg-zinc-300", text: t("Not used yet") }
  }

  return (
    <div className="mx-auto max-w-5xl space-y-4 p-4 sm:p-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="flex items-center gap-2 text-xl font-semibold text-zinc-900">
            <Printer className="size-5 text-zinc-500" aria-hidden />
            {t("Kitchen printers")}
          </h1>
          <p className="mt-1 max-w-2xl text-sm text-zinc-500">
            {t(
              "Which printer gets which KOTs. Two restaurants can share a kitchen printer, and the bar's drinks can print at the bar. With no printers here, each till prints its own KOTs.",
            )}
          </p>
          <p className="mt-1 text-xs text-zinc-400">
            {t("On a kitchen device, open")}{" "}
            <Link to="/kitchen" className="text-brand-700 underline-offset-2 hover:underline">
              {t("Kitchen Display")}
            </Link>{" "}
            {t("and choose Print for this printer.")}
          </p>
        </div>
        {canEdit && !form && (
          <Button
            variant="outline"
            className="shrink-0 whitespace-nowrap"
            onClick={() => {
              setForm(blankPrinter())
              setNote(null)
            }}
          >
            {t("Add printer")}
          </Button>
        )}
      </div>

      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-base">{t("Printers at this property")}</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          {err && <p className="text-sm text-rose-700">{err}</p>}
          {note && <p className="text-sm text-emerald-700">{note}</p>}

          {!form && !err && printers.length === 0 && (
            <div className="rounded-lg border border-dashed border-zinc-300 bg-zinc-50 px-4 py-6 text-center">
              <p className="text-sm font-medium text-zinc-800">
                {t("No kitchen printers yet.")}
              </p>
              <p className="mt-1 text-xs text-zinc-500">
                {t(
                  "Add a printer to route KOTs by outlet and station. Status (online, waiting, failed) shows here once a kitchen screen is set to Print for it.",
                )}
              </p>
              {canEdit && (
                <Button
                  className="mt-3"
                  variant="outline"
                  onClick={() => {
                    setForm(blankPrinter())
                    setNote(null)
                  }}
                >
                  {t("Add printer")}
                </Button>
              )}
            </div>
          )}

          {!form &&
            printers.map((p) => {
              const st = status(p)
              return (
                <div
                  key={p.name}
                  className="flex flex-wrap items-start justify-between gap-3 rounded-lg border border-zinc-200 px-3 py-2.5"
                >
                  <div className="min-w-0">
                    <div className="flex items-center gap-2 text-sm font-semibold text-zinc-900">
                      <span className={`size-2 shrink-0 rounded-full ${st.tone}`} title={st.text} />
                      {p.printer_name}
                      <span className="text-xs font-normal text-zinc-400">
                        {p.connection === "Direct IP"
                          ? `${p.ip_address}:${p.port || 9100}`
                          : t("Print station")}{" "}
                        · {p.paper_width}
                        {p.copies > 1 ? ` · ×${p.copies}` : ""}
                      </span>
                    </div>
                    <p className="mt-0.5 text-xs text-zinc-500">
                      {p.routes.length
                        ? p.routes
                            .map(
                              (r) =>
                                `${outletName(r.outlet)} · ${r.prep_station || t("all stations")}`,
                            )
                            .join(", ")
                        : t("Prints nothing yet - choose outlets and stations.")}
                    </p>
                    <p className="mt-0.5 text-xs text-zinc-400">
                      {st.text}
                      {p.queued ? ` · ${t("{n} waiting", { n: p.queued })}` : ""}
                      {p.failed_today ? ` · ${t("{n} failed today", { n: p.failed_today })}` : ""}
                    </p>
                  </div>
                  {canEdit && (
                    <div className="flex shrink-0 gap-1.5">
                      <Button variant="ghost" onClick={() => test(p)}>
                        {t("Test print")}
                      </Button>
                      <Button
                        variant="ghost"
                        onClick={() => {
                          setNote(null)
                          setForm({
                            name: p.name,
                            printer_name: p.printer_name,
                            connection: p.connection,
                            paper_width: p.paper_width,
                            copies: p.copies,
                            ip_address: p.ip_address || "",
                            port: p.port || 9100,
                            fallback_printer: p.fallback_printer,
                            disabled: p.disabled,
                            prints_kots: p.prints_kots ?? 1,
                            prints_bills: p.prints_bills ?? 0,
                            routes: p.routes,
                          })
                        }}
                      >
                        {t("Edit")}
                      </Button>
                      <Button variant="ghost" onClick={() => remove(p)}>
                        {t("Remove")}
                      </Button>
                    </div>
                  )}
                </div>
              )
            })}

          {form && canEdit && (
            <div className="space-y-4 rounded-lg border border-zinc-200 p-3">
              <div className="grid gap-3 sm:grid-cols-2">
                <label className="block text-sm">
                  <span className="mb-1 block font-medium text-zinc-700">{t("Printer name")}</span>
                  <input
                    className={inputCls}
                    value={form.printer_name}
                    placeholder={t("Main kitchen")}
                    onChange={(e) => setForm({ ...form, printer_name: e.target.value })}
                  />
                </label>
                <label className="block text-sm">
                  <span className="mb-1 block font-medium text-zinc-700">{t("Connection")}</span>
                  <select
                    className={inputCls}
                    value={form.connection}
                    onChange={(e) =>
                      setForm({
                        ...form,
                        connection: e.target.value as PrinterDraft["connection"],
                      })
                    }
                  >
                    <option value="Print station">
                      {t("Print station (a kitchen screen prints it)")}
                    </option>
                    <option value="Direct IP">
                      {t("Direct IP (Kamra on the hotel network)")}
                    </option>
                  </select>
                  <span className="mt-1 block text-xs text-zinc-400">
                    {form.connection === "Print station"
                      ? t(
                          "Any printer - USB, network or Bluetooth - attached to a device in the kitchen. On that device, open the kitchen display and pick this printer under Print for.",
                        )
                      : t(
                          "Kamra sends the ticket straight to the printer's network address. Only works when the Kamra server is on the same network as the printer, not on a cloud server.",
                        )}
                  </span>
                </label>
                {form.connection === "Direct IP" && (
                  <>
                    <label className="block text-sm">
                      <span className="mb-1 block font-medium text-zinc-700">{t("IP address")}</span>
                      <input
                        className={inputCls}
                        value={form.ip_address || ""}
                        placeholder="192.168.1.50"
                        onChange={(e) => setForm({ ...form, ip_address: e.target.value })}
                      />
                    </label>
                    <label className="block text-sm">
                      <span className="mb-1 block font-medium text-zinc-700">{t("Port")}</span>
                      <input
                        className={inputCls}
                        type="number"
                        value={form.port ?? 9100}
                        onChange={(e) =>
                          setForm({ ...form, port: Number(e.target.value) || 9100 })
                        }
                      />
                    </label>
                  </>
                )}
                <label className="block text-sm">
                  <span className="mb-1 block font-medium text-zinc-700">{t("Paper width")}</span>
                  <select
                    className={inputCls}
                    value={form.paper_width}
                    onChange={(e) => setForm({ ...form, paper_width: e.target.value })}
                  >
                    <option>80 mm</option>
                    <option>58 mm</option>
                  </select>
                </label>
                <label className="block text-sm">
                  <span className="mb-1 block font-medium text-zinc-700">{t("Copies")}</span>
                  <select
                    className={inputCls}
                    value={form.copies}
                    onChange={(e) => setForm({ ...form, copies: Number(e.target.value) })}
                  >
                    {[1, 2, 3].map((n) => (
                      <option key={n} value={n}>
                        {n}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="block text-sm">
                  <span className="mb-1 block font-medium text-zinc-700">
                    {t("Fallback printer")}
                  </span>
                  <select
                    className={inputCls}
                    value={form.fallback_printer || ""}
                    onChange={(e) =>
                      setForm({ ...form, fallback_printer: e.target.value || null })
                    }
                  >
                    <option value="">{t("None")}</option>
                    {printers
                      .filter((p) => p.name !== form.name)
                      .map((p) => (
                        <option key={p.name} value={p.name}>
                          {p.printer_name}
                        </option>
                      ))}
                  </select>
                  <span className="mt-1 block text-xs text-zinc-400">
                    {t("Where a ticket goes if this printer fails.")}
                  </span>
                </label>
                <div className="sm:col-span-2">
                  <p className="mb-1 text-sm font-medium text-zinc-700">{t("This printer prints")}</p>
                  <div className="flex flex-wrap gap-4 text-sm">
                    <label className="flex items-center gap-2">
                      <input
                        type="checkbox"
                        checked={!!form.prints_kots}
                        onChange={(e) =>
                          setForm({ ...form, prints_kots: e.target.checked ? 1 : 0 })
                        }
                      />
                      {t("KOTs (kitchen and bar tickets)")}
                    </label>
                    <label className="flex items-center gap-2">
                      <input
                        type="checkbox"
                        checked={!!form.prints_bills}
                        onChange={(e) =>
                          setForm({ ...form, prints_bills: e.target.checked ? 1 : 0 })
                        }
                      />
                      {t("Bills and receipts")}
                    </label>
                  </div>
                  <span className="mt-1 block text-xs text-zinc-400">
                    {t("KOTs follow the outlet and station routes below. A bill goes to the printer chosen on the till, else to a bill printer routed to the bill's outlet.")}
                  </span>
                </div>
                <label className="flex items-center gap-2 self-end pb-2 text-sm">
                  <input
                    type="checkbox"
                    checked={!!form.disabled}
                    onChange={(e) =>
                      setForm({ ...form, disabled: e.target.checked ? 1 : 0 })
                    }
                  />
                  {t("Disabled")}
                </label>
              </div>

              <div>
                <p className="mb-1.5 text-sm font-medium text-zinc-700">{t("Routes: outlets and stations this printer serves")}</p>
                {outlets.length === 0 ? (
                  <p className="text-sm text-zinc-500">
                    {t("Add an outlet first.")}{" "}
                    <Link to="/outlets" className="text-brand-700 underline-offset-2 hover:underline">
                      {t("Outlets")}
                    </Link>
                  </p>
                ) : (
                  <div className="overflow-x-auto">
                    <table className="w-full min-w-[28rem] text-sm">
                      <thead>
                        <tr className="text-xs text-zinc-500">
                          <th className="py-1 text-start font-medium">{t("Outlet")}</th>
                          <th className="px-2 py-1 font-medium">{t("All stations")}</th>
                          {STATIONS.map((st) => (
                            <th key={st} className="px-2 py-1 font-medium">
                              {t(st)}
                            </th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {outlets.map((o) => (
                          <tr key={o.name} className="border-t border-zinc-100">
                            <td className="py-1.5 pe-2">{o.outlet_name}</td>
                            <td className="px-2 text-center">
                              <input
                                type="checkbox"
                                checked={has(o.name, "")}
                                onChange={() => toggle(o.name, "")}
                                aria-label={`${o.outlet_name} - ${t("All stations")}`}
                              />
                            </td>
                            {STATIONS.map((st) => (
                              <td key={st} className="px-2 text-center">
                                <input
                                  type="checkbox"
                                  checked={has(o.name, "") || has(o.name, st)}
                                  disabled={has(o.name, "")}
                                  onChange={() => toggle(o.name, st)}
                                  aria-label={`${o.outlet_name} - ${st}`}
                                />
                              </td>
                            ))}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
                <p className="mt-1.5 text-xs text-zinc-400">
                  {t(
                    "A station comes from each menu item. Tick the same outlet on several printers to print a copy on each.",
                  )}
                </p>
              </div>

              <div className="flex gap-2">
                <Button disabled={busy} onClick={save}>
                  {busy ? t("Saving…") : t("Save printer")}
                </Button>
                <Button
                  variant="ghost"
                  onClick={() => {
                    setForm(null)
                    setErr(null)
                  }}
                >
                  {t("Cancel")}
                </Button>
              </div>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
