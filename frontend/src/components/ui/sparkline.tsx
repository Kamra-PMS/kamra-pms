/**
 * A tiny inline trend line. Pure SVG, no library. Give it a short series and
 * it draws a smoothed-ish polyline with a soft area fill and an emphasized
 * endpoint - the micro-chart under each headline figure.
 */
export function Sparkline({
  data,
  color = "var(--color-brand-600)",
  width = 96,
  height = 32,
  fill = true,
}: {
  data: number[]
  color?: string
  width?: number
  height?: number
  fill?: boolean
}) {
  if (!data || data.length < 2) return null
  const min = Math.min(...data)
  const max = Math.max(...data)
  const span = max - min || 1
  const pad = 2
  const w = width - pad * 2
  const h = height - pad * 2
  const pts = data.map((v, i) => {
    const x = pad + (i / (data.length - 1)) * w
    const y = pad + h - ((v - min) / span) * h
    return [x, y] as const
  })
  const line = pts.map(([x, y]) => `${x.toFixed(1)},${y.toFixed(1)}`).join(" ")
  const area = `${pad},${height - pad} ${line} ${width - pad},${height - pad}`
  const [ex, ey] = pts[pts.length - 1]
  const id = `sg-${Math.round(pts[0][1])}-${data.length}-${Math.round(max)}`
  return (
    <svg
      width={width}
      height={height}
      viewBox={`0 0 ${width} ${height}`}
      className="overflow-visible"
      aria-hidden
    >
      {fill && (
        <>
          <defs>
            <linearGradient id={id} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={color} stopOpacity="0.18" />
              <stop offset="100%" stopColor={color} stopOpacity="0" />
            </linearGradient>
          </defs>
          <polygon points={area} fill={`url(#${id})`} />
        </>
      )}
      <polyline
        points={line}
        fill="none"
        stroke={color}
        strokeWidth="1.75"
        strokeLinejoin="round"
        strokeLinecap="round"
      />
      <circle cx={ex} cy={ey} r="2.4" fill={color} />
    </svg>
  )
}
