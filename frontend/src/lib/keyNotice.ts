/** What the lock system said when keys were cancelled (api.reverse_check_in
 *  key_result), for the desk to read; null when there is nothing to say
 *  (manual keys, or no message). */
export function keyResultMessage(out?: { key_result?: { message?: string | null } | null } | null): string | null {
  const message = out?.key_result?.message?.trim()
  return message ? message : null
}
