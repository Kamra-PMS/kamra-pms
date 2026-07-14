import { useEffect, useMemo, useState } from "react"
import { useLocation, useNavigate, useParams } from "react-router-dom"
import {
  BedDouble,
  Check,
  ExternalLink,
  MapPin,
  Phone,
  Star,
  Users,
} from "lucide-react"
import { call, DEMO_PROPERTY } from "../lib/api"
import { serverError } from "../lib/resource"
import { accentVars } from "../lib/accents"
import { Badge } from "../components/ui/badge"
import { Button } from "../components/ui/button"
import { Sheet } from "../components/ui/sheet"

const inr = (n: number) =>
  n.toLocaleString("en-IN", { maximumFractionDigits: 0 })

interface Showcase {
  property: {
    name: string
    property_name: string
    description: string | null
    logo_url: string | null
    hero_image: string | null
    brand_accent: string | null
    payment_mode: string
    advance_percent: number
    registration_fee: number
    star_category: string | null
    address_line: string | null
    city: string
    state: string
    pincode: string | null
    phone: string | null
    google_reviews_url: string | null
    tripadvisor_url: string | null
    amenities: string[]
    checkin_time: string
    checkout_time: string
    driving_directions: string | null
    latitude: number | null
    longitude: number | null
    gallery: { url: string; caption: string | null }[]
    faqs: { question: string; answer: string }[]
    house_rules: string | null
    pets_policy: string | null
    children_policy: string | null
    extra_bed_policy: string | null
    meta_title: string | null
    meta_description: string | null
    og_image: string | null
    page_slug: string | null
  }
  room_types: {
    name: string
    room_type_name: string
    description: string | null
    base_price: number
    adults_capacity: number
    bed_type: string | null
    room_view: string | null
    amenities: string[]
    media: { media_type: string; url: string; caption: string | null }[]
  }[]
  meal_plans: { name: string; code: string; label: string; price_per_adult: number }[]
  experiences: {
    name: string
    experience_name: string
    category: string | null
    price: number
    duration: string | null
    description: string | null
    image_url: string | null
    gst_rate: number
  }[]
}

interface StayResult {
  room_type: string
  rooms_left: number
  quote: { nights: number; amount_after_tax: number; discount: number } | null
}

const inputCls =
  "w-full rounded-lg border border-zinc-300 bg-white px-3.5 py-2.5 text-base " +
  "focus:outline-2 focus:outline-offset-1 focus:outline-brand-600"

function todayPlus(days: number) {
  const d = new Date()
  d.setDate(d.getDate() + days)
  return d.toISOString().slice(0, 10)
}

function nightsBetween(a: string, b: string) {
  const ms = new Date(b).getTime() - new Date(a).getTime()
  return Math.max(1, Math.round(ms / 86_400_000))
}

function setMetaTag(name: string, content: string) {
  let el = document.querySelector<HTMLMetaElement>(`meta[name="${name}"]`)
  if (!el) {
    el = document.createElement("meta")
    el.name = name
    document.head.appendChild(el)
  }
  el.content = content
}

