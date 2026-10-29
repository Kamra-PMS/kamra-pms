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

export { serverError } from "./api"
