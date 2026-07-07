import { ScrollText } from "lucide-react"

import { getCurrentProperty } from "../lib/api"
import { ActivityTab } from "./Agents"

/** The complete ledger - every action anyone took, human or AI. Admin view. */
export default function Activity() {
  return (
    <div className="space-y-4">
      <header className="flex items-center gap-2">
        <ScrollText className="size-5 text-brand-600" aria-hidden />
        <h1 className="text-xl font-semibold tracking-tight">Activity Log</h1>
        <p className="ml-2 text-sm text-zinc-500">
          Everything that happened on the property, by people and by AI.
        </p>
      </header>
      <ActivityTab property={getCurrentProperty()} />
    </div>
  )
}