export default function PublicBooking() {
  const params = useParams()
  const navigate = useNavigate()
  const location = useLocation()
  const [data, setData] = useState<Showcase | null>(null)
  const [search, setSearch] = useState(() => ({
    check_in_date: params.checkin ?? todayPlus(1),
    nights:
      params.checkin && params.checkout
        ? nightsBetween(params.checkin, params.checkout)
        : 2,
    adults: Number(params.adults ?? 2) || 2,
    children: Number(params.children ?? 0) || 0,
  }))
  const [results, setResults] = useState<Record<string, StayResult>>({})
  const [booking, setBooking] = useState<string | null>(null) // room type name
  const [form, setForm] = useState({ guest_name: "", phone: "", email: "", meal_plan: "", special_requests: "" })
  // experience add-ons the guest picked: docname -> quantity
  const [addons, setAddons] = useState<Record<string, number>>({})
  const [voucher, setVoucher] = useState("")
  const [voucherMsg, setVoucherMsg] = useState<{ ok: boolean; text: string } | null>(null)
  const [done, setDone] = useState<{ reservation: string; amount: number } | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const checkOut = useMemo(() => {
    const d = new Date(search.check_in_date)
    d.setDate(d.getDate() + Math.max(1, search.nights))
    return d.toISOString().slice(0, 10)
  }, [search])

  useEffect(() => {
    call<Showcase>("kamra.public_api.showcase", {
      property: DEMO_PROPERTY,
    }).then((d) => {
      setData(d)
      setForm((f) => ({ ...f, meal_plan: d.meal_plans[0]?.name ?? "" }))
    })
  }, [])

  // stay state lives in the URL - shareable, crawlable, UTM params kept
  useEffect(() => {
    navigate(
      `/book/${search.check_in_date}/${checkOut}/${search.adults}/${search.children}${location.search}`,
      { replace: true },
    )
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [search, checkOut])

  // SEO: title, description, canonical, and schema.org Hotel JSON-LD
  useEffect(() => {
    if (!data) return
    const p = data.property
    const minPrice = Math.min(...data.room_types.map((r) => r.base_price))
    document.title = p.meta_title || `${p.property_name}, ${p.city} - book direct from ₹${inr(minPrice)}/night`
    setMetaTag(
      "description",
      p.meta_description ||
        (`${p.property_name} in ${p.city}: ${data.room_types.length} room types from ₹${inr(minPrice)}/night. ` +
          `Best-rate direct booking, pay at hotel. ${p.description ?? ""}`).slice(0, 158),
    )
    if (p.og_image) {
      setMetaTag("og:image", p.og_image)
    }
    let canonical = document.querySelector<HTMLLinkElement>('link[rel="canonical"]')
    if (!canonical) {
      canonical = document.createElement("link")
      canonical.rel = "canonical"
      document.head.appendChild(canonical)
    }
    canonical.href = `${window.location.origin}/book`

    const jsonld = {
      "@context": "https://schema.org",
      "@type": "Hotel",
      name: p.property_name,
      description: p.description ?? undefined,
      image: p.hero_image ?? undefined,
      logo: p.logo_url ?? undefined,
      telephone: p.phone ?? undefined,
      address: {
        "@type": "PostalAddress",
        addressLocality: p.city,
        addressRegion: p.state,
        addressCountry: "IN",
      },
      checkinTime: p.checkin_time?.slice(0, 5),
      checkoutTime: p.checkout_time?.slice(0, 5),
      amenityFeature: p.amenities.map((a) => ({
        "@type": "LocationFeatureSpecification",
        name: a,
      })),
      makesOffer: data.room_types.map((rt) => ({
        "@type": "Offer",
        name: rt.room_type_name,
        priceCurrency: "INR",
        price: rt.base_price,
        itemOffered: {
          "@type": "HotelRoom",
          name: rt.room_type_name,
          occupancy: {
            "@type": "QuantitativeValue",
            maxValue: rt.adults_capacity,
          },
        },
      })),
    }
    let script = document.getElementById("kamra-jsonld") as HTMLScriptElement | null
    if (!script) {
      script = document.createElement("script")
      script.id = "kamra-jsonld"
      script.type = "application/ld+json"
      document.head.appendChild(script)
    }
    script.textContent = JSON.stringify(jsonld)
  }, [data])

  useEffect(() => {
    const t = setTimeout(() => {
      call<StayResult[]>("kamra.public_api.search_stay", {
        property: DEMO_PROPERTY,
        check_in_date: search.check_in_date,
        check_out_date: checkOut,
        adults: search.adults,
        children: search.children,
      }).then((rows) => {
        const map: Record<string, StayResult> = {}
        rows.forEach((r) => (map[r.room_type] = r))
        setResults(map)
      })
    }, 300)
    return () => clearTimeout(t)
  }, [search, checkOut])

  async function submitBooking() {
    if (!booking) return
    setBusy(true)
    setError(null)
    try {
      const res = await call<{ reservation: string; amount_after_tax: number }>(
        "kamra.public_api.book",
        {
          property: DEMO_PROPERTY,
          room_type: booking,
          check_in_date: search.check_in_date,
          check_out_date: checkOut,
          adults: search.adults,
          children: search.children,
          ...form,
          voucher_code: voucherMsg?.ok ? voucher.trim() : "",
          addons: Object.entries(addons)
            .filter(([, qty]) => qty > 0)
            .map(([experience, qty]) => ({ experience, qty })),
        },
      )
      setDone({ reservation: res.reservation, amount: res.amount_after_tax })
    } catch (e) {
      setError(serverError(e))
    } finally {
      setBusy(false)
    }
  }

  if (!data)
    return <p className="py-20 text-center text-zinc-400">Loading…</p>

  const p = data.property

  return (
    <div
      className="min-h-screen bg-zinc-50"
      style={accentVars(data?.property.brand_accent)}
    >
      {/* hero */}
      <div className="relative h-72 overflow-hidden sm:h-80">
        {p.hero_image && (
          <img
            src={p.hero_image}
            alt=""
            className="absolute inset-0 size-full object-cover"
          />
        )}
        <div className="absolute inset-0 bg-gradient-to-t from-black/80 via-black/30 to-transparent" />
        <div className="absolute inset-x-0 bottom-0 mx-auto flex max-w-5xl items-end gap-4 px-5 pb-6 text-white">
          {/* hotel logo slot - falls back to a monogram until one is set */}
          <div className="flex size-16 shrink-0 items-center justify-center overflow-hidden rounded-xl border border-white/30 bg-white shadow-lg sm:size-20">
            {p.logo_url ? (
              <img
                src={p.logo_url}
                alt={`${p.property_name} logo`}
                className="size-full object-contain p-1"
              />
            ) : (
              <span className="text-2xl font-bold text-brand-700 sm:text-3xl">
                {p.property_name
                  .split(" ")
                  .map((w) => w[0])
                  .slice(0, 2)
                  .join("")}
              </span>
            )}
          </div>
          <div className="min-w-0">
          <div className="mb-1 flex items-center gap-2 text-sm">
            {p.star_category && (
              <span className="inline-flex items-center gap-1 rounded-md bg-white/15 px-2 py-0.5 backdrop-blur">
                <Star className="size-3.5 fill-amber-300 text-amber-300" aria-hidden />
                {p.star_category}
              </span>
            )}
            <span className="inline-flex items-center gap-1 text-white/80">
              <MapPin className="size-3.5" aria-hidden />
              {p.city}, {p.state}
            </span>
          </div>
          <h1 className="text-3xl font-semibold tracking-tight">
            {p.property_name}
          </h1>
          <div className="mt-2 flex flex-wrap items-center gap-3 text-sm">
            {p.google_reviews_url && (
              <a
                href={p.google_reviews_url}
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center gap-1 text-white/90 underline-offset-2 hover:underline"
              >
                Google Reviews <ExternalLink className="size-3.5" aria-hidden />
              </a>
            )}
            {p.tripadvisor_url && (
              <a
                href={p.tripadvisor_url}
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center gap-1 text-white/90 underline-offset-2 hover:underline"
              >
                TripAdvisor <ExternalLink className="size-3.5" aria-hidden />
              </a>
            )}
            {p.phone && (
              <span className="inline-flex items-center gap-1 text-white/80">
                <Phone className="size-3.5" aria-hidden />
                {p.phone}
              </span>
            )}
          </div>
          </div>
        </div>
      </div>

      <div className="mx-auto max-w-5xl px-5 pb-16">
        {/* search bar */}
        <div className="relative z-10 -mt-6 mb-8 grid gap-3 rounded-xl border border-zinc-200 bg-white p-4 shadow-lg sm:grid-cols-4">
          <label className="block">
            <span className="mb-1 block text-xs font-medium text-zinc-500">Check-in</span>
            <input
              type="date"
              className={inputCls}
              value={search.check_in_date}
              min={todayPlus(0)}
              onChange={(e) =>
                setSearch({ ...search, check_in_date: e.target.value })
              }
            />
          </label>
          <label className="block">
            <span className="mb-1 block text-xs font-medium text-zinc-500">Nights</span>
            <input
              type="number"
              min={1}
              className={inputCls}
              value={search.nights}
              onChange={(e) =>
                setSearch({ ...search, nights: Math.max(1, Number(e.target.value)) })
              }
            />
          </label>
          <label className="block">
            <span className="mb-1 block text-xs font-medium text-zinc-500">Adults</span>
            <input
              type="number"
              min={1}
              className={inputCls}
              value={search.adults}
              onChange={(e) =>
                setSearch({ ...search, adults: Math.max(1, Number(e.target.value)) })
              }
            />
          </label>
          <label className="block">
            <span className="mb-1 block text-xs font-medium text-zinc-500">Children</span>
            <input
              type="number"
              min={0}
              className={inputCls}
              value={search.children}
              onChange={(e) =>
                setSearch({ ...search, children: Math.max(0, Number(e.target.value)) })
              }
            />
          </label>
        </div>

        {p.description && (
          <p className="mb-3 max-w-3xl text-[15px] leading-relaxed text-zinc-600">
            {p.description}
          </p>
        )}
        <div className="mb-8 flex flex-wrap gap-2">
          {p.amenities.map((a) => (
            <Badge key={a} tone="zinc">{a}</Badge>
          ))}
          <Badge tone="brand">
            Check-in {p.checkin_time.slice(0, 5)} · Check-out {p.checkout_time.slice(0, 5)}
          </Badge>
        </div>

        {p.gallery && p.gallery.length > 0 && (
          <div className="mb-8">
            <h2 className="mb-3 text-lg font-semibold text-zinc-800">Photo Gallery</h2>
            <div className="flex gap-3 overflow-x-auto pb-3 scrollbar-thin">
              {p.gallery.map((img: any, i: number) => (
                <div key={i} className="relative h-40 w-64 shrink-0 rounded-xl overflow-hidden shadow-sm border border-zinc-200 bg-zinc-100">
                  <img src={img.url} alt={img.caption || ""} className="size-full object-cover" />
                  {img.caption && (
                    <div className="absolute inset-x-0 bottom-0 bg-black/60 px-3 py-1 text-center text-xs text-white truncate">
                      {img.caption}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* room cards */}
        <div className="space-y-5">
          {data.room_types.map((rt) => {
            const r = results[rt.name]
            const soldOut = r && r.rooms_left === 0
            return (
              <div
                key={rt.name}
                className="grid overflow-hidden rounded-xl border border-zinc-200 bg-white shadow-sm sm:grid-cols-5"
              >
                <div className="relative sm:col-span-2">
                  {rt.media[0] ? (
                    <img
                      src={rt.media[0].url}
                      alt={rt.media[0].caption ?? rt.room_type_name}
                      className="h-52 w-full object-cover sm:h-full"
                      loading="lazy"
                    />
                  ) : (
                    <div className="flex h-52 items-center justify-center bg-zinc-100 sm:h-full">
                      <BedDouble className="size-10 text-zinc-300" aria-hidden />
                    </div>
                  )}
                  {rt.media.length > 1 && (
                    <span className="absolute bottom-2 right-2 rounded-md bg-black/70 px-2 py-0.5 text-xs text-white">
                      {rt.media.length} photos
                    </span>
                  )}
                </div>
                <div className="flex flex-col justify-between p-5 sm:col-span-3">
                  <div>
                    <div className="flex flex-wrap items-center gap-2">
                      <h2 className="text-lg font-semibold">{rt.room_type_name}</h2>
                      {rt.bed_type && <Badge tone="zinc">{rt.bed_type} bed</Badge>}
                      {rt.room_view && <Badge tone="sky">{rt.room_view}</Badge>}
                      <span className="inline-flex items-center gap-1 text-xs text-zinc-500">
                        <Users className="size-3.5" aria-hidden />
                        up to {rt.adults_capacity} adults
                      </span>
                    </div>
                    {rt.description && (
                      <p className="mt-1 text-sm text-zinc-500">{rt.description}</p>
                    )}
                    <ul className="mt-2 flex flex-wrap gap-x-4 gap-y-1">
                      {rt.amenities.map((a) => (
                        <li key={a} className="inline-flex items-center gap-1 text-xs text-zinc-500">
                          <Check className="size-3 text-brand-600" aria-hidden />
                          {a}
                        </li>
                      ))}
                    </ul>
                  </div>
                  <div className="mt-4 flex flex-wrap items-end justify-between gap-3">
                    <div>
                      {r?.quote ? (
                        <>
                          <p className="text-2xl font-semibold">
                            ₹{inr(r.quote.amount_after_tax)}
                            <span className="ml-1 text-sm font-normal text-zinc-500">
                              total · {r.quote.nights} night{r.quote.nights === 1 ? "" : "s"}, taxes in
                            </span>
                          </p>
                          {r.rooms_left <= 2 && (
                            <p className="text-xs font-medium text-rose-600">
                              Only {r.rooms_left} left for these dates
                            </p>
                          )}
                        </>
                      ) : soldOut ? (
                        <p className="text-sm font-medium text-rose-600">
                          Sold out for these dates
                        </p>
                      ) : (
                        <p className="text-sm text-zinc-400">
                          from ₹{inr(rt.base_price)}/night
                        </p>
                      )}
                    </div>
                    <Button
                      className="px-5 py-2.5 text-base"
                      disabled={!r?.quote}
                      onClick={() => setBooking(rt.name)}
                    >
                      Book now
                    </Button>
                  </div>
                </div>
              </div>
            )
          })}
        </div>

        <div className="mt-12 grid gap-8 md:grid-cols-2 border-t border-zinc-200 pt-8">
          {/* Policies & Rules */}
          <div className="space-y-4">
            <h2 className="text-xl font-bold text-zinc-800">Hotel Policies & Rules</h2>
            <div className="rounded-xl border border-zinc-200 bg-white p-5 space-y-4 shadow-sm text-sm">
              <div className="flex justify-between border-b border-zinc-100 pb-2">
                <span className="font-medium text-zinc-500">Check-in</span>
                <span className="font-semibold text-zinc-800">{p.checkin_time?.slice(0, 5)} onwards</span>
              </div>
              <div className="flex justify-between border-b border-zinc-100 pb-2">
                <span className="font-medium text-zinc-500">Check-out</span>
                <span className="font-semibold text-zinc-800">Before {p.checkout_time?.slice(0, 5)}</span>
              </div>
              {p.house_rules && (
                <div>
                  <span className="block font-semibold text-zinc-700 mb-1">House Rules</span>
                  <p className="text-zinc-600 text-xs leading-relaxed whitespace-pre-line">{p.house_rules}</p>
                </div>
              )}
              {p.pets_policy && (
                <div>
                  <span className="block font-semibold text-zinc-700 mb-1">Pets Policy</span>
                  <p className="text-zinc-600 text-xs leading-relaxed whitespace-pre-line">{p.pets_policy}</p>
                </div>
              )}
              {p.children_policy && (
                <div>
                  <span className="block font-semibold text-zinc-700 mb-1">Children & Extra Beds</span>
                  <p className="text-zinc-600 text-xs leading-relaxed whitespace-pre-line">{p.children_policy}</p>
                </div>
              )}
              {p.extra_bed_policy && (
                <div>
                  <span className="block font-semibold text-zinc-700 mb-1">Extra Bed Policy</span>
                  <p className="text-zinc-600 text-xs leading-relaxed whitespace-pre-line">{p.extra_bed_policy}</p>
                </div>
              )}
            </div>
          </div>

          {/* Map & Directions */}
          <div className="space-y-4">
            <h2 className="text-xl font-bold text-zinc-800">Location & Directions</h2>
            <div className="rounded-xl border border-zinc-200 bg-white p-5 shadow-sm space-y-3">
              {p.latitude && p.longitude ? (
                <iframe
                  title="Hotel Location Map"
                  width="100%"
                  height="220"
                  src={`https://maps.google.com/maps?q=${p.latitude},${p.longitude}&t=&z=15&ie=UTF8&iwloc=&output=embed`}
                  className="rounded-lg border border-zinc-200 shadow-inner"
                />
              ) : (
                <div className="flex h-40 items-center justify-center bg-zinc-50 rounded-lg border border-zinc-200">
                  <span className="text-sm text-zinc-400">Map location not set</span>
                </div>
              )}
              <p className="text-sm font-medium text-zinc-800 flex items-start gap-2">
                <MapPin className="size-4 shrink-0 text-brand-600 mt-0.5" />
                {p.address_line ? `${p.address_line}, ` : ""}{p.city}, {p.state} {p.pincode ? `- ${p.pincode}` : ""}
              </p>
              {p.driving_directions && (
                <div className="text-xs text-zinc-600 border-t border-zinc-100 pt-3">
                  <span className="block font-semibold text-zinc-700 mb-1">Driving Directions</span>
                  <p className="leading-relaxed whitespace-pre-line">{p.driving_directions}</p>
                </div>
              )}
            </div>
          </div>
        </div>

        {p.faqs && p.faqs.length > 0 && (
          <div className="mt-12 border-t border-zinc-200 pt-8 max-w-3xl mx-auto space-y-4">
            <h2 className="text-xl font-bold text-zinc-800 text-center mb-6">Frequently Asked Questions</h2>
            <div className="space-y-3">
              {p.faqs.map((faq: any, i: number) => (
                <details key={i} className="group rounded-xl border border-zinc-200 bg-white p-4 shadow-sm [&_summary::-webkit-details-marker]:hidden cursor-pointer">
                  <summary className="flex items-center justify-between text-sm font-medium text-zinc-800 select-none">
                    <span>{faq.question}</span>
                    <span className="transition group-open:rotate-180">
                      <svg fill="none" height="24" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" viewBox="0 0 24 24" width="24" className="size-4 text-zinc-500"><polyline points="6 9 12 15 18 9"></polyline></svg>
                    </span>
                  </summary>
                  <p className="mt-3 text-xs leading-relaxed text-zinc-600 border-t border-zinc-100 pt-3">
                    {faq.answer}
                  </p>
                </details>
              ))}
            </div>
          </div>
        )}

        <p className="mt-10 text-center text-xs text-zinc-400">
          Powered by Kamra - the open-source, agent-ready hotel PMS
        </p>
      </div>

      {booking && (
        <Sheet
          title={done ? "Booking confirmed" : "Complete your booking"}
          description={
            done
              ? undefined
              : `${data.room_types.find((r) => r.name === booking)?.room_type_name} · ${search.check_in_date} → ${checkOut}`
          }
          onClose={() => {
            setBooking(null)
            setDone(null)
          }}
          footer={
            done ? (
              <Button className="w-full justify-center py-2.5" onClick={() => { setBooking(null); setDone(null) }}>
                Done
              </Button>
            ) : (
              <Button
                className="w-full justify-center py-2.5 text-base"
                disabled={busy || !form.guest_name || !form.phone}
                onClick={submitBooking}
              >
                {busy ? "Booking…" : "Confirm - pay at hotel"}
              </Button>
            )
          }
        >
          {done ? (
            <div className="space-y-3">
              <div className="rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-4 text-emerald-800">
                <p className="text-lg font-semibold">{done.reservation}</p>
                <p className="mt-1 text-sm">
                  Total ₹{inr(done.amount)} - payable at the hotel. We've saved
                  your number; the front desk will reach out before arrival.
                </p>
              </div>
            </div>
          ) : (
            <div className="space-y-4">
              <label className="block">
                <span className="mb-1.5 block text-sm font-medium text-zinc-600">Full name</span>
                <input className={inputCls} value={form.guest_name} autoFocus
                  onChange={(e) => setForm({ ...form, guest_name: e.target.value })} />
              </label>
              <label className="block">
                <span className="mb-1.5 block text-sm font-medium text-zinc-600">Phone</span>
                <input className={inputCls} value={form.phone} placeholder="+91 …"
                  onChange={(e) => setForm({ ...form, phone: e.target.value })} />
              </label>
              <label className="block">
                <span className="mb-1.5 block text-sm font-medium text-zinc-600">Email (optional)</span>
                <input className={inputCls} type="email" value={form.email}
                  onChange={(e) => setForm({ ...form, email: e.target.value })} />
              </label>
              <label className="block">
                <span className="mb-1.5 block text-sm font-medium text-zinc-600">Meal plan</span>
                <select className={inputCls} value={form.meal_plan}
                  onChange={(e) => setForm({ ...form, meal_plan: e.target.value })}>
                  <option value="">Room only</option>
                  {data.meal_plans.map((mp) => (
                    <option key={mp.name} value={mp.name}>
                      {mp.label} (+₹{inr(mp.price_per_adult)}/adult/night)
                    </option>
                  ))}
                </select>
              </label>
              {data.experiences.length > 0 && (
                <div className="block">
                  <span className="mb-1.5 block text-sm font-medium text-zinc-600">
                    Add experiences
                  </span>
                  <div className="space-y-2">
                    {data.experiences.map((exp) => {
                      const qty = addons[exp.name] || 0
                      const on = qty > 0
                      return (
                        <div
                          key={exp.name}
                          className={
                            "flex items-center gap-3 rounded-xl border p-2.5 " +
                            (on ? "border-brand-400 bg-brand-50/50" : "border-zinc-200")
                          }
                        >
                          {exp.image_url && (
                            <img
                              src={exp.image_url}
                              alt=""
                              className="size-12 shrink-0 rounded-lg object-cover"
                            />
                          )}
                          <div className="min-w-0 flex-1">
                            <div className="flex items-center gap-1.5">
                              <span className="truncate text-sm font-medium text-zinc-800">
                                {exp.experience_name}
                              </span>
                              {exp.category && (
                                <span className="shrink-0 rounded-full bg-zinc-100 px-1.5 py-0.5 text-[10px] text-zinc-500">
                                  {exp.category}
                                </span>
                              )}
                            </div>
                            <div className="truncate text-xs text-zinc-500">
                              ₹{inr(exp.price)}
                              {exp.duration ? ` · ${exp.duration}` : ""}
                              {exp.description ? ` · ${exp.description}` : ""}
                            </div>
                          </div>
                          {on ? (
                            <div className="flex shrink-0 items-center gap-1.5">
                              <button
                                type="button"
                                className="size-7 rounded-lg border border-zinc-300 text-zinc-600 hover:bg-white"
                                onClick={() =>
                                  setAddons((a) => ({ ...a, [exp.name]: qty - 1 }))
                                }
                              >
                                −
                              </button>
                              <span className="w-5 text-center text-sm tabular-nums">
                                {qty}
                              </span>
                              <button
                                type="button"
                                className="size-7 rounded-lg border border-zinc-300 text-zinc-600 hover:bg-white"
                                onClick={() =>
                                  setAddons((a) => ({ ...a, [exp.name]: qty + 1 }))
                                }
                              >
                                +
                              </button>
                            </div>
                          ) : (
                            <button
                              type="button"
                              className="shrink-0 rounded-lg border border-brand-500 px-3 py-1.5 text-xs font-medium text-brand-700 hover:bg-brand-50"
                              onClick={() =>
                                setAddons((a) => ({ ...a, [exp.name]: 1 }))
                              }
                            >
                              Add
                            </button>
                          )}
                        </div>
                      )
                    })}
                  </div>
                  {(() => {
                    const addonTotal = data.experiences.reduce(
                      (s, e) => s + (addons[e.name] || 0) * e.price,
                      0,
                    )
                    return addonTotal > 0 ? (
                      <p className="mt-2 text-right text-xs text-zinc-500">
                        Experiences: +₹{inr(addonTotal)} · added to your bill at
                        the hotel
                      </p>
                    ) : null
                  })()}
                </div>
              )}
              <label className="block">
                <span className="mb-1.5 block text-sm font-medium text-zinc-600">Special requests</span>
                <textarea className={inputCls} rows={2} value={form.special_requests}
                  onChange={(e) => setForm({ ...form, special_requests: e.target.value })} />
              </label>
              <div className="block">
                <span className="mb-1.5 block text-sm font-medium text-zinc-600">
                  Promo code
                </span>
                <div className="flex gap-2">
                  <input className={inputCls} placeholder="Have a code?"
                    value={voucher}
                    onChange={(e) => {
                      setVoucher(e.target.value)
                      setVoucherMsg(null)
                    }} />
                  <button type="button"
                    className="shrink-0 rounded-lg border border-brand-500 px-4 text-sm font-medium text-brand-700 hover:bg-brand-50 disabled:opacity-50"
                    disabled={!voucher.trim()}
                    onClick={async () => {
                      const nights = Math.max(
                        1,
                        Math.round(
                          (new Date(checkOut).getTime() -
                            new Date(search.check_in_date).getTime()) /
                            86_400_000,
                        ),
                      )
                      try {
                        const r = await call<{ ok: boolean; message: string }>(
                          "kamra.public_api.check_voucher",
                          { property: DEMO_PROPERTY, code: voucher.trim(), nights },
                        )
                        setVoucherMsg({ ok: r.ok, text: r.message })
                      } catch {
                        setVoucherMsg({ ok: false, text: "Couldn't check that code." })
                      }
                    }}>
                    Apply
                  </button>
                </div>
                {voucherMsg && (
                  <p className={
                    "mt-1 text-xs " +
                    (voucherMsg.ok ? "text-brand-700" : "text-rose-600")
                  }>
                    {voucherMsg.text}
                  </p>
                )}
              </div>
              {data.property.payment_mode &&
                data.property.payment_mode !== "Pay at hotel" && (
                  <div className="rounded-xl border border-zinc-200 bg-zinc-50 px-3 py-2.5 text-sm text-zinc-600">
                    {data.property.payment_mode === "Full online"
                      ? "Full amount is paid online to confirm this booking."
                      : data.property.payment_mode === "Advance percent"
                        ? `A ${data.property.advance_percent}% advance is collected to confirm; the rest is paid at the hotel.`
                        : `A ₹${inr(data.property.registration_fee)} registration fee is collected to confirm; the rest is paid at the hotel.`}
                  </div>
                )}
              {error && (
                <div className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
                  {error}
                </div>
              )}
            </div>
          )}
        </Sheet>
      )}
    </div>
  )
}
