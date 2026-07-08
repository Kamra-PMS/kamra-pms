import { useEffect, useRef, useState } from "react"

/** A small draw-with-finger/mouse signature box. Emits a PNG data URL on each
 *  stroke end; empty until the guest draws something. */
export function SignaturePad({ onChange }: { onChange: (dataUrl: string) => void }) {
  const ref = useRef<HTMLCanvasElement>(null)
  const drawing = useRef(false)
  const drawn = useRef(false)
  const [empty, setEmpty] = useState(true)

  useEffect(() => {
    const c = ref.current
    if (!c) return
    const ctx = c.getContext("2d")
    if (!ctx) return
    ctx.lineWidth = 2
    ctx.lineCap = "round"
    ctx.strokeStyle = "#18181b"
  }, [])

  function point(e: React.PointerEvent) {
    const c = ref.current!
    const r = c.getBoundingClientRect()
    return {
      x: (e.clientX - r.left) * (c.width / r.width),
      y: (e.clientY - r.top) * (c.height / r.height),
    }
  }

  function down(e: React.PointerEvent) {
    drawing.current = true
    const ctx = ref.current!.getContext("2d")!
    const p = point(e)
    ctx.beginPath()
    ctx.moveTo(p.x, p.y)
    ;(e.target as Element).setPointerCapture?.(e.pointerId)
  }
  function move(e: React.PointerEvent) {
    if (!drawing.current) return
    const ctx = ref.current!.getContext("2d")!
    const p = point(e)
    ctx.lineTo(p.x, p.y)
    ctx.stroke()
    drawn.current = true
    if (empty) setEmpty(false)
  }
  function up() {
    if (!drawing.current) return
    drawing.current = false
    onChange(drawn.current ? ref.current!.toDataURL("image/png") : "")
  }
  function clear() {
    const c = ref.current!
    c.getContext("2d")!.clearRect(0, 0, c.width, c.height)
    drawn.current = false
    setEmpty(true)
    onChange("")
  }

  return (
    <div>
      <div className="relative overflow-hidden rounded-lg border border-zinc-300 bg-white">
        <canvas
          ref={ref}
          width={560}
          height={160}
          className="h-40 w-full touch-none"
          onPointerDown={down}
          onPointerMove={move}
          onPointerUp={up}
          onPointerLeave={up}
        />
        {empty && (
          <span className="pointer-events-none absolute inset-0 flex items-center justify-center text-sm text-zinc-300">
            Sign here
          </span>
        )}
      </div>
      <button
        type="button"
        onClick={clear}
        className="mt-1 text-xs font-medium text-zinc-400 hover:text-zinc-600"
      >
        Clear
      </button>
    </div>
  )
}
