import { useNavigate } from "react-router-dom"
import { Store } from "lucide-react"

import { useAuth } from "../lib/auth"
import { visibleApps, type AppDef } from "../lib/apps"

/** The suite launcher - the "all apps" home. Opens an app by routing to its
 *  first screen. Also the front door to the Marketplace. */
export default function AppLauncher() {
  const { roles } = useAuth()
  const navigate = useNavigate()
  const apps = visibleApps(roles)
  const canMarket = ["Hotel Admin", "System Manager", "Administrator"].some(
    (r) => roles.includes(r),
  )

  const open = (app: AppDef) => {
    const first = app.items.find((i) => i.to)
    if (first?.to) navigate(first.to)
  }

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-xl font-semibold tracking-tight">Your apps</h1>
        <p className="mt-0.5 text-sm text-zinc-500">
          Everything Kamra does, one room at a time. Pick where you want to
          work.
        </p>
      </header>

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {apps.map((app) => (
          <button
            key={app.id}
            onClick={() => open(app)}
            className="group flex items-start gap-3 rounded-2xl border border-zinc-200 bg-white p-4 text-left transition hover:border-brand-300 hover:shadow-sm"
          >
            <span
              className={`flex size-11 shrink-0 items-center justify-center rounded-xl ${app.tint}`}
            >
              <app.icon className="size-5" aria-hidden />
            </span>
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <span className="font-semibold text-zinc-800">{app.name}</span>
              </div>
              <p className="mt-0.5 text-sm text-zinc-500">{app.description}</p>
            </div>
          </button>
        ))}
      </div>

      {canMarket && (
        <button
          onClick={() => navigate("/marketplace")}
          className="flex w-full items-center gap-3 rounded-2xl border border-dashed border-zinc-300 bg-zinc-50 p-4 text-left hover:border-brand-300 hover:bg-white"
        >
          <span className="flex size-11 shrink-0 items-center justify-center rounded-xl bg-white text-brand-600">
            <Store className="size-5" aria-hidden />
          </span>
          <div>
            <div className="font-semibold text-zinc-800">Marketplace</div>
            <p className="mt-0.5 text-sm text-zinc-500">
              Add channels, payments, accounting and country packs - and see
              what's included in your plan.
            </p>
          </div>
        </button>
      )}
    </div>
  )
}
