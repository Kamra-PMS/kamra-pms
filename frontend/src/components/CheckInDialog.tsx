import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import {
  BedDouble,
  Check,
  CircleCheck,
  ExternalLink,
  KeyRound,
  Loader2,
  MessageCircle,
  Printer,
  Star,
  Wifi,
} from "lucide-react"
import { call } from "../lib/api"
import { serverError } from "../lib/resource"
import { toFullPath } from "../lib/routing"
import { fmtMoney } from "../lib/money"
import { useT, t as translateUI, useUILanguage } from "../lib/i18n"
import { cn } from "../lib/utils"
import { Button } from "./ui/button"
import { Badge } from "./ui/badge"
import { Sheet } from "./ui/sheet"
import { IdDocumentField } from "./IdDocumentField"
import { SignaturePad } from "./SignaturePad"
import DepositPanel, { type DepositState } from "./DepositPanel"
import SecurityDepositPanel, { type SecurityDepositState } from "./SecurityDepositPanel"
import RoomChangeDialog from "./RoomChangeDialog"
import TillCard, { type TillState } from "./TillCard"
import {
  StepFlowFooter,
  StepFlowHeader,
  useStepFlow,
  type FlowStep,
} from "./StepFlow"


/* Guided check-in: one decision per screen, in the property's order
   (Settings > Front desk > Check-in steps). Required steps have no Skip
   and kamra.api.check_in refuses until they are done, so this screen and
   the server agree. Every step writes through its own endpoint in
   kamra.checkin, which records who did it and when. */

type StepState = "done" | "skipped" | "todo" | "blocked"

interface Step {
  step_key: string
  step_type: string
  title: string
  instruction: string
  prompt_to_guest: string
  is_blocking: 0 | 1
  relevant: 0 | 1
  state: StepState
  done_by?: string | null
  done_at?: string | null
}

interface Room {
  name: string
  room_number: string
  housekeeping_status: string
}

interface Flow {
  reservation: {
    name: string
    status: string
    guest: string | null
    guest_name: string
    room_type: string
    check_in_date: string
    check_out_date: string
    nights: number
    adults: number
    children: number
    vip: 0 | 1
    source: string
    special_requests: string
  }
  guest: {
    name: string | null
    full_name: string
    phone: string | null
    email: string | null
    nationality: string | null
    id_type: string | null
    id_number: string | null
    id_on_file: boolean
    /** what the profile already holds: warnings for the desk, never a block */
    id_status: "none" | "valid" | "expiring" | "expired"
    id_expiry_date: string | null
    id_used_count: number
    address: string
  }
  vocabulary: { id_types: string[] }
  steps: Step[]
  missing_required: string[]
  rooms: Room[]
  request_presets: { key: string; label: string }[]
  ids: {
    ok: boolean
    missing: string[]
    online: boolean
    precheckin_status: string
    precheckin_on: string | null
    occupants: {
      row: string
      full_name: string
      age: number | null
      has_id: boolean
      exempt: boolean
    }[]
  }
  billing: {
    payer: string
    source: string
    channel: string | null
    ota_ref: string | null
    pay_at_hotel: 0 | 1
    company: string | null
    company_name: string | null
    billing_rules: { charge_type: string; pay_by: string }[]
    group_booking: string | null
    group_name: string | null
    stay_total: number
    advance_paid: number
    balance_due: number
    options: string[]
  }
  room: {
    room: string | null
    room_number: string | null
    housekeeping_status: string | null
    entire_place: string[] | null
    room_type_name: string | null
    assigned_by: string | null
    assigned_at: string | null
  }
  deposit: {
    applies: boolean
    satisfied: boolean
    security: SecurityDepositState
    advance: DepositState
    security_due: number
    advance_due: number
  }
  grc: { signed: boolean }
  keys: {
    count: number
    cards: string
    issued_by: string | null
    adapter: string
    adapter_label: string
    manual: boolean
  }
  stay_info: {
    guest_wifi_name: string
    guest_wifi_password: string
    breakfast_hours: string
    emergency_number: string
    guest_info_note: string
    checkout_time: string
    configured: boolean
  }
  room_charges: { allowed: boolean; recommend_block: boolean }
  /** the operator's till: the deposit step takes money */
  till: TillState
  records: Record<string, { state: string; by: string; at: string; note?: string }>
  key_result?: { ok: boolean; manual: boolean; message: string } | null
}

/* Built-in step texts, translated here; a property that rewrote a step's
   wording in its SOP gets its own words instead. */
/** Marks a string for the i18n catalog (scripts/i18n-extract.mjs picks up
 *  translate("...")); the text is translated where it is shown, with t(). */
const translate = (s: string) => s

const BUILT_IN: Record<string, { title: string; instruction: string }> = {
  guest_ids: {
    title: translate("Guest and IDs"),
    instruction:
      translate("Check the guest's name and phone, then the ID for the guest and everyone staying. If they checked in online, review what they sent."),
  },
  billing_check: {
    title: translate("Who pays"),
    instruction:
      translate("Confirm who pays for the room and the extras: the OTA, the guest, the company or the group."),
  },
  assign_room: {
    title: translate("Room"),
    instruction:
      translate("Give a clean, empty room of the booked type, or keep the room already assigned."),
  },
  security_deposit: {
    title: translate("Deposit and advance"),
    instruction:
      translate("Take the security deposit (or waive it with a reason) and any advance the booking still owes."),
  },
  registration_card: {
    title: translate("Registration card"),
    instruction: translate("Show or print the registration card and have the guest sign it."),
  },
  keys: { title: translate("Keys"), instruction: translate("Make the room keys and note how many you gave.") },
  stay_info: {
    title: translate("Wi-Fi and stay info"),
    instruction:
      translate("Tell the guest the Wi-Fi, breakfast and check-out times. Print it or send it on WhatsApp."),
  },
  guest_requests: {
    title: translate("Anything needed?"),
    instruction: translate("Ask if they need anything: an extra bed, a wake-up call, an airport drop."),
  },
  room_charges: {
    title: translate("Charges to the room"),
    instruction:
      translate("Decide if the guest can charge the restaurant, laundry and minibar to the room."),
  },
}

