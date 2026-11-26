/*  Makes the figures on a printed bill add up.

    Money is printed in whole units of the currency (no decimals for IDR or JPY, two
    for USD or SAR, three for KWD). Rounding each figure on its own means the printed
    lines can miss the printed subtotal by a unit or two. This turns the exact figures
    the server sent into the units that are printed, with one rule:

      subtotal = the sum of the printed lines
      rounding = printed total - (subtotal - discount + levy + tax)

    The rounding is 0 on most bills. When it is not, the bill prints it as its own
    "Rounding" line, so every printed figure adds up and the tax and the total stay
    exactly what the server calculated. Print only: nothing stored or calculated
    on the server changes. */

export interface AddUpInput {
  /** decimals the currency is printed with (moneyDigits()) */
  digits: number
  /** the exact amount of each line, after voids */
  lines: number[]
  discount?: number
  levy?: number
  /** each tax part (CGST + SGST, or one VAT line) */
  taxes?: number[]
  /** the exact amount the guest is charged */
  total: number
}

export interface AddUpFigures {
  digits: number
  /** every figure below is exact at `digits` decimals: it is what gets printed */
  lines: number[]
  subtotal: number
  discount: number
  levy: number
  taxes: number[]
  total: number
  /** 0 when the printed pieces already add up to the printed total */
  rounding: number
}

/** An amount in whole units, rounded the way Intl prints it (half away from zero, on the
 *  shortest decimal form, so 1.005 at 2 digits is 101 units, as the formatter shows it). */
export function toUnits(amount: number, digits: number): number {
  const scaled = Math.abs(Number(amount) || 0) * 10 ** digits
  const units = Math.round(Number(scaled.toPrecision(15)))
  return (Number(amount) || 0) < 0 && units !== 0 ? -units : units   // never -0
}

export function addUp(input: AddUpInput): AddUpFigures {
  const d = input.digits
  const unit = (n: number) => toUnits(n, d)
  const back = (u: number) => u / 10 ** d
  const lines = input.lines.map(unit)
  const taxes = (input.taxes ?? []).map(unit)
  const subtotal = lines.reduce((s, u) => s + u, 0)
  const discount = unit(input.discount ?? 0)
  const levy = unit(input.levy ?? 0)
  const total = unit(input.total)
  const rounding = total - (subtotal - discount + levy + taxes.reduce((s, u) => s + u, 0))
  return {
    digits: d,
    lines: lines.map(back),
    subtotal: back(subtotal),
    discount: back(discount),
    levy: back(levy),
    taxes: taxes.map(back),
    total: back(total),
    rounding: back(rounding),
  }
}
