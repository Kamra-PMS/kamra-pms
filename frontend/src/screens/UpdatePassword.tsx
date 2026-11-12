/* Set a new password from a reset-email key (?key=), or change the current
   user's password when already signed in. Uses Frappe's update_password. */

import { useMemo, useState, type ReactNode } from "react"
import { Link, useNavigate, useSearchParams } from "react-router-dom"
import { serverError, updatePassword } from "../lib/api"
import { asset } from "../lib/asset"
import { useAuth } from "../lib/auth"
import { useT, t as translate } from "../lib/i18n"
import { Button } from "../components/ui/button"

const inputCls =
  "w-full rounded border border-[#E2E8F0] bg-[#ffffff] px-3 py-2 text-sm " +
  "text-[#191c1e] placeholder:text-[#6f7a71] " +
  "focus:outline-2 focus:outline-offset-1 focus:outline-[#1E7B4F]"

export default function UpdatePassword() {
  const { t } = useT()
  const { status, refresh } = useAuth()
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const key = (params.get("key") || "").trim()
  const expired = params.get("password_expired") === "true"
  const byKey = Boolean(key)

  const [oldPwd, setOldPwd] = useState("")
  const [pwd, setPwd] = useState("")
  const [confirm, setConfirm] = useState("")
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [done, setDone] = useState(false)

  const mismatch = useMemo(
    () => Boolean(confirm) && pwd !== confirm,
    [pwd, confirm],
  )

  // signed-out with no key: send them to forgot-password on login
  if (!byKey && status === "anon") {
    return (
      <Shell>
        <p className="text-sm text-[#3f4941]">
          {t("To reset your password, ask for a link from the sign-in screen.")}
        </p>
        <Link
          to="/login"
          className="mt-4 inline-block text-sm font-medium text-[#1E7B4F] hover:underline"
        >
          {t("Back to sign in")}
        </Link>
      </Shell>
    )
  }

  if (status === "loading" && !byKey) {
    return (
      <Shell>
        <p className="text-sm text-[#6f7a71]">{t("Loading…")}</p>
      </Shell>
    )
  }

  async function submit() {
    if (mismatch || !pwd) return
    setBusy(true)
    setError(null)
    try {
      await updatePassword({
        new_password: pwd,
        key: byKey ? key : undefined,
        old_password: byKey ? undefined : oldPwd,
      })
      setDone(true)
      await refresh()
      if (import.meta.env.PROD) {
        window.location.assign("/kamra/")
      } else {
        navigate("/", { replace: true })
      }
    } catch (e) {
      setError(serverError(e))
    } finally {
      setBusy(false)
    }
  }

  return (
    <Shell>
      <h1 className="mb-1 text-lg font-semibold text-[#1C3F38]">
        {expired
          ? t("Your password has expired")
          : byKey
            ? t("Choose a new password")
            : t("Change password")}
      </h1>
      <p className="mb-4 text-sm text-[#6f7a71]">
        {byKey
          ? t("Pick a password you have not used on this hotel before.")
          : t("Enter your current password, then the new one twice.")}
      </p>

      <form
        className="space-y-3"
        onSubmit={(e) => {
          e.preventDefault()
          submit()
        }}
      >
        {!byKey && (
          <label className="block">
            <span className="mb-1 block text-xs font-medium text-[#3f4941]">
              {t("Current password")}
            </span>
            <input
              className={inputCls}
              type="password"
              autoComplete="current-password"
              value={oldPwd}
              onChange={(e) => setOldPwd(e.target.value)}
              required
            />
          </label>
        )}
        <label className="block">
          <span className="mb-1 block text-xs font-medium text-[#3f4941]">
            {t("New password")}
          </span>
          <input
            className={inputCls}
            type="password"
            autoComplete="new-password"
            value={pwd}
            onChange={(e) => setPwd(e.target.value)}
            required
          />
        </label>
        <label className="block">
          <span className="mb-1 block text-xs font-medium text-[#3f4941]">
            {t("Confirm new password")}
          </span>
          <input
            className={inputCls}
            type="password"
            autoComplete="new-password"
            value={confirm}
            onChange={(e) => setConfirm(e.target.value)}
            required
          />
        </label>

        {mismatch && (
          <p className="text-sm text-[#93000a]">{t("The new passwords do not match.")}</p>
        )}
        {error && (
          <div className="rounded border border-[#ffdad6] bg-[#fff8f7] px-3 py-2 text-sm text-[#93000a]">
            {translate(error)}
          </div>
        )}
        {done && (
          <p className="text-sm text-[#1E7B4F]">{t("Password updated. Signing you in…")}</p>
        )}

        <Button
          className="w-full justify-center rounded bg-[#1E7B4F] py-2 text-white hover:bg-[#00613a]"
          disabled={
            busy ||
            mismatch ||
            !pwd ||
            !confirm ||
            (!byKey && !oldPwd)
          }
          type="submit"
        >
          {busy ? t("Saving…") : t("Save password")}
        </Button>
      </form>

      {!byKey && (
        <Link
          to="/"
          className="mt-4 inline-block text-sm text-[#6f7a71] hover:text-[#1E7B4F]"
        >
          {t("Cancel")}
        </Link>
      )}
    </Shell>
  )
}

function Shell(props: { children: ReactNode }) {
  return (
    <div
      className="flex min-h-[100dvh] flex-col items-center justify-center bg-[#f7f9fb] px-4"
      style={{ colorScheme: "light" }}
    >
      <div className="fixed inset-x-0 top-0 h-[5px] bg-[#1C3F38]" aria-hidden />
      <div className="w-full max-w-sm">
        <div className="mb-6 flex flex-col items-center gap-2">
          <img src={asset("kamra-mark.svg")} alt="Kamra" className="size-16" />
          <span
            className="text-2xl font-semibold tracking-[0.02em] text-[#1C3F38]"
            style={{ fontFamily: "Montserrat, ui-sans-serif, system-ui, sans-serif" }}
          >
            kamra
            <span className="ml-1.5 align-middle text-[10px] font-semibold tracking-[0.4em] text-[#1E7B4F]">
              PMS
            </span>
          </span>
        </div>
        <div className="rounded border border-[#E2E8F0] bg-white p-6">{props.children}</div>
      </div>
    </div>
  )
}