const PAYER_LABEL: Record<string, string> = {
  "OTA prepaid": translate("OTA has paid the room"),
  "OTA, guest pays here": translate("OTA booking, guest pays here"),
  Guest: translate("Guest pays"),
  Company: translate("Company pays"),
  Group: translate("Group account pays"),
}

const REQUEST_LABEL: Record<string, string> = {
  extra_bed: translate("Extra bed"),
  wake_up_call: translate("Wake-up call"),
  airport_drop: translate("Airport drop"),
  dietary: translate("Dietary needs"),
  special_occasion: translate("Special occasion"),
}

const hkTone: Record<string, string> = {
  Clean: "border-emerald-200 bg-emerald-50 text-emerald-800",
  Inspected: "border-sky-200 bg-sky-50 text-sky-800",
  Dirty: "border-amber-200 bg-amber-50 text-amber-800",
}

const inputCls =
  "w-full rounded-lg border border-zinc-300 bg-white px-3 py-2.5 text-base sm:text-sm " +
  "focus:outline-2 focus:outline-offset-1 focus:outline-brand-600"

const who = (u?: string | null) => (u ?? "").split("@")[0]
const when = (d?: string | null) => (d ? d.replace("T", " ").slice(0, 16) : "")

function Choice(props: {
  selected: boolean
  onClick: () => void
  title: string
  hint?: string
  disabled?: boolean
}) {
  useUILanguage()
  return (
    <button
      type="button"
      disabled={props.disabled}
      onClick={props.onClick}
      aria-pressed={props.selected}
      className={cn(
        "flex w-full items-start gap-3 rounded-xl border p-4 text-start transition",
        "disabled:cursor-not-allowed disabled:opacity-50",
        props.selected
          ? "border-brand-500 bg-brand-50 ring-2 ring-brand-100"
          : "border-zinc-200 bg-white hover:border-brand-300",
      )}
    >
      <span
        aria-hidden
        className={cn(
          "mt-0.5 flex size-5 shrink-0 items-center justify-center rounded-full border",
          props.selected ? "border-brand-600 bg-brand-600 text-white" : "border-zinc-300",
        )}
      >
        {props.selected && <Check className="size-3.5" />}
      </span>
      <span>
        <span className="block text-base font-semibold text-zinc-900">{translateUI(props.title)}</span>
        {props.hint && <span className="mt-0.5 block text-sm text-zinc-500">{translateUI(props.hint)}</span>}
      </span>
    </button>
  )
}

function Row(props: { label: string; value: React.ReactNode; strong?: boolean }) {
  useUILanguage()
  return (
    <div className="flex items-baseline justify-between gap-3 py-1.5">
      <dt className="text-sm text-zinc-500">{translateUI(props.label)}</dt>
      <dd className={cn("text-end text-sm tabular-nums", props.strong && "font-semibold text-zinc-900")}>
        {props.value}
      </dd>
    </div>
  )
}

