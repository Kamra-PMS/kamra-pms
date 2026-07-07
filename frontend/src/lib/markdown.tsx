import { Fragment, type ReactNode } from "react"

// Minimal, dependency-free markdown for the copilot's replies - bold, italic,
// inline code, links, and bullet/numbered lists. Renders to React elements
// (no HTML injection), so it's XSS-safe by construction.

const INLINE =
  /(\*\*([^*]+)\*\*|\*([^*]+)\*|`([^`]+)`|\[([^\]]+)\]\(([^)\s]+)\))/g

function renderInline(text: string): ReactNode[] {
  const out: ReactNode[] = []
  let last = 0
  let key = 0
  let m: RegExpExecArray | null
  INLINE.lastIndex = 0
  while ((m = INLINE.exec(text))) {
    if (m.index > last) out.push(text.slice(last, m.index))
    if (m[2]) out.push(<strong key={key++}>{m[2]}</strong>)
    else if (m[3]) out.push(<em key={key++}>{m[3]}</em>)
    else if (m[4])
      out.push(
        <code key={key++} className="rounded bg-black/10 px-1 py-0.5 text-[0.85em]">
          {m[4]}
        </code>,
      )
    else if (m[5])
      out.push(
        <a
          key={key++}
          href={m[6]}
          target="_blank"
          rel="noreferrer"
          className="underline"
        >
          {m[5]}
        </a>,
      )
    last = m.index + m[0].length
  }
  if (last < text.length) out.push(text.slice(last))
  return out
}

export function Markdown({ text }: { text: string }) {
  const lines = text.split("\n")
  const blocks: ReactNode[] = []
  let listType: "ul" | "ol" | null = null
  let items: string[] = []

  const flushList = (key: string) => {
    if (!listType) return
    const lis = items.map((it, i) => <li key={i}>{renderInline(it)}</li>)
    blocks.push(
      listType === "ul" ? (
        <ul key={key} className="list-disc space-y-0.5 pl-5">
          {lis}
        </ul>
      ) : (
        <ol key={key} className="list-decimal space-y-0.5 pl-5">
          {lis}
        </ol>
      ),
    )
    listType = null
    items = []
  }

  lines.forEach((line, i) => {
    const heading = line.match(/^\s*#{1,6}\s+(.*)/)
    const bullet = line.match(/^\s*[-*]\s+(.*)/)
    const num = line.match(/^\s*\d+\.\s+(.*)/)
    if (heading) {
      flushList("l" + i)
      blocks.push(
        <p key={"h" + i} className="font-semibold">
          {renderInline(heading[1])}
        </p>,
      )
    } else if (bullet) {
      if (listType !== "ul") flushList("l" + i)
      listType = "ul"
      items.push(bullet[1])
    } else if (num) {
      if (listType !== "ol") flushList("l" + i)
      listType = "ol"
      items.push(num[1])
    } else {
      flushList("l" + i)
      if (line.trim())
        blocks.push(<p key={"p" + i}>{renderInline(line)}</p>)
    }
  })
  flushList("lend")

  return <Fragment>{blocks}</Fragment>
}
