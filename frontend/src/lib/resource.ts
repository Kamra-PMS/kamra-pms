// Generic Frappe REST resource helpers (list/create/update/delete).

import { frappeFetch } from "./api"

export type Row = Record<string, unknown> & { name: string }

export async function listResource(
  doctype: string,
  opts: {
    fields: string[]
    filters?: (string | number)[][]
    orFilters?: (string | number)[][]
    orderBy?: string
    limit?: number
    start?: number
  },
): Promise<Row[]> {
  const params = new URLSearchParams({
    fields: JSON.stringify(opts.fields),
    limit_page_length: String(opts.limit ?? 100),
    limit_start: String(opts.start ?? 0),
    order_by: opts.orderBy ?? "modified desc",
  })
  if (opts.filters?.length) params.set("filters", JSON.stringify(opts.filters))
  if (opts.orFilters?.length)
    params.set("or_filters", JSON.stringify(opts.orFilters))
  const res = await frappeFetch<{ data: Row[] }>(
    `/api/resource/${encodeURIComponent(doctype)}?${params}`,
  )
  return res.data
}

export async function createResource(
  doctype: string,
  data: Record<string, unknown>,
) {
  return frappeFetch(`/api/resource/${encodeURIComponent(doctype)}`, {
    method: "POST",
    body: JSON.stringify(data),
  })
}

export async function updateResource(
  doctype: string,
  name: string,
  data: Record<string, unknown>,
) {
  return frappeFetch(
    `/api/resource/${encodeURIComponent(doctype)}/${encodeURIComponent(name)}`,
    { method: "PUT", body: JSON.stringify(data) },
  )
}

export async function deleteResource(doctype: string, name: string) {
  return frappeFetch(
    `/api/resource/${encodeURIComponent(doctype)}/${encodeURIComponent(name)}`,
    { method: "DELETE" },
  )
}

export function serverError(e: unknown): string {
  const body = (e as { body?: string }).body
  if (body) {
    try {
      const parsed = JSON.parse(body)
      const msgs = JSON.parse(parsed._server_messages ?? "[]")
      if (msgs.length) {
        const first = JSON.parse(msgs[0])
        return String(first.message).replace(/<[^>]+>/g, "")
      }
      if (parsed.exception) return String(parsed.exception).split(":").pop()!
    } catch {
      /* ignore */
    }
  }
  // no readable server message: translate, never show debug internals
  if ((e as { network?: boolean }).network) return (e as Error).message
  const status = (e as { status?: number }).status
  if (status === 401 || status === 403)
    return "You don't have permission for that, or your session ended — sign in again if this persists."
  if (status === 404) return "That record wasn't found — it may have been removed."
  if (status === 429) return "Too many requests — give it a few seconds and try again."
  if (status && status >= 500)
    return "Something went wrong on the server. Try again in a moment."
  if (status) return "That didn't go through. Please try again."
  console.warn("[kamra] unexpected error", e)
  return "Something unexpected went wrong. Try again — if it keeps happening, let your admin know."
}