export default function CheckInDialog(props: {
  reservation: string
  onDone: () => void
  onClose: () => void
}) {
  const { t } = useT()
  const [flow, setFlow] = useState<Flow | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [finished, setFinished] = useState<{
    room: string | null
    keys?: { message: string } | null
  } | null>(null)

  // per-step drafts
  const [details, setDetails] = useState({ phone: "", email: "", nationality: "", id_type: "", id_number: "" })
  const [detailsDirty, setDetailsDirty] = useState(false)
  const [payer, setPayer] = useState("")
  const [room, setRoom] = useState("")
  const [changeRoom, setChangeRoom] = useState(false)
  const [upgrade, setUpgrade] = useState(false)
  const [signature, setSignature] = useState("")
  const [onPaper, setOnPaper] = useState(false)
  const [keyCount, setKeyCount] = useState(1)
  const [keyCards, setKeyCards] = useState("")
  const [requests, setRequests] = useState<string[]>([])
  const [note, setNote] = useState("")
  const [allowCharges, setAllowCharges] = useState<boolean | null>(null)
  const [chargesReason, setChargesReason] = useState("")
  const [keyMessage, setKeyMessage] = useState<string | null>(null)

  const adopt = useCallback((f: Flow) => {
    setFlow(f)
    setError(null)
    if (f.key_result?.message) setKeyMessage(f.key_result.message)
  }, [])

  const load = useCallback(async () => {
    try {
      const f = await call<Flow>("kamra.checkin.checkin_flow", { reservation: props.reservation })
      adopt(f)
      setDetails({
        phone: f.guest.phone ?? "",
        email: f.guest.email ?? "",
        nationality: f.guest.nationality ?? "",
        id_type: f.guest.id_type ?? "",
        id_number: "",
      })
      setPayer((f.records.billing_check as { payer?: string } | undefined)?.payer ?? f.billing.payer)
      setKeyCount(f.keys.count || Math.max(1, Math.min(f.reservation.adults || 1, 4)))
      setKeyCards(f.keys.cards || "")
      setAllowCharges(f.records.room_charges ? f.room_charges.allowed : !f.room_charges.recommend_block)
    } catch (e) {
      setError(
        (e as { status?: number }).status === 403
          ? t("Checking a guest in is for Front Desk or a Hotel Admin. Your role can see the booking but not check the guest in.")
          : serverError(e),
      )
    }
  }, [props.reservation, adopt, t])

  useEffect(() => {
    load()
  }, [load])

  const flowSteps: FlowStep[] = useMemo(() => {
    const out: FlowStep[] = (flow?.steps ?? []).map((s) => ({
      key: s.step_key,
      label: BUILT_IN[s.step_key] && s.title === BUILT_IN[s.step_key].title
        ? t(BUILT_IN[s.step_key].title)
        : s.title,
      status: s.state === "done" ? "done" : s.state === "skipped" ? "skipped" : undefined,
      optional: !s.is_blocking,
      hidden: !s.relevant,
    }))
    out.push({ key: "confirm", label: t("Check in") })
    return out
  }, [flow, t])

  const nav = useStepFlow(flowSteps)
  // the last step reads "needs attention" only once the desk gets there
  // with required steps still open, not from the first screen
  const headerSteps = useMemo(
    () => flowSteps.map((s) =>
      s.key === "confirm" && nav.current === "confirm" && flow?.missing_required.length
        ? { ...s, status: "blocked" as const } : s),
    [flowSteps, nav, flow],
  )
  const step = flow?.steps.find((s) => s.step_key === nav.current) ?? null

  // open on the first step still to do (a pre-assigned room is already done)
  const started = useRef(false)
  const { goTo } = nav
  useEffect(() => {
    if (!flow || started.current) return
    started.current = true
    const first = flow.steps.find((s) => s.relevant && s.state !== "done")
    goTo(first ? first.step_key : "confirm")
  }, [flow, goTo])

  async function run<T>(method: string, args: Record<string, unknown>, advance = true): Promise<T | null> {
    setBusy(true)
    setError(null)
    try {
      const f = await call<Flow>(method, { reservation: props.reservation, ...args })
      adopt(f)
      if (advance) nav.next()
      return f as unknown as T
    } catch (e) {
      setError(serverError(e))
      return null
    } finally {
      setBusy(false)
    }
  }

  async function saveDetails() {
    if (!detailsDirty) return true
    const f = await run<Flow>("kamra.checkin.save_guest_details", {
      phone: details.phone,
      email: details.email,
      nationality: details.nationality,
      id_type: details.id_type || undefined,
      id_number: details.id_number || undefined,
    }, false)
    if (f) {
      setDetailsDirty(false)
      setDetails((d) => ({ ...d, id_number: "" }))
    }
    return !!f
  }

  async function onContinue() {
    if (!flow) return
    const key = nav.current
    if (key === "confirm") return confirm()
    const s = flow.steps.find((x) => x.step_key === key)
    if (s?.state === "done" && !(key === "guest_ids" && detailsDirty)) {
      nav.next()
      return
    }
    switch (key) {
      case "guest_ids":
        if (await saveDetails()) await run("kamra.checkin.complete_checkin_step", { step: key })
        return
      case "billing_check":
        await run("kamra.checkin.confirm_billing", { payer })
        return
      case "assign_room":
        await run("kamra.checkin.assign_checkin_room", { room: room || undefined })
        setChangeRoom(false)
        return
      case "registration_card":
        if (signature) {
          await run("kamra.checkin.sign_registration_card", { signature })
        } else if (onPaper) {
          await run("kamra.checkin.sign_registration_card", { on_paper: 1 })
        } else if (flow.grc.signed) {
          await run("kamra.checkin.complete_checkin_step", { step: key, note: "Signed online" })
        } else {
          setError(t("Have the guest sign on screen, or tick that they signed the printed card."))
        }
        return
      case "keys":
        await run("kamra.checkin.issue_keys", { key_count: keyCount, key_cards: keyCards || undefined })
        return
      case "guest_requests":
        await run("kamra.checkin.log_checkin_requests", { requests, note })
        return
      case "room_charges":
        await run("kamra.checkin.set_room_charges", {
          allowed: allowCharges === false ? 0 : 1,
          reason: chargesReason || undefined,
        })
        return
      case "stay_info":
        await run("kamra.checkin.complete_checkin_step", { step: key, note: "Told the guest" })
        return
      default:
        await run("kamra.checkin.complete_checkin_step", { step: key })
    }
  }

  async function onSkip() {
    await run("kamra.checkin.skip_checkin_step", { step: nav.current })
  }

  async function confirm() {
    setBusy(true)
    setError(null)
    try {
      const out = await call<{ room: string | null; keys?: { message: string } }>(
        "kamra.api.check_in",
        { reservation: props.reservation },
      )
      setFinished({ room: flow?.room.room_number ?? out.room, keys: out.keys ?? null })
    } catch (e) {
      setError(serverError(e))
      load()
    } finally {
      setBusy(false)
    }
  }

  const r = flow?.reservation
  const title = r ? t("Check in {name}", { name: r.guest_name }) : t("Check in")
  const description = r
    ? `${flow?.room.room_type_name ?? ""} · ${r.check_in_date} → ${r.check_out_date} · ${t("{n} adult{s}", { n: r.adults, s: r.adults === 1 ? "" : "s" })}${r.children ? ` + ${r.children}` : ""}`
    : undefined

  if (finished && flow) {
    return (
      <Sheet
        wide
        title={translateUI(title)}
        description={translateUI(description)}
        onClose={props.onDone}
        footer={
          <div className="flex w-full flex-wrap items-center gap-2">
            <a
              href={toFullPath(`/grc/${flow.reservation.name}`)}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1.5 rounded-lg border border-zinc-300 bg-white px-4 py-2.5 text-sm font-medium text-zinc-700 hover:bg-zinc-50"
            >
              <Printer className="size-4" aria-hidden /> {t("Print registration card")}
            </a>
            <Button className="ms-auto px-6 py-2.5 text-base" onClick={props.onDone}>
              {t("Done")}
            </Button>
          </div>
        }
      >
        <div className="space-y-4">
          <div className="flex items-start gap-3 rounded-xl border border-emerald-200 bg-emerald-50 px-5 py-4 text-emerald-900">
            <CircleCheck className="mt-0.5 size-6 shrink-0 text-emerald-600" aria-hidden />
            <div>
              <p className="text-lg font-semibold">
                {finished.room
                  ? t("{name} is checked in to room {room}", { name: flow.reservation.guest_name, room: finished.room })
                  : t("{name} is checked in", { name: flow.reservation.guest_name })}
              </p>
              <p className="mt-1 text-sm">
                {flow.keys.count
                  ? t("{n} key(s) handed over.", { n: flow.keys.count })
                  : t("No keys recorded.")}
              </p>
            </div>
          </div>
          {(finished.keys?.message || keyMessage) && (
            <p className="flex items-start gap-2 rounded-xl border border-zinc-200 bg-white px-4 py-3 text-sm text-zinc-700">
              <KeyRound className="mt-0.5 size-4 shrink-0 text-zinc-500" aria-hidden />
              {translateUI(finished.keys?.message || keyMessage)}
            </p>
          )}
        </div>
      </Sheet>
    )
  }

  const isConfirm = nav.current === "confirm"
  const optional = !isConfirm && step && !step.is_blocking && step.state !== "done"
  const builtIn = step ? BUILT_IN[step.step_key] : undefined
  const instruction = step
    ? builtIn && step.instruction === builtIn.instruction
      ? t(builtIn.instruction)
      : step.instruction
    : ""

  return (
    <Sheet
      wide
      title={translateUI(title)}
      description={translateUI(description)}
      onClose={props.onClose}
      footer={
        <StepFlowFooter
          start={
            <Button variant="outline" disabled={busy} onClick={props.onClose}>
              {t("Close")}
            </Button>
          }
          error={error}
          busy={busy || !flow}
          onBack={nav.isFirst ? undefined : nav.back}
          onSkip={optional ? onSkip : undefined}
          onContinue={onContinue}
          continueDisabled={(isConfirm && !!flow?.missing_required.length) ||
            (nav.current === "security_deposit" && !!flow && !flow.deposit.satisfied && step?.state !== "done")}
          disabledReason={isConfirm
            ? t("Finish the required steps first.")
            : t("Take the deposit (or waive it with a reason) to continue.")}
          continueLabel={
            busy
              ? t("Saving…")
              : isConfirm
                ? flow?.room.room_number
                  ? t("Check in to room {room}", { room: flow.room.room_number })
                  : t("Check in")
                : step?.state === "done"
                  ? t("Continue")
                  : t("Done, continue")
          }
        />
      }
    >
      {!flow && !error && (
        <p className="flex items-center gap-2 text-sm text-zinc-500">
          <Loader2 className="size-4 animate-spin" aria-hidden />
          {t("Loading…")}
        </p>
      )}
      {flow && r && (
        <div className="space-y-5">
          <StepFlowHeader steps={headerSteps} current={nav.current} onSelect={nav.goTo} />

          {r.vip ? (
            <p className="flex items-center gap-1.5 text-sm font-semibold text-amber-700">
              <Star className="size-4 fill-amber-400 text-amber-400" aria-hidden />
              {t("VIP guest")}
            </p>
          ) : null}

          {step && (
            <header className="space-y-1">
              <h3 className="flex flex-wrap items-center gap-2 text-lg font-semibold text-zinc-900">
                {translateUI(flowSteps.find((s) => s.key === step.step_key)?.label)}
                <span
                  className={cn(
                    "rounded-full border px-2 py-0.5 text-[11px] font-semibold uppercase",
                    step.is_blocking
                      ? "border-rose-200 bg-rose-50 text-rose-700"
                      : "border-zinc-200 bg-zinc-50 text-zinc-500",
                  )}
                >
                  {step.is_blocking ? t("Required") : t("Optional")}
                </span>
              </h3>
              <p className="text-sm text-zinc-600">{instruction}</p>
              {step.state !== "todo" && step.done_by && (
                <p className="text-xs text-zinc-400">
                  {step.state === "skipped"
                    ? t("Skipped by {who} at {when}", { who: who(step.done_by), when: when(step.done_at) })
                    : t("Done by {who} at {when}", { who: who(step.done_by), when: when(step.done_at) })}
                </p>
              )}
            </header>
          )}

          {nav.current === "guest_ids" && (
            <div className="space-y-4">
              {flow.ids.online && (
                <div className="rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-900">
                  <p className="font-semibold">{t("Done online")}</p>
                  <p>
                    {t("The guest checked in online{when}. Check what they sent against the guest at the desk.", {
                      when: flow.ids.precheckin_on ? ` (${when(flow.ids.precheckin_on)})` : "",
                    })}
                  </p>
                </div>
              )}
              <dl className="divide-y divide-zinc-100 rounded-xl border border-zinc-200 bg-white px-4">
                <Row label={t("Name")} value={flow.guest.full_name} strong />
                <Row
                  label={t("ID")}
                  value={
                    <span className="flex flex-wrap items-center justify-end gap-1.5">
                      {flow.guest.id_number
                        ? `${flow.guest.id_type ? t(flow.guest.id_type) + " · " : ""}${flow.guest.id_number}`
                        : flow.guest.id_on_file
                          ? t("Photo on file")
                          : <span className="text-rose-700">{t("Missing")}</span>}
                      {flow.guest.id_status === "expired" && (
                        <Badge tone="rose">{t("Expired {date}", { date: flow.guest.id_expiry_date ?? "" })}</Badge>
                      )}
                      {flow.guest.id_status === "expiring" && (
                        <Badge tone="amber">{t("Expires {date}", { date: flow.guest.id_expiry_date ?? "" })}</Badge>
                      )}
                      {flow.guest.id_used_count > 0 && (
                        <Badge tone="brand">
                          {flow.guest.id_used_count === 1
                            ? t("Used on 1 earlier stay")
                            : t("Used on {n} earlier stays", { n: flow.guest.id_used_count })}
                        </Badge>
                      )}
                    </span>
                  }
                />
              </dl>
              <div className="grid gap-3 sm:grid-cols-2">
                {(
                  [
                    ["phone", t("Phone"), "tel"],
                    ["email", t("Email"), "email"],
                    ["nationality", t("Nationality"), "text"],
                  ] as const
                ).map(([k, label, type]) => (
                  <label key={k} className="block">
                    <span className="mb-1 block text-xs font-medium text-zinc-500">{translateUI(label)}</span>
                    <input
                      className={inputCls}
                      type={type}
                      value={details[k]}
                      onChange={(e) => {
                        setDetails((d) => ({ ...d, [k]: e.target.value }))
                        setDetailsDirty(true)
                      }}
                    />
                  </label>
                ))}
                <label className="block">
                  <span className="mb-1 block text-xs font-medium text-zinc-500">{t("ID type")}</span>
                  <select
                    className={inputCls}
                    value={details.id_type}
                    onChange={(e) => {
                      setDetails((d) => ({ ...d, id_type: e.target.value }))
                      setDetailsDirty(true)
                    }}
                  >
                    <option value="">{t("Choose…")}</option>
                    {flow.vocabulary.id_types.map((x) => (
                      <option key={x} value={x}>{t(x)}</option>
                    ))}
                  </select>
                </label>
                <label className="block sm:col-span-2">
                  <span className="mb-1 block text-xs font-medium text-zinc-500">
                    {flow.guest.id_number ? t("New ID number (leave empty to keep)") : t("ID number")}
                  </span>
                  <input
                    className={inputCls}
                    value={details.id_number}
                    autoComplete="off"
                    onChange={(e) => {
                      setDetails((d) => ({ ...d, id_number: e.target.value }))
                      setDetailsDirty(true)
                    }}
                  />
                </label>
              </div>
              <IdDocumentField
                method="kamra.api.upload_id_document"
                params={{ reservation: r.name }}
                uploaded={flow.guest.id_on_file}
                onUploaded={load}
                label={t("Photograph the guest's ID")}
              />
              <section className="rounded-xl border border-zinc-200 bg-white p-4">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <h4 className="text-sm font-semibold text-zinc-800">{t("Everyone staying")}</h4>
                  <a
                    href={toFullPath(`/grc/${r.name}`)}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex items-center gap-1 text-sm font-medium text-brand-700 hover:underline"
                  >
                    {t("Add guests and their IDs")} <ExternalLink className="size-3.5" aria-hidden />
                  </a>
                </div>
                {flow.ids.occupants.length === 0 ? (
                  <p className="mt-1 text-sm text-zinc-500">
                    {t("No other guests recorded. Add them on the registration card, then come back here.")}
                  </p>
                ) : (
                  <ul className="mt-2 divide-y divide-zinc-100">
                    {flow.ids.occupants.map((o) => (
                      <li key={o.row} className="flex items-center justify-between py-1.5 text-sm">
                        <span>
                          {o.full_name}
                          {o.age != null ? ` · ${o.age}` : ""}
                        </span>
                        <span
                          className={cn(
                            "text-xs font-medium",
                            o.has_id ? "text-emerald-700" : o.exempt ? "text-zinc-500" : "text-rose-700",
                          )}
                        >
                          {o.has_id ? t("ID on file") : o.exempt ? t("No ID needed (child)") : t("ID missing")}
                        </span>
                      </li>
                    ))}
                  </ul>
                )}
                <Button variant="ghost" className="mt-2 h-8 px-2 text-xs" onClick={load}>
                  {t("Refresh")}
                </Button>
              </section>
              {!flow.ids.ok && (
                <p className="text-sm font-medium text-rose-700">
                  {t("ID still needed for: {names}.", { names: flow.ids.missing.join(", ") })}
                </p>
              )}
            </div>
          )}

          {nav.current === "billing_check" && (
            <div className="space-y-4">
              <div className="grid gap-2">
                {flow.billing.options
                  .filter((p) =>
                    p === "Guest" ||
                    (p === "Company" && flow.billing.company) ||
                    (p === "Group" && flow.billing.group_booking) ||
                    (p.startsWith("OTA") && (flow.billing.source === "OTA" || flow.billing.ota_ref)),
                  )
                  .map((p) => (
                    <Choice
                      key={p}
                      selected={payer === p}
                      onClick={() => setPayer(p)}
                      title={t(PAYER_LABEL[p] ?? p)}
                      hint={
                        translateUI(p === "Company"
                          ? flow.billing.company_name ?? undefined
                          : p === "Group"
                            ? flow.billing.group_name ?? undefined
                            : p.startsWith("OTA")
                              ? [flow.billing.channel, flow.billing.ota_ref].filter(Boolean).join(" · ") || undefined
                              : undefined)
                      }
                    />
                  ))}
              </div>
              <dl className="divide-y divide-zinc-100 rounded-xl border border-zinc-200 bg-white px-4">
                <Row label={t("Stay total")} value={fmtMoney(flow.billing.stay_total)} />
                <Row label={t("Paid so far")} value={fmtMoney(flow.billing.advance_paid)} />
                {flow.deposit.security.held > 0 && (
                  <Row label={t("Security deposit held")} value={fmtMoney(flow.deposit.security.held)} />
                )}
                <Row label={t("Left to pay")} value={fmtMoney(flow.billing.balance_due)} strong />
              </dl>
              {payer === "Company" && flow.billing.billing_rules.length > 0 && (
                <div className="rounded-xl border border-zinc-200 bg-white p-4 text-sm">
                  <p className="mb-1 font-semibold text-zinc-800">{t("What the company pays")}</p>
                  <ul className="space-y-0.5 text-zinc-600">
                    {flow.billing.billing_rules.map((b) => (
                      <li key={b.charge_type}>
                        {t(b.charge_type)}: {t(b.pay_by)}
                      </li>
                    ))}
                  </ul>
                  <p className="mt-1 text-xs text-zinc-400">{t("Alcohol is always paid by the guest.")}</p>
                </div>
              )}
              {payer === "OTA prepaid" && (
                <p className="text-sm text-zinc-600">
                  {t("Do not take money for the room. Extras are paid by the guest.")}
                </p>
              )}
            </div>
          )}

          {nav.current === "assign_room" && (
            <div className="space-y-4">
              {flow.room.entire_place && !flow.room.room ? (
                <p className="rounded-xl border border-zinc-200 bg-white px-4 py-3 text-base">
                  {t("Whole place: rooms {rooms}", { rooms: flow.room.entire_place.join(", ") })}
                </p>
              ) : flow.room.room && !changeRoom ? (
                <div className="space-y-3">
                  <div className="flex flex-wrap items-center gap-3 rounded-xl border border-zinc-200 bg-white px-4 py-4">
                    <BedDouble className="size-6 text-brand-600" aria-hidden />
                    <div>
                      <p className="text-xl font-semibold">{t("Room {n}", { n: flow.room.room_number ?? "" })}</p>
                      {flow.room.assigned_by && (
                        <p className="text-xs text-zinc-400">
                          {t("Assigned by {who} at {when}", { who: who(flow.room.assigned_by), when: when(flow.room.assigned_at) })}
                        </p>
                      )}
                    </div>
                    {flow.room.housekeeping_status && (
                      <span className={cn("ms-auto rounded-full border px-2.5 py-0.5 text-xs font-semibold", hkTone[flow.room.housekeeping_status] ?? "border-zinc-200 text-zinc-600")}>
                        {t(flow.room.housekeeping_status)}
                      </span>
                    )}
                  </div>
                  {flow.room.housekeeping_status === "Dirty" && (
                    <p className="text-sm font-medium text-amber-700">
                      {t("This room is not cleaned yet. Pick a clean room, or ask housekeeping first.")}
                    </p>
                  )}
                  {r.status === "Confirmed" && (
                    <div className="flex flex-wrap gap-2">
                      <Button variant="outline" onClick={() => setUpgrade(true)}>
                        {t("Change room or upgrade")}
                      </Button>
                    </div>
                  )}
                </div>
              ) : (
                <div className="space-y-3">
                  {flow.rooms.length === 0 ? (
                    <p className="text-sm text-rose-700">
                      {t("No free room of this type for these dates. Try an upgrade to another type.")}
                    </p>
                  ) : (
                    <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
                      {flow.rooms.map((x) => (
                        <button
                          key={x.name}
                          type="button"
                          onClick={() => setRoom(x.name)}
                          aria-pressed={room === x.name}
                          className={cn(
                            "rounded-xl border p-3 text-start transition",
                            room === x.name
                              ? "border-brand-500 bg-brand-50 ring-2 ring-brand-100"
                              : "border-zinc-200 bg-white hover:border-brand-300",
                          )}
                        >
                          <span className="block text-lg font-semibold">{x.room_number}</span>
                          <span className={cn("mt-1 inline-block rounded-full border px-2 py-0.5 text-[11px] font-semibold", hkTone[x.housekeeping_status] ?? "border-zinc-200 text-zinc-600")}>
                            {t(x.housekeeping_status || "Unknown")}
                          </span>
                        </button>
                      ))}
                    </div>
                  )}
                  <Button variant="outline" onClick={() => setUpgrade(true)}>
                    {t("Upgrade or another type")}
                  </Button>
                </div>
              )}
            </div>
          )}

          {nav.current === "security_deposit" && (
            <div className="space-y-4">
              {!flow.deposit.satisfied && (
                <TillCard till={flow.till} onOpened={load} purpose={t("to take the deposit")} />
              )}
              {flow.deposit.security.status !== "None" && (
                <SecurityDepositPanel
                  reservation={r.name}
                  deposit={flow.deposit.security}
                  canStart
                  onChanged={load}
                />
              )}
              {flow.deposit.advance_due > 0 && (
                <DepositPanel
                  reservation={r.name}
                  deposit={flow.deposit.advance}
                  guestPhone={flow.guest.phone}
                  onChanged={() => load()}
                />
              )}
              {!flow.deposit.satisfied && (
                <p className="text-sm font-medium text-rose-700">
                  {t("Take the security deposit or waive it with a reason to continue.")}
                </p>
              )}
            </div>
          )}

          {nav.current === "registration_card" && (
            <div className="space-y-4">
              <a
                href={toFullPath(`/grc/${r.name}`)}
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center gap-2 rounded-xl border border-zinc-300 bg-white px-4 py-3 text-base font-medium text-zinc-800 hover:bg-zinc-50"
              >
                <Printer className="size-5" aria-hidden /> {t("Open the card to show or print")}
              </a>
              {flow.grc.signed && !signature && (
                <p className="rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-900">
                  {t("The guest already signed (online or earlier). Continue, or ask them to sign again below.")}
                </p>
              )}
              <div>
                <p className="mb-1 text-sm font-medium text-zinc-700">{t("Guest signs here")}</p>
                <SignaturePad onChange={setSignature} />
              </div>
              <label className="flex items-center gap-2 text-base">
                <input
                  type="checkbox"
                  className="size-5"
                  checked={onPaper}
                  onChange={(e) => setOnPaper(e.target.checked)}
                />
                {t("The guest signed the printed card")}
              </label>
            </div>
          )}

          {nav.current === "keys" && (
            <div className="space-y-4">
              {!flow.keys.manual && (
                <p className="rounded-xl border border-zinc-200 bg-white px-4 py-3 text-sm text-zinc-700">
                  {t("{lock} makes the keys when you check the guest in.", { lock: flow.keys.adapter_label })}
                </p>
              )}
              <div className="flex items-center gap-3">
                <span className="text-sm font-medium text-zinc-700">{t("Keys")}</span>
                <Button variant="outline" className="size-11 text-xl" aria-label={t("Fewer keys")}
                  disabled={keyCount <= 1} onClick={() => setKeyCount((n) => Math.max(1, n - 1))}>
                  −
                </Button>
                <span className="w-8 text-center text-2xl font-semibold tabular-nums">{keyCount}</span>
                <Button variant="outline" className="size-11 text-xl" aria-label={t("More keys")}
                  disabled={keyCount >= 10} onClick={() => setKeyCount((n) => Math.min(10, n + 1))}>
                  +
                </Button>
              </div>
              {flow.keys.manual && (
                <label className="block">
                  <span className="mb-1 block text-xs font-medium text-zinc-500">
                    {t("Key card numbers (optional)")}
                  </span>
                  <input className={inputCls} value={keyCards} onChange={(e) => setKeyCards(e.target.value)} />
                </label>
              )}
              {keyMessage && (
                <p className="flex items-start gap-2 text-sm text-zinc-600">
                  <KeyRound className="mt-0.5 size-4 shrink-0" aria-hidden /> {translateUI(keyMessage)}
                </p>
              )}
            </div>
          )}

          {nav.current === "stay_info" && <StayInfoCard flow={flow} />}

          {nav.current === "guest_requests" && (
            <div className="space-y-4">
              {r.special_requests && (
                <p className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
                  <span className="font-semibold">{t("Booking notes")}: </span>
                  {r.special_requests}
                </p>
              )}
              <div className="flex flex-wrap gap-2">
                {flow.request_presets.map((p) => {
                  const on = requests.includes(p.key)
                  return (
                    <button
                      key={p.key}
                      type="button"
                      aria-pressed={on}
                      onClick={() => setRequests((xs) => (on ? xs.filter((x) => x !== p.key) : [...xs, p.key]))}
                      className={cn(
                        "rounded-full border px-4 py-2 text-sm font-medium",
                        on ? "border-brand-500 bg-brand-50 text-brand-800" : "border-zinc-300 bg-white text-zinc-700",
                      )}
                    >
                      {on && <Check className="me-1 inline size-3.5" aria-hidden />}
                      {t(REQUEST_LABEL[p.key] ?? p.label)}
                    </button>
                  )
                })}
              </div>
              <label className="block">
                <span className="mb-1 block text-xs font-medium text-zinc-500">{t("Anything else (optional)")}</span>
                <textarea className={inputCls} rows={3} value={note} onChange={(e) => setNote(e.target.value)} />
              </label>
              <p className="text-xs text-zinc-400">
                {t("Each request becomes a task for the right team.")}
              </p>
            </div>
          )}

          {nav.current === "room_charges" && (
            <div className="space-y-3">
              {flow.room_charges.recommend_block && (
                <p className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
                  {t("The OTA paid the room and nothing is held for extras. Blocking charges to the room is safer.")}
                </p>
              )}
              <Choice
                selected={allowCharges === true}
                onClick={() => setAllowCharges(true)}
                title={t("Allow charges to the room")}
                hint={t("Restaurant, laundry and minibar go on the guest's bill.")}
              />
              <Choice
                selected={allowCharges === false}
                onClick={() => setAllowCharges(false)}
                title={t("Block charges to the room")}
                hint={t("The guest pays at the outlet. Outlets cannot post to this room.")}
              />
              {allowCharges === false && (
                <label className="block">
                  <span className="mb-1 block text-xs font-medium text-zinc-500">{t("Why (optional)")}</span>
                  <input className={inputCls} value={chargesReason} onChange={(e) => setChargesReason(e.target.value)} />
                </label>
              )}
            </div>
          )}

          {step && !BUILT_IN[step.step_key] && step.prompt_to_guest && (
            <p className="rounded-xl border border-zinc-200 bg-white px-4 py-3 text-sm text-zinc-700">
              {step.prompt_to_guest}
            </p>
          )}

          {isConfirm && (
            <div className="space-y-3">
              <h3 className="text-lg font-semibold text-zinc-900">{t("Check-in summary")}</h3>
              <ul className="divide-y divide-zinc-100 rounded-xl border border-zinc-200 bg-white">
                {flow.steps
                  .filter((s) => s.relevant)
                  .map((s) => {
                    const missing = flow.missing_required.includes(s.step_key)
                    return (
                      <li key={s.step_key} className="flex flex-wrap items-center gap-2 px-4 py-2.5 text-sm">
                        <span
                          aria-hidden
                          className={cn(
                            "flex size-5 items-center justify-center rounded-full text-white",
                            s.state === "done" ? "bg-emerald-500" : missing ? "bg-rose-500" : "bg-zinc-300",
                          )}
                        >
                          {s.state === "done" ? <Check className="size-3" /> : "!"}
                        </span>
                        <span className="font-medium">{translateUI(flowSteps.find((f) => f.key === s.step_key)?.label)}</span>
                        <span className="text-zinc-400">
                          {s.state === "done"
                            ? (s.done_by || (s.step_key === "assign_room" && flow.room.assigned_by))
                              ? t("by {who}", { who: who(s.done_by || flow.room.assigned_by) })
                              : ""
                            : s.state === "skipped"
                              ? t("skipped")
                              : missing
                                ? t("required, not done")
                                : t("not done")}
                        </span>
                        {s.state !== "done" && (
                          <Button variant="ghost" className="ms-auto h-8 px-2 text-xs" onClick={() => nav.goTo(s.step_key)}>
                            {t("Go to step")}
                          </Button>
                        )}
                      </li>
                    )
                  })}
              </ul>
              {flow.missing_required.length > 0 ? (
                <p className="text-sm font-medium text-rose-700">
                  {t("Finish the required steps first.")}
                </p>
              ) : (
                <p className="text-sm text-zinc-600">{t("Everything required is done. Check the guest in.")}</p>
              )}
            </div>
          )}
        </div>
      )}

      {upgrade && flow && (
        <RoomChangeDialog
          reservation={flow.reservation.name}
          currentRoomNumber={flow.room.room_number}
          onClose={() => setUpgrade(false)}
          onMoved={async () => {
            setUpgrade(false)
            await load()
          }}
        />
      )}
    </Sheet>
  )
}

