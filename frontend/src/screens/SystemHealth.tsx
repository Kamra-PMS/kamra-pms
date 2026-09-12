import { useCallback, useEffect, useState } from "react"
import {
  AlertTriangle,
  CheckCircle2,
  ExternalLink,
  HeartPulse,
  Info,
  RefreshCw,
  XCircle,
} from "lucide-react"
import { call } from "../lib/api"
import { serverError } from "../lib/resource"
import { useT } from "../lib/i18n"
import { Button } from "../components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card"

type CheckStatus = "passed" | "attention" | "failed" | "info"

type HealthCheck = {
  id: string
  title: string
  status: CheckStatus
  detail: string
  link?: string | null
}

type HealthPayload = {
  overall: CheckStatus
  summary: Record<CheckStatus, number>
  installed: { kamra: string; frappe: string | null; site: string }
  latest: {
    ok: boolean
    tag: string | null
    name: string | null
    url: string
    published_at: string | null
    error?: string | null
    body_preview?: string
  }
  upgrade: {
    docs: string
    releases: string
    docker_latest: string
    docker_nightly: string
    bench: string
    note: string
  }
  checks: HealthCheck[]
}

const STATUS_STYLE: Record<
  CheckStatus,
  { label: string; dot: string; text: string; Icon: typeof CheckCircle2 }
> = {
  passed: {
    label: "Passed",
    dot: "bg-emerald-500",
    text: "text-emerald-700",
    Icon: CheckCircle2,
  },
  attention: {
    label: "Needs attention",
    dot: "bg-rose-500",
    text: "text-rose-700",
    Icon: AlertTriangle,
  },
  failed: {
    label: "Failed",
    dot: "bg-rose-600",
    text: "text-rose-800",
    Icon: XCircle,
  },
  info: {
    label: "Info",
    dot: "bg-sky-500",
    text: "text-sky-700",
    Icon: Info,
  },
}

function StatusPill({ status }: { status: CheckStatus }) {
  const { t } = useT()
  const s = STATUS_STYLE[status]
  return (
    <span className={`inline-flex items-center gap-1.5 text-sm font-medium ${s.text}`}>
      <span className={`size-2 rounded-full ${s.dot}`} aria-hidden />
      {t(s.label)}
    </span>
  )
}

