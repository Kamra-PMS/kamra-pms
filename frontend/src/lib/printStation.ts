import { useEffect, useState } from "react"
/*  Print station: a kitchen display screen that prints a Kitchen Printer's
    tickets to the printer attached to this device (its default printer;
    run Chrome with --kiosk-printing so nobody clicks Print). The choice is
    per device, kept in this browser. Jobs arrive over the socket the
    moment a KOT is fired; a 5 s check is the fallback and also tells the
    server this station is online. */

import { call } from "./api"
import { subscribeRealtime } from "./realtime"
import { joinTickets, kotHtml, printThermal, type KotLine } from "./thermal"

const KEY = "kamra_print_station"
const POLL_MS = 5000

export interface StationPrinter {
  name: string
  printer_name: string
  connection: string
  disabled: 0 | 1
  online: boolean | null
}

interface Job {
  job: string
  kind: string
  ticket: {
    outlet?: string
    kot_no: number | null
    label?: string
    order_type?: string | null
    order?: string
    customer?: string | null
    address?: string | null
    nc?: boolean
    nc_by?: string | null
    reprint?: boolean
    station?: string | null
    fallback_from?: string | null
    copies?: number
    items: KotLine[]
  }
}

export function getStationPrinter(): string {
  try { return localStorage.getItem(KEY) || "" } catch { return "" }
}

function setStationPrinter(name: string) {
  try {
    if (name) localStorage.setItem(KEY, name)
    else localStorage.removeItem(KEY)
  } catch { /* private window: the choice lasts this session only */ }
}

/** Run the print-station loop for the printer chosen on this device. */
export function usePrintStation() {
  const [printer, setPrinter] = useState(getStationPrinter)
  const [last, setLast] = useState<{ at: Date; count: number } | null>(null)
  const [error, setError] = useState<string | null>(null)

  const choose = (name: string) => { setStationPrinter(name); setPrinter(name); setError(null) }

  useEffect(() => {
    if (!printer) return
    let running = false
    let stopped = false
    const run = async () => {
      if (running || stopped) return
      running = true
      try {
        const jobs = await call<Job[]>("kamra.printing.claim_jobs", { printer })
        setError(null)
        if (!jobs.length) return
        const bodies = jobs.flatMap((j) => {
          const one = kotHtml({
            outlet: j.ticket.outlet || "", kot_no: j.ticket.kot_no, label: j.ticket.label || "",
            order_type: j.ticket.order_type, order: j.ticket.order || "",
            reprint: !!j.ticket.reprint || j.kind === "Reprint", customer: j.ticket.customer,
            address: j.ticket.address, nc: !!j.ticket.nc, nc_by: j.ticket.nc_by,
            items: j.ticket.items || [], station: j.ticket.station, kind: j.kind,
            fallback_from: j.ticket.fallback_from,
          })
          return Array.from({ length: Math.max(1, j.ticket.copies || 1) }, () => one)
        })
        const ids = jobs.map((j) => j.job)
        // One print for the batch: a second iframe would cancel the first.
        const ok = printThermal(`KOT ${jobs[0].ticket.kot_no ?? ""}`, joinTickets(bodies))
        await call("kamra.printing.ack_jobs", ok
          ? { printer, printed: JSON.stringify(ids) }
          : { printer, failed: JSON.stringify(ids), error: "The browser could not open the print view." })
        if (ok) setLast({ at: new Date(), count: jobs.length })
      } catch (e) {
        setError(e instanceof Error ? e.message : String(e))
      } finally {
        running = false
      }
    }
    void run()
    const unsub = subscribeRealtime(() => { void run() }, {
      event: "kamra_print",
      filter: (e) => !e.printer || e.printer === printer,
      fallbackMs: POLL_MS,
    })
    const t = setInterval(() => { void run() }, POLL_MS)
    return () => { stopped = true; unsub(); clearInterval(t) }
  }, [printer])

  return { printer, choose, last, error }
}
