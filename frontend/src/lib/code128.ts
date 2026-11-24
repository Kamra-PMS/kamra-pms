/** Code 128, set B (ASCII 32-126): enough for order numbers like "ORD-2026-00042".
 *
 * Small and dependency-free. `code128Svg` returns one <svg> sized in millimetres so a
 * narrow bar is a whole number of printer dots (0.25 mm = 2 dots at 203 dpi), or an
 * empty string when the text cannot be encoded (a character outside ASCII 32-126).
 */

// Bar, space, bar, space, bar, space widths for symbol values 0..105.
const PATTERNS = [
  "212222", "222122", "222221", "121223", "121322", "131222", "122213", "122312", "132212", "221213",
  "221312", "231212", "112232", "122132", "122231", "113222", "123122", "123221", "223211", "221132",
  "221231", "213212", "223112", "312131", "311222", "321122", "321221", "312212", "322112", "322211",
  "212123", "212321", "232121", "111323", "131123", "131321", "112313", "132113", "132311", "211313",
  "231113", "231311", "112133", "112331", "132131", "113123", "113321", "133121", "313121", "211331",
  "231131", "213113", "213311", "213131", "311123", "311321", "331121", "312113", "312311", "332111",
  "314111", "221411", "431111", "111224", "111422", "121124", "121421", "141122", "141221", "112214",
  "112412", "122114", "122411", "142112", "142211", "241211", "221114", "413111", "241112", "134111",
  "111242", "121142", "121241", "114212", "124112", "124211", "411212", "421112", "421211", "212141",
  "214121", "412121", "111143", "111341", "131141", "114113", "114311", "411113", "411311", "113141",
  "114131", "311141", "411131", "211412", "211214", "211232",
]
const STOP = "2331112" // seven elements, ends with a bar
const START_B = 104

/** Alternating bar/space widths in modules, starting with a bar; null if the text cannot be encoded. */
export function code128Widths(text: string): number[] | null {
  if (!text) return null
  const values = [START_B]
  for (const ch of text) {
    const c = ch.charCodeAt(0)
    if (c < 32 || c > 126) return null
    values.push(c - 32)
  }
  let sum = START_B
  for (let i = 1; i < values.length; i++) sum += values[i] * i
  values.push(sum % 103)
  const widths: number[] = []
  for (const v of values) for (const d of PATTERNS[v]) widths.push(Number(d))
  for (const d of STOP) widths.push(Number(d))
  return widths
}

export function code128Svg(
  text: string,
  { moduleMm = 0.25, heightMm = 9, quiet = 10 }: { moduleMm?: number; heightMm?: number; quiet?: number } = {},
): string {
  const widths = code128Widths(text)
  if (!widths) return ""
  let x = quiet
  let d = ""
  widths.forEach((n, i) => {
    if (i % 2 === 0) d += `M${x} 0h${n}v1h-${n}z`
    x += n
  })
  const total = x + quiet
  const label = text.replace(/[&<>"]/g, "")
  return (
    `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${total} 1" preserveAspectRatio="none" ` +
    `width="${(total * moduleMm).toFixed(2)}mm" height="${heightMm}mm" shape-rendering="crispEdges" ` +
    `role="img" aria-label="${label}"><path d="${d}"/></svg>`
  )
}