export default function SystemHealth() {
  const { t } = useT()
  const [data, setData] = useState<HealthPayload | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const load = useCallback(async (refresh = false) => {
    setBusy(true)
    setError(null)
    try {
      const out = await call<HealthPayload>("kamra.health.system_health", {
        refresh: refresh ? 1 : 0,
      })
      setData(out)
    } catch (e) {
      setError(serverError(e))
    } finally {
      setBusy(false)
    }
  }, [])

  useEffect(() => {
    void load(false)
  }, [load])

  return (
    <div className="mx-auto max-w-3xl space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="flex items-center gap-2 text-lg font-semibold text-zinc-900">
            <HeartPulse className="size-5 text-brand-700" aria-hidden />
            {t("System Health")}
          </h1>
          <p className="mt-0.5 text-sm text-zinc-500">
            {t("Check the status of this Kamra site and whether a newer open-source release is available.")}
          </p>
        </div>
        <Button
          variant="outline"
          disabled={busy}
          onClick={() => void load(true)}
        >
          <RefreshCw className={`size-4 ${busy ? "animate-spin" : ""}`} aria-hidden />
          {t("Refresh")}
        </Button>
      </div>

      {error && (
        <p className="rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-800">
          {error}
        </p>
      )}

      {!data && !error && (
        <p className="py-10 text-center text-sm text-zinc-400">{t("Loading…")}</p>
      )}

      {data && (
        <>
          <Card>
            <CardHeader className="flex flex-row items-center justify-between gap-3">
              <CardTitle>{t("Overview")}</CardTitle>
              <StatusPill status={data.overall === "info" ? "passed" : data.overall} />
            </CardHeader>
            <CardContent className="grid gap-3 sm:grid-cols-3">
              <div className="rounded-lg border border-zinc-100 bg-zinc-50 px-3 py-2">
                <p className="text-[11px] font-medium uppercase tracking-wider text-zinc-400">
                  {t("Installed")}
                </p>
                <p className="mt-0.5 font-mono text-sm font-semibold">
                  kamra {data.installed.kamra}
                </p>
                <p className="text-xs text-zinc-500">
                  Frappe {data.installed.frappe ?? "—"}
                </p>
              </div>
              <div className="rounded-lg border border-zinc-100 bg-zinc-50 px-3 py-2">
                <p className="text-[11px] font-medium uppercase tracking-wider text-zinc-400">
                  {t("Latest on GitHub")}
                </p>
                <p className="mt-0.5 font-mono text-sm font-semibold">
                  {data.latest.tag ?? t("Unavailable")}
                </p>
                {data.latest.url && (
                  <a
                    href={data.latest.url}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex items-center gap-1 text-xs font-medium text-brand-700 hover:underline"
                  >
                    {t("Release notes")}
                    <ExternalLink className="size-3" aria-hidden />
                  </a>
                )}
              </div>
              <div className="rounded-lg border border-zinc-100 bg-zinc-50 px-3 py-2">
                <p className="text-[11px] font-medium uppercase tracking-wider text-zinc-400">
                  {t("Site")}
                </p>
                <p className="mt-0.5 truncate font-mono text-sm font-semibold">
                  {data.installed.site}
                </p>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>{t("Checks")}</CardTitle>
            </CardHeader>
            <CardContent className="divide-y divide-zinc-100">
              {data.checks.map((c) => {
                const style = STATUS_STYLE[c.status]
                return (
                  <div
                    key={c.id}
                    className="flex flex-wrap items-start justify-between gap-3 py-3 first:pt-0 last:pb-0"
                  >
                    <div className="min-w-0 flex-1">
                      <p className="flex items-center gap-1.5 text-sm font-medium text-zinc-800">
                        <style.Icon className={`size-4 shrink-0 ${style.text}`} aria-hidden />
                        {t(c.title)}
                        {c.link && (
                          <a
                            href={c.link}
                            target={c.link.startsWith("http") ? "_blank" : undefined}
                            rel="noreferrer"
                            className="text-zinc-400 hover:text-brand-700"
                            aria-label={t("Open details")}
                          >
                            <ExternalLink className="size-3.5" />
                          </a>
                        )}
                      </p>
                      <p className="mt-0.5 text-sm text-zinc-500">{c.detail}</p>
                    </div>
                    <StatusPill status={c.status} />
                  </div>
                )
              })}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>{t("How to upgrade")}</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3 text-sm text-zinc-600">
              <p>{t(data.upgrade.note)}</p>
              <div className="rounded-lg border border-zinc-200 bg-zinc-50 px-3 py-2">
                <p className="text-xs font-medium uppercase tracking-wider text-zinc-400">
                  {t("Docker (self-host)")}
                </p>
                <code className="mt-1 block break-all font-mono text-xs text-zinc-800">
                  docker pull {data.upgrade.docker_latest}
                </code>
                <p className="mt-1 text-xs text-zinc-500">
                  {t("Then recreate the stack / run migrate. Nightly channel")}:{" "}
                  <code className="font-mono">{data.upgrade.docker_nightly}</code>
                </p>
              </div>
              <div className="rounded-lg border border-zinc-200 bg-zinc-50 px-3 py-2">
                <p className="text-xs font-medium uppercase tracking-wider text-zinc-400">
                  {t("Bench")}
                </p>
                <code className="mt-1 block whitespace-pre-wrap break-all font-mono text-xs text-zinc-800">
                  {data.upgrade.bench}
                </code>
              </div>
              <div className="flex flex-wrap gap-3">
                <a
                  href={data.upgrade.releases}
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex items-center gap-1 text-sm font-medium text-brand-700 hover:underline"
                >
                  {t("GitHub releases")}
                  <ExternalLink className="size-3.5" aria-hidden />
                </a>
                <a
                  href={data.upgrade.docs}
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex items-center gap-1 text-sm font-medium text-brand-700 hover:underline"
                >
                  {t("Self-hosting docs")}
                  <ExternalLink className="size-3.5" aria-hidden />
                </a>
              </div>
            </CardContent>
          </Card>
        </>
      )}
    </div>
  )
}
