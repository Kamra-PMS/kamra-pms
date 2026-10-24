import { useState } from "react"
import { useT } from "../lib/i18n"
import { PHONE_DIAL_CODES, dialForCountry, isPhoneComplete, joinPhone, phoneLengthForDial, splitPhone } from "../lib/phone"

/**
 * Default to the hotel's calling code, allowing a guest or booker to use any
 * international code. `value`/`onChange` stay fully qualified for storage.
 */
export default function PhoneInput(props: {
  value: string
  country?: string | null
  onChange: (phone: string) => void
  placeholder?: string
}) {
  const { t } = useT()
  const [selection, setSelection] = useState({ country: props.country, dial: "" })
  const stored = splitPhone(props.value, props.country)
  // Remember a selection even before a number is entered or after it is cleared.
  const dial = props.value
    ? stored.dial
    : (selection.country === props.country && selection.dial) || dialForCountry(props.country)
  const local = stored.local
  const { min, max } = phoneLengthForDial(dial)
  const invalid = !!props.value.trim() && !isPhoneComplete(props.value, props.country)
  const outsideRange = local.length < min || local.length > max

  function changeNumber(raw: string) {
    if (/^\s*(\+|00)/.test(raw)) {
      const pasted = splitPhone(raw, props.country)
      setSelection({ country: props.country, dial: pasted.dial })
      props.onChange(pasted.dial ? joinPhone(pasted.dial, pasted.local) : raw)
    } else {
      setSelection({ country: props.country, dial })
      const digits = joinPhone("", raw)
      props.onChange(dial ? joinPhone(dial, raw) : digits ? `+${digits}` : "")
    }
  }
  return (
    <>
      <div
        dir="ltr"
        className={
          "flex items-center gap-1.5 rounded-lg border bg-white pl-3.5 " +
          "focus-within:outline-2 focus-within:outline-offset-1 " +
          (invalid
            ? "border-rose-300 focus-within:outline-rose-500"
            : "border-zinc-300 focus-within:outline-brand-600")
        }
      >
        <select
          aria-label={t("Country calling code")}
          aria-invalid={invalid && !dial}
          title={t("Country calling code")}
          autoComplete="tel-country-code"
          className="w-24 shrink-0 bg-transparent py-2.5 text-base text-zinc-600 focus:outline-none"
          value={dial}
          onChange={(e) => {
            const nextDial = e.target.value
            setSelection({ country: props.country, dial: nextDial })
            props.onChange(joinPhone(nextDial, local))
          }}
        >
          <option value="" disabled>{t("Select")}</option>
          {PHONE_DIAL_CODES.map((code) => (
            <option key={code} value={code}>+{code}</option>
          ))}
        </select>
        <input
          type="tel"
          inputMode="numeric"
          autoComplete="tel-national"
          aria-label={t("Phone")}
          aria-invalid={invalid}
          className="w-full min-w-0 bg-transparent py-2.5 pr-3.5 text-base focus:outline-none"
          value={local}
          // Full international paste/autofill can change the selected code.
          // Keep all digits so an oversized number can be corrected, not truncated.
          onChange={(e) => changeNumber(e.target.value)}
          placeholder={props.placeholder ? t(props.placeholder) : dial === "91" ? "91488 69914" : t("Mobile number")}
        />
        <span className="shrink-0 pr-3.5 text-xs tabular-nums text-zinc-400">
          {local.length}/{max}
        </span>
      </div>
      {invalid && (
        <p className="mt-1.5 text-xs text-rose-600">
          {!dial
            ? t("Select a calling code.")
            : !outsideRange
              ? t("Check the phone number and calling code.")
              : min === max
                ? t("+{v0} numbers are {v1} digits.", { v0: String(dial), v1: String(min) })
                : t("+{v0} numbers are {v1}-{v2} digits.", { v0: String(dial), v1: String(min), v2: String(max) })}
        </p>
      )}
    </>
  )
}
