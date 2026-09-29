export function cn(...classes: Array<string | false | null | undefined>) {
  return classes.filter(Boolean).join(" ")
}

/** Plain text of a server message that may carry HTML. A single
 *  /<[^>]+>/ pass can leave a tag behind from nested input ("<scr<b>ipt"),
 *  so strip until nothing changes, then drop any stray angle bracket - the
 *  result can never contain markup. It is only ever rendered as text. */
export function htmlToText(s: string): string {
  let out = s
  let prev: string
  do {
    prev = out
    out = out.replace(/<[^<>]*>/g, "")
  } while (out !== prev)
  return out.replace(/[<>]/g, "")
}
