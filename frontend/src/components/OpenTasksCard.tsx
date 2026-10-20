/*  Today widget: rooms with open housekeeping work (pending or in
    progress), who has it, and a way into the room. Reads rooms_board. */

import { useEffect, useState } from "react"
import { Link } from "react-router-dom"
import { ListChecks } from "lucide-react"
import { getRoomsBoard, type BoardRoom } from "../lib/rooms"
import { serverError } from "../lib/resource"
import { useT } from "../lib/i18n"
import { Badge } from "./ui/badge"
import { Card, CardContent, CardHeader, CardTitle } from "./ui/card"

export default function OpenTasksCard({ refreshKey }: { refreshKey?: number }) {
  const { t } = useT()
  const [rows, setRows] = useState<BoardRoom[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  useEffect(() => {
    getRoomsBoard()
      .then((b) => setRows(b.rooms.filter((r) => r.task)))
      .catch((e) => setError(serverError(e)))
  }, [refreshKey])
  return (
    <Card>
      <CardHeader>
        <CardTitle>{t("Open tasks")}</CardTitle>
        <ListChecks className="size-4 text-zinc-400" aria-hidden />
      </CardHeader>
      <CardContent className="pt-1">
        {error ? (
          <p className="text-sm text-rose-700">{error}</p>
        ) : rows === null ? (
          <p className="py-3 text-sm text-zinc-400">{t("Loading…")}</p>
        ) : rows.length === 0 ? (
          <p className="px-1 py-3 text-sm text-zinc-400">{t("No open housekeeping tasks.")}</p>
        ) : (
          <ul className="divide-y divide-zinc-100">
            {rows.map((r) => (
              <li key={r.name}>
                <Link
                  to={`/room-board?room=${encodeURIComponent(r.name)}`}
                  className="flex min-h-11 items-center gap-3 py-2"
                >
                  <span className="w-12 shrink-0 font-semibold tabular-nums">{r.room_number}</span>
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-sm font-medium text-zinc-800">
                      {t(r.task!.type)}
                    </span>
                    <span className="block truncate text-xs text-zinc-500">
                      {r.task!.assignee ?? t("Not assigned")}
                    </span>
                  </span>
                  <Badge tone={r.task!.status === "In Progress" ? "sky" : "zinc"}>
                    {t(r.task!.status)}
                  </Badge>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  )
}
