import { useEffect, useState } from "react"
import { Link, useParams } from "react-router-dom"
import { LanguageSwitcher } from "../components/LanguageSwitcher"
import { callGuest } from "../lib/api"
import { adoptGuestLanguage } from "../lib/dir"
import { useT } from "../lib/i18n"

interface Site {
  enabled: boolean
  stay_path?: string
  property?: {
    property_name?: string
    description?: string | null
    city?: string | null
    state?: string | null
    phone?: string | null
    email?: string | null
    hero_image?: string | null
    logo_url?: string | null
    house_rules?: string | null
    pets_policy?: string | null
    children_policy?: string | null
    checkin_time?: string
    checkout_time?: string
    gallery?: { url: string; caption?: string | null }[]
    faqs?: { question: string; answer: string }[]
  }
  room_types?: {
    name: string
    room_type_name: string
    description?: string | null
    base_price?: number
    amenities?: string[]
  }[]
  facilities?: { area: string; items: string[] }[]
}

const SECTIONS = ["rooms", "facilities", "gallery", "policies", "faq"] as const

/** Public property website. Community hotels keep the booking page at /stay. */
export default function PropertyWebsite() {
  const { slug = "" } = useParams()
  const { t } = useT()
  const [site, setSite] = useState<Site | null>(null)
  const [error, setError] = useState("")

  useEffect(() => {
    adoptGuestLanguage()
  }, [])

  useEffect(() => {
    let live = true
    callGuest<Site>("kamra.enterprise.property_site", { slug })
      .then((data) => {
        if (live) setSite(data)
      })
      .catch((err: Error) => {
        if (live) setError(err.message || t("This page is not available."))
      })
    return () => {
      live = false
    }
  }, [slug, t])

  if (error) {
    return <p className="p-10 text-center text-sm text-zinc-500">{error}</p>
  }
  if (!site) {
    return <p className="p-10 text-center text-sm text-zinc-400">{t("Loading…")}</p>
  }
  if (!site.enabled) {
    return (
      <main className="mx-auto max-w-lg p-10 text-center">
        <h1 className="text-2xl font-semibold text-zinc-900">{t("Book direct")}</h1>
        <p className="mt-3 text-sm text-zinc-600">
          {t("The full property website is part of Kamra Enterprise. You can still book on the property page.")}
        </p>
        {site.stay_path && (
          <Link to={site.stay_path} className="mt-6 inline-block rounded-lg bg-brand-700 px-4 py-2 text-sm font-medium text-white">
            {t("Continue to booking")}
          </Link>
        )}
      </main>
    )
  }

  const property = site.property || {}
  const place = [property.city, property.state].filter(Boolean).join(", ")

  return (
    <main className="min-h-screen bg-zinc-50 text-zinc-900">
      <header className="border-b border-zinc-200 bg-white">
        <div className="mx-auto flex max-w-5xl items-center gap-4 px-4 py-4">
          {property.logo_url && (
            <img src={property.logo_url} alt="" className="size-10 rounded-md object-contain" />
          )}
          <div className="min-w-0">
            <p className="truncate text-lg font-semibold">{property.property_name}</p>
            {place && <p className="truncate text-xs text-zinc-500">{place}</p>}
          </div>
          <nav className="ms-auto hidden gap-4 text-sm text-zinc-600 md:flex">
            {SECTIONS.map((id) => (
              <a key={id} href={`#${id}`} className="hover:text-brand-700">{t(sectionLabel(id))}</a>
            ))}
          </nav>
          <LanguageSwitcher />
          <Link to={site.stay_path || `/stay/${slug}`} className="rounded-lg bg-brand-700 px-3 py-2 text-sm font-medium text-white">
            {t("Book")}
          </Link>
        </div>
      </header>

      <section
        className="bg-zinc-900 bg-cover bg-center text-white"
        style={property.hero_image ? { backgroundImage: `linear-gradient(rgba(0,0,0,.45), rgba(0,0,0,.45)), url(${property.hero_image})` } : undefined}
      >
        <div className="mx-auto max-w-5xl px-4 py-20">
          <h1 className="text-4xl font-semibold">{property.property_name}</h1>
          {property.description && <p className="mt-4 max-w-2xl text-lg text-zinc-100">{property.description}</p>}
          <p className="mt-6 text-sm text-zinc-200">
            {t("Check-in {in} · Check-out {out}", {
              in: property.checkin_time || "",
              out: property.checkout_time || "",
            })}
          </p>
        </div>
      </section>

      <div className="mx-auto max-w-5xl space-y-14 px-4 py-12">
        <section id="rooms">
          <h2 className="text-2xl font-semibold">{t("Rooms and suites")}</h2>
          <div className="mt-4 grid gap-4 md:grid-cols-2">
            {(site.room_types || []).map((room) => (
              <article key={room.name} className="rounded-xl border border-zinc-200 bg-white p-4">
                <h3 className="font-medium">{room.room_type_name}</h3>
                {room.description && <p className="mt-2 text-sm text-zinc-600">{room.description}</p>}
                {!!room.amenities?.length && (
                  <p className="mt-2 text-xs text-zinc-500">{room.amenities.join(" · ")}</p>
                )}
              </article>
            ))}
            {!site.room_types?.length && <p className="text-sm text-zinc-500">{t("Rooms will appear here once they are published.")}</p>}
          </div>
        </section>

        <section id="facilities">
          <h2 className="text-2xl font-semibold">{t("Facilities")}</h2>
          <div className="mt-4 grid gap-4 md:grid-cols-2">
            {(site.facilities || []).map((group) => (
              <article key={group.area} className="rounded-xl border border-zinc-200 bg-white p-4">
                <h3 className="font-medium">{group.area}</h3>
                <ul className="mt-2 list-disc ps-5 text-sm text-zinc-600">
                  {group.items.map((item) => <li key={item}>{item}</li>)}
                </ul>
              </article>
            ))}
          </div>
        </section>

        <section id="gallery">
          <h2 className="text-2xl font-semibold">{t("Gallery")}</h2>
          <div className="mt-4 grid grid-cols-2 gap-3 md:grid-cols-3">
            {(property.gallery || []).map((shot) => (
              <figure key={shot.url} className="overflow-hidden rounded-xl bg-zinc-200">
                <img src={shot.url} alt={shot.caption || ""} className="h-40 w-full object-cover" />
              </figure>
            ))}
          </div>
        </section>

        <section id="policies">
          <h2 className="text-2xl font-semibold">{t("Policies")}</h2>
          <div className="mt-4 space-y-3 text-sm text-zinc-700">
            {property.house_rules && <p>{property.house_rules}</p>}
            {property.children_policy && <p>{property.children_policy}</p>}
            {property.pets_policy && <p>{property.pets_policy}</p>}
          </div>
        </section>

        <section id="faq">
          <h2 className="text-2xl font-semibold">{t("Questions")}</h2>
          <div className="mt-4 space-y-4">
            {(property.faqs || []).map((faq) => (
              <article key={faq.question}>
                <h3 className="font-medium">{faq.question}</h3>
                <p className="mt-1 text-sm text-zinc-600">{faq.answer}</p>
              </article>
            ))}
          </div>
        </section>

        <p className="text-sm text-zinc-500">
          {property.phone} {property.email}
        </p>
      </div>
    </main>
  )
}

function sectionLabel(id: string) {
  if (id === "rooms") return "Rooms and suites"
  if (id === "facilities") return "Facilities"
  if (id === "gallery") return "Gallery"
  if (id === "policies") return "Policies"
  return "Questions"
}
