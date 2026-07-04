// Generic Frappe REST resource helpers (list/create/update/delete).

import { frappeFetch } from "./api"

export type Row = Record<string, unknown> & { name: string }

export async function listResource(
  doctype: string,
  opts: {
    fields: string[]
    filters?: (string | number)[][]
    orderBy?: string
    limit?: number
  },
): Promise<Row[]> {
  const params = new URLSearchParams({
    fields: JSON.stringify(opts.fields),
    limit_page_length: String(opts.limit ?? 100),
    order_by: opts.orderBy ?? "modified desc",
  })
  if (opts.filters?.length) params.set("filters", JSON.stringify(opts.filters))
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
  return (e as Error).message
}
