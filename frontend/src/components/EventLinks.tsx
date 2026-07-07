import { useEffect, useState } from "react"
import { useNavigate } from "react-router-dom"
import { Receipt } from "lucide-react"

import { call } from "../lib/api"
import { serverError, type Row } from "../lib/resource"
import { Button } from "./ui/button"
import LinkedRecords from "./LinkedRecords"

/** Billing & connections for an event: chips to everything it touches, and
 *  a one-tap path to the group folio (rooms + banquet on one bill). */
export default function EventLinks({
  row,
  reload,
}: {
  row: Row
  reload: () => void
}) {
  const name = String(row.name)
  const [group, setGroup] = useState<string | null>(null)
  const [hasFolio, setHasFolio] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const navigate = useNavigate()

  useEffect(() => {
    call<{ group_booking: string | null; folios: { name: string }[] }>(
      "kamra.api.linked_records",
      { doctype: "Venue Booking", name },
    )
      .then((l) => {
        setGroup(l.group_booking)
        setHasFolio(l.folios.length > 0)
      })
      .catch(() => {})
  }, [name])

  return (
    <div className="space-y-3 border-t border-zinc-200 pt-4">
      <div className="text-xs font-semibold uppercase tracking-wider text-zinc-500">
        Connections & billing
      </div>
      <LinkedRecords doctype="Venue Booking" name={name} exclude={["event"]} />
      {group && !hasFolio && (
        <Button
          variant="outline"
          disabled={busy}
          onClick={async () => {
            setBusy(true)
            setError(null)
            try {
              const r = await call<{ folio: string }>(
                "kamra.api.group_master_folio",
                { group_booking: group },
              )
              navigate(`/billing/${encodeURIComponent(r.folio)}`)
              reload()
            } catch (e) {
              setError(serverError(e))
            } finally {
              setBusy(false)
            }
          }}
        >
          <Receipt className="size-4" aria-hidden />
          Open group folio (bill this event)
        </Button>
      )}
      {!group && (
        <p className="text-xs text-zinc-500">
          To bill this event, attach it to a group in Groups &amp; Blocks -
          rooms and banquet then land on one folio.
        </p>
      )}
      {error && <p className="text-xs text-rose-600">{error}</p>}
    </div>
  )
}
