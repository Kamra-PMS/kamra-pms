/*  What the signed-in user may do, from Frappe's role permissions.

    Every staff action on the server is gated on a permission type of a
    doctype (Role Permission Manager in Desk). whoami returns the ones this
    user holds; screens ask hasPerm(...) to show a menu or a button. The
    role list is only the fallback for a server that doesn't send them. */

export type Can = Record<string, string[]> | null

export function hasPerm(
  can: Can,
  roles: string[],
  doctype: string,
  ptype: string,
  fallbackRoles: string[] = [],
): boolean {
  if (can) return !!can[doctype]?.includes(ptype)
  return fallbackRoles.some((r) => roles.includes(r))
}
