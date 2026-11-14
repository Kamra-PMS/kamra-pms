import { useState } from "react"
import { ExternalLink } from "lucide-react"

/** A connected app's icon from its manifest, or a plain link mark when it
 *  has none or the image fails to load. */
export default function ConnectedAppIcon({ src }: { src?: string | null }) {
  const [broken, setBroken] = useState(false)
  if (!src || broken)
    return <ExternalLink className="size-4" strokeWidth={1.75} aria-hidden />
  return (
    <img
      src={src}
      alt=""
      className="size-5 rounded object-contain"
      referrerPolicy="no-referrer"
      onError={() => setBroken(true)}
    />
  )
}