function StayInfoCard({ flow }: { flow: Flow }) {
  const { t } = useT()
  const info = flow.stay_info
  const lines: [string, string][] = (
    [
      [t("Wi-Fi"), info.guest_wifi_name],
      [t("Wi-Fi password"), info.guest_wifi_password],
      [t("Breakfast"), info.breakfast_hours],
      [t("Check-out time"), info.checkout_time],
      [t("Emergency number"), info.emergency_number],
      [t("Good to know"), info.guest_info_note],
    ] as [string, string][]
  ).filter(([, v]) => v)
  const text = lines.map(([k, v]) => `${k}: ${v}`).join("\n")
  const phone = (flow.guest.phone ?? "").replace(/[^\d]/g, "")

  function print() {
    const w = window.open("", "_blank", "width=420,height=600")
    if (!w) return
    const esc = (s: string) => s.replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" })[c] ?? c)
    w.document.write(
      `<html><head><title>${esc(t("Stay info"))}</title></head><body style="font-family:system-ui;padding:24px">` +
        `<h2>${esc(flow.reservation.guest_name)}</h2>` +
        lines.map(([k, v]) => `<p><b>${esc(k)}</b><br>${esc(v).replace(/\n/g, "<br>")}</p>`).join("") +
        `</body></html>`,
    )
    w.document.close()
    w.focus()
    w.print()
  }

  return (
    <div className="space-y-4">
      <dl className="divide-y divide-zinc-100 rounded-xl border border-zinc-200 bg-white px-4">
        {lines.map(([k, v]) => (
          <div key={k} className="flex items-baseline justify-between gap-3 py-2">
            <dt className="flex items-center gap-1.5 text-sm text-zinc-500">
              {k === t("Wi-Fi") && <Wifi className="size-4" aria-hidden />}
              {translateUI(k)}
            </dt>
            <dd className="whitespace-pre-line text-end text-base font-medium text-zinc-900">{v}</dd>
          </div>
        ))}
      </dl>
      <div className="flex flex-wrap gap-2">
        <Button variant="outline" onClick={print}>
          <Printer className="size-4" aria-hidden /> {t("Print")}
        </Button>
        {phone && (
          <a
            href={`https://wa.me/${phone}?text=${encodeURIComponent(text)}`}
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-1.5 rounded-lg border border-zinc-300 bg-white px-4 py-2 text-sm font-medium text-zinc-700 hover:bg-zinc-50"
          >
            <MessageCircle className="size-4" aria-hidden /> {t("Send on WhatsApp")}
          </a>
        )}
      </div>
    </div>
  )
}
