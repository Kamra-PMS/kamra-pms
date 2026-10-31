import { useEffect, useRef, useState } from "react"
import { clampGuests, maxCapacity } from "../lib/occupancy"
import PrivacyNotice, { setPrivacyTerms } from "../components/PrivacyNotice"
import { Link, useLocation, useNavigate, useParams } from "react-router-dom"
import {
  ArrowRight,
  BedDouble,
  CalendarDays,
  Check,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  Clock,
  ExternalLink,
  Eye,
  Images,
  MapPin,
  Phone,
  Search,
  ShieldCheck,
  Star,
  Users,
  Wallet,
  X,
  Zap,
} from "lucide-react"
import { callGuest, getDefaultProperty } from "../lib/api"
import { serverError } from "../lib/resource"
import { accentVars } from "../lib/accents"
import { Badge } from "../components/ui/badge"
import { Button } from "../components/ui/button"
import { Sheet } from "../components/ui/sheet"
import { cur, locale, moneyLocale, adoptUiLocale } from "../lib/money"
import { formatPhoneDisplay, formatPhoneTel } from "../lib/phone"
import { petChargeBasis } from "../lib/pets"
import { useT, t as translate } from "../lib/i18n"
import { adoptGuestLanguage } from "../lib/dir"
import { LanguageSwitcher } from "../components/LanguageSwitcher"
import { addDays, nightsBetween, parseDate, stayFromParams, todayPlus } from "../lib/stay"
import ChildAges, {
  agesToSend, canReserve, sizeAges, StayNotice,
  type ChildAge, type StayFit,
} from "../components/ChildAges"


const inr = (n: number) =>
  n.toLocaleString(moneyLocale(), { maximumFractionDigits: 0 })
const money = (n: number) => `${cur()}${inr(n)}`

interface Photo { url: string; caption: string | null }

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
    cleaning_fee: number
    pets_allowed?: number
    pet_charge?: number
    pet_charge_basis?: string
    security_deposit_amount: number
    minimum_nights: number
    free_cancel_days: number
    cancellation_fee: string
    has_cancellation_tiers?: boolean
    booking_mode: string
    property_kind: string
    star_category: string | null
    address_line: string | null
    city: string
    state: string
    pincode: string | null
    country?: string | null
    phone: string | null
    google_reviews_url: string | null
    tripadvisor_url: string | null
    amenities: string[]
    checkin_time: string
    checkout_time: string
    privacy_contact?: string | null
    guest_retention_months?: number | null
    driving_directions: string | null
    latitude: number | null
    longitude: number | null
    gallery: Photo[]
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
    listing_slug: string | null
    description: string | null
    base_price: number
    adults_capacity: number
    children_capacity: number
    bed_type: string | null
    room_view: string | null
    amenities: string[]
    media: { media_type: string; url: string; caption: string | null }[]
    location_name: string | null
    location_address: string | null
    google_maps_url: string | null
    latitude: number | null
    longitude: number | null
  }[]
  // One pin per distinct site - a single-property hotel gets one entry
  // (the property's own address); a multi-villa portfolio gets
  // one per villa, each listing which room types live there.
  locations: {
    name: string
    slug: string | null
    address: string | null
    google_maps_url: string | null
    latitude: number | null
    longitude: number | null
    room_types: string[]
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

/** One way to buy the stay: room only, or with a meal plan. Totals are the
 *  server's quote - the page never prices anything itself. */
interface Plan {
  meal_plan: string
  amount_after_tax: number
  /** Before the promo code, only when one is applied. */
  list_amount?: number
  advance_due?: number
  balance_at_hotel?: number
}

interface StayResult extends StayFit {
  room_type: string
  rooms_left: number
  quote: {
    nights: number
    amount_after_tax: number
    discount: number
    cleaning_fee?: number
    pet_charge?: number
    totals?: { deposit_required?: number }
    stay_rules?: { non_refundable?: boolean }
    /** Server-computed from the property's payment policy - never derived here. */
    advance_due?: number
    balance_at_hotel?: number
  } | null
  plans?: Plan[]
}

const inputCls =
  "w-full rounded-lg border border-zinc-300 bg-white px-3.5 py-2.5 text-base " +
  "focus:outline-2 focus:outline-offset-1 focus:outline-brand-600"

const initials = (name: string) =>
  name.split(" ").map((w) => w[0]).slice(0, 2).join("")

function setMetaTag(name: string, content: string) {
  let el = document.querySelector<HTMLMetaElement>(`meta[name="${name}"]`)
  if (!el) {
    el = document.createElement("meta")
    el.name = name
    document.head.appendChild(el)
  }
  el.content = content
}

/** Plans for a row; an older server sends only the room-only quote. */
function plansOf(r?: StayResult): Plan[] {
  if (!r?.quote) return []
  if (r.plans?.length) return r.plans
  return [{
    meal_plan: "",
    amount_after_tax: r.quote.amount_after_tax,
    advance_due: r.quote.advance_due,
    balance_at_hotel: r.quote.balance_at_hotel,
  }]
}

const imagesOf = (media: { media_type: string; url: string; caption: string | null }[]) =>
  media.filter((m) => m.url && (!m.media_type || m.media_type === "Image"))

interface PropertyCard {
  name: string
  property_name: string
  property_slug: string
  city: string | null
  state: string | null
  hero_image: string | null
  logo_url: string | null
  property_kind: string | null
  description: string | null
  from_rate: number
}

/** /book on a site with several properties: pick one, then book it. Each
 *  card opens that property's own page with the stay already filled in. */
function PropertyChooser({
  properties,
  stayPath,
  query,
}: {
  properties: PropertyCard[]
  stayPath: string
  query: string
}) {
  const { t } = useT()
  useEffect(() => {
    document.title = t("Places to stay - book direct")
  }, [t])
  const linkFor = (slug: string) => {
    const qs = new URLSearchParams(query)
    qs.set("property", slug)
    return `/book${stayPath}?${qs}`
  }
  return (
    <div className="min-h-screen bg-zinc-50">
      <div className="mx-auto max-w-6xl px-4 py-10 sm:px-6 sm:py-14">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h1 className="text-3xl font-semibold tracking-tight text-zinc-900 sm:text-4xl">
              {t("Places to stay")}
            </h1>
            <p className="mt-2 text-zinc-500">
              {t("Pick a property to see its rooms, prices and availability.")}
            </p>
          </div>
          <LanguageSwitcher />
        </div>
        <div className="mt-8 grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {properties.map((p) => (
            <Link
              key={p.name}
              to={linkFor(p.property_slug)}
              className="group overflow-hidden rounded-2xl border border-zinc-200 bg-white transition hover:border-zinc-300 hover:shadow-lg focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-600"
            >
              <div className="relative aspect-[4/3] overflow-hidden bg-zinc-100">
                {p.hero_image ? (
                  <img
                    src={p.hero_image}
                    alt=""
                    loading="lazy"
                    className="size-full object-cover transition duration-500 group-hover:scale-[1.03]"
                  />
                ) : (
                  <div className="flex size-full items-center justify-center bg-brand-900 text-white">
                    <span className="text-4xl font-semibold tracking-tight">{initials(p.property_name)}</span>
                  </div>
                )}
                {p.property_kind && (
                  <span className="absolute start-3 top-3 rounded-full bg-white/95 px-2.5 py-1 text-xs font-medium text-zinc-700 shadow-sm">
                    {p.property_kind === "Short Term Rental" ? t("Villa / home") : translate(p.property_kind)}
                  </span>
                )}
              </div>
              <div className="p-5">
                <h2 className="text-lg font-semibold text-zinc-900">{p.property_name}</h2>
                {(p.city || p.state) && (
                  <p className="mt-1 inline-flex items-center gap-1.5 text-sm text-zinc-500">
                    <MapPin className="size-3.5 shrink-0" aria-hidden />
                    {[p.city, p.state].filter(Boolean).join(", ")}
                  </p>
                )}
                {p.description && (
                  <p className="mt-2 line-clamp-2 text-sm text-zinc-600">{p.description}</p>
                )}
                <div className="mt-4 flex items-end justify-between gap-2 border-t border-zinc-100 pt-4">
                  <p className="text-sm text-zinc-500">
                    {p.from_rate > 0 ? (
                      <>
                        {t("from")}{" "}
                        <span className="text-lg font-semibold text-zinc-900">{money(p.from_rate)}</span>
                        {" "}/ {t("night")}
                      </>
                    ) : (
                      t("See rooms and prices")
                    )}
                  </p>
                  <span className="inline-flex items-center gap-1 text-sm font-medium text-brand-700">
                    {t("View rooms")}
                    <ChevronRight className="size-4 rtl:rotate-180" aria-hidden />
                  </span>
                </div>
              </div>
            </Link>
          ))}
        </div>
      </div>
    </div>
  )
}

/** Full-screen photo viewer. A native <dialog> gives focus trapping and
 *  Escape for free. */
function Lightbox({ photos, start, title, onClose }: {
  photos: Photo[]
  start: number
  title: string
  onClose: () => void
}) {
  const { t } = useT()
  const ref = useRef<HTMLDialogElement>(null)
  const [i, setI] = useState(start)
  const n = photos.length
  const go = (d: number) => setI((x) => (x + d + n) % n)
  useEffect(() => {
    ref.current?.showModal()
  }, [])
  const photo = photos[i]
  return (
    <dialog
      ref={ref}
      onClose={onClose}
      aria-label={title}
      onKeyDown={(e) => {
        const rtl = document.documentElement.dir === "rtl"
        if (e.key === "ArrowRight") go(rtl ? -1 : 1)
        if (e.key === "ArrowLeft") go(rtl ? 1 : -1)
      }}
      className="m-0 h-dvh max-h-none w-full max-w-none bg-zinc-950 p-0 text-white backdrop:bg-black/90"
    >
      <div className="flex h-full flex-col">
        <div className="flex items-center gap-3 px-4 py-3 sm:px-6">
          <p className="min-w-0 flex-1 truncate text-sm">
            <span className="font-medium">{title}</span>
            <span className="ms-2 tabular-nums text-white/60">{i + 1} / {n}</span>
          </p>
          <button
            type="button"
            onClick={() => ref.current?.close()}
            className="rounded-full p-2 hover:bg-white/10 focus-visible:outline-2 focus-visible:outline-white"
            aria-label={t("Close")}
          >
            <X className="size-5" />
          </button>
        </div>
        <div className="relative flex min-h-0 flex-1 items-center justify-center px-2 sm:px-16">
          <img src={photo.url} alt={photo.caption ? translate(photo.caption) : ""} className="max-h-full max-w-full rounded-lg object-contain" />
          {n > 1 && (
            <>
              <button type="button" onClick={() => go(-1)} aria-label={t("Previous photo")}
                className="absolute start-2 rounded-full bg-white/10 p-2.5 hover:bg-white/20 focus-visible:outline-2 focus-visible:outline-white sm:start-4">
                <ChevronLeft className="size-6 rtl:rotate-180" />
              </button>
              <button type="button" onClick={() => go(1)} aria-label={t("Next photo")}
                className="absolute end-2 rounded-full bg-white/10 p-2.5 hover:bg-white/20 focus-visible:outline-2 focus-visible:outline-white sm:end-4">
                <ChevronRight className="size-6 rtl:rotate-180" />
              </button>
            </>
          )}
        </div>
        <p className="h-8 px-4 pt-2 text-center text-sm text-white/70">{photo.caption ? translate(photo.caption) : ""}</p>
        {n > 1 && (
          <div className="flex justify-center gap-2 overflow-x-auto px-4 pb-4">
            {photos.map((ph, k) => (
              <button key={ph.url + k} type="button" onClick={() => setI(k)}
                aria-label={t("Photo {n}", { n: k + 1 })}
                aria-current={k === i}
                className={"h-14 w-20 shrink-0 overflow-hidden rounded-md ring-2 transition " +
                  (k === i ? "ring-white" : "opacity-50 ring-transparent hover:opacity-100")}>
                <img src={ph.url} alt="" className="size-full object-cover" loading="lazy" />
              </button>
            ))}
          </div>
        )}
      </div>
    </dialog>
  )
}

/** Swipeable room photos (CSS scroll-snap), with arrows on larger screens. */
function PhotoStrip({ photos, name, onOpen }: {
  photos: Photo[]
  name: string
  onOpen: (i: number) => void
}) {
  const { t, tn } = useT()
  const ref = useRef<HTMLDivElement>(null)
  const [i, setI] = useState(0)
  if (!photos.length)
    return (
      <div className="flex aspect-[4/3] items-center justify-center bg-zinc-100">
        <BedDouble className="size-10 text-zinc-300" aria-hidden />
      </div>
    )
  const step = (d: number) => {
    const el = ref.current
    if (!el) return
    const rtl = document.documentElement.dir === "rtl"
    el.scrollBy({ left: d * el.clientWidth * (rtl ? -1 : 1), behavior: "smooth" })
  }
  return (
    <div className="group/strip relative">
      <div
        ref={ref}
        className="flex aspect-[4/3] snap-x snap-mandatory overflow-x-auto [scrollbar-width:none]"
        onScroll={(e) => {
          const el = e.currentTarget
          setI(Math.round(Math.abs(el.scrollLeft) / el.clientWidth))
        }}
      >
        {photos.map((ph, k) => (
          <button key={ph.url + k} type="button" onClick={() => onOpen(k)}
            className="size-full shrink-0 snap-start"
            aria-label={t("Open photo {n} of {name}", { n: k + 1, name })}>
            <img src={ph.url} alt={ph.caption ? translate(ph.caption) : name}
              className="size-full object-cover" loading="lazy" />
          </button>
        ))}
      </div>
      {photos.length > 1 && (
        <>
          <button type="button" onClick={() => step(-1)} aria-label={t("Previous photo")}
            className="absolute start-2 top-1/2 hidden -translate-y-1/2 rounded-full bg-white/90 p-1.5 text-zinc-800 shadow group-hover/strip:block focus-visible:block">
            <ChevronLeft className="size-4 rtl:rotate-180" />
          </button>
          <button type="button" onClick={() => step(1)} aria-label={t("Next photo")}
            className="absolute end-2 top-1/2 hidden -translate-y-1/2 rounded-full bg-white/90 p-1.5 text-zinc-800 shadow group-hover/strip:block focus-visible:block">
            <ChevronRight className="size-4 rtl:rotate-180" />
          </button>
          <div className="pointer-events-none absolute inset-x-0 bottom-2.5 flex justify-center gap-1.5" aria-hidden>
            {photos.map((_, k) => (
              <span key={k} className={"size-1.5 rounded-full " + (k === i ? "bg-white" : "bg-white/50")} />
            ))}
          </div>
        </>
      )}
      <button type="button" onClick={() => onOpen(0)}
        className="absolute end-2.5 top-2.5 inline-flex items-center gap-1.5 rounded-full bg-black/60 px-2.5 py-1 text-xs font-medium text-white backdrop-blur hover:bg-black/75">
        <Images className="size-3.5" aria-hidden />
        {tn(photos.length, "{n} photo", "{n} photos")}
      </button>
    </div>
  )
}

export default function PublicBooking() {
  const { t, tn, lang } = useT()
  useEffect(() => adoptGuestLanguage(), [])
  const params = useParams()
  const navigate = useNavigate()
  const location = useLocation()
  const [property, setProperty] = useState<string | null>(null)
  const [catalogMode, setCatalogMode] = useState<string | null>(null)
  const [sites, setSites] = useState<
    {
      name: string
      slug: string | null
      address: string | null
      from_rate: number
      room_types: string[]
      listing_count?: number
      cover_image?: string | null
      google_maps_url?: string | null
      phone?: string | null
      city?: string | null
      state?: string | null
      latitude?: number | null
      longitude?: number | null
    }[]
  >([])
  const [data, setData] = useState<Showcase | null>(null)
  // several properties live on one site: the guest picks one first
  const [properties, setProperties] = useState<PropertyCard[]>([])
  // A property slug where the check-in date goes (/book/kamra-demo-palace,
  // a hand-typed or older link) means that property, not a date.
  const slugInPath = params.checkin && !parseDate(params.checkin) ? params.checkin : null
  const propertySlug = new URLSearchParams(location.search).get("property") || slugInPath

  // What this property can actually sleep. A property page lists several room
  // types and the guest has not picked one yet, so the roomiest bounds the
  // search. Without it the page quotes a party the booking then refuses -
  // the guest gets a price, fills in their details, and only finds out on
  // submit (Reservation.validate_occupancy is the real guard).
  const maxAdults = maxCapacity(data?.room_types, "adults_capacity")
  const maxChildren = maxCapacity(data?.room_types, "children_capacity")

  // The party also arrives in the URL (/book/in/out/adults/children), so clamp
  // once the capacity is known - otherwise a shared or edited link walks
  // straight past the inputs.
  useEffect(() => {
    if (!maxAdults && !maxChildren) return
    setSearch((q) => {
      const adults = clampGuests(q.adults, 1, maxAdults)
      const children = clampGuests(q.children, 0, maxChildren)
      return adults === q.adults && children === q.children
        ? q
        : { ...q, adults, children }
    })
  }, [maxAdults, maxChildren])
  const [search, setSearch] = useState(() =>
    stayFromParams(slugInPath ? {} : params),
  )
  const [results, setResults] = useState<Record<string, StayResult>>({})
  const [loadingRates, setLoadingRates] = useState(false)
  const [ratesFailed, setRatesFailed] = useState(false)
  const [childAgesState, setChildAges] = useState<ChildAge[]>([])
  const childAges = sizeAges(childAgesState, search.children)
  const agesMissing = search.children > 0 && !agesToSend(childAges)
  const [editing, setEditing] = useState(false)
  const [mealFilter, setMealFilter] = useState<string | null>(null)
  const [availableOnly, setAvailableOnly] = useState(false)
  const [selected, setSelected] = useState<{ room_type: string; meal_plan: string } | null>(null)
  const [lightbox, setLightbox] = useState<{ photos: Photo[]; start: number; title: string } | null>(null)
  const [booking, setBooking] = useState<string | null>(null) // room type name
  const [form, setForm] = useState({ guest_name: "", phone: "", email: "", special_requests: "", marketing_consent: 0 })
  // experience add-ons the guest picked: docname -> quantity
  const [addons, setAddons] = useState<Record<string, number>>({})
  const [voucher, setVoucher] = useState("")
  const [appliedVoucher, setAppliedVoucher] = useState("")
  const [voucherMsg, setVoucherMsg] = useState<{ ok: boolean; text: string } | null>(null)
  const [done, setDone] = useState<{
    reservation: string
    amount: number
    advance_due: number
    balance_at_hotel: number
    status: string
  } | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loadFailed, setLoadFailed] = useState(false)
  const [busy, setBusy] = useState(false)

  const checkOut = search.check_out_date
  const nights = nightsBetween(search.check_in_date, checkOut)

  useEffect(() => {
    setData(null)
    setProperty(null)
    setResults({})
    setError(null)
    setLoadFailed(false)
    callGuest<{
      mode: string
      property?: string
      sites?: typeof sites
      listing_slug?: string
      properties?: PropertyCard[]
      ui_locale?: { currency_symbol?: string; locale?: string }
    }>("kamra.public_api.catalog_index", propertySlug ? { property_slug: propertySlug } : {})
      .then((idx) => {
        setCatalogMode(idx.mode)
        if (idx.mode === "single_listing" && idx.listing_slug) {
          navigate(`/stay/${idx.listing_slug}`, { replace: true })
          return null
        }
        if (idx.mode === "properties") {
          // nothing to show until the guest picks a property
          adoptUiLocale(idx.ui_locale)
          setProperties(idx.properties ?? [])
          return null
        }
        if (idx.mode === "sites" && idx.sites) {
          setSites(idx.sites)
        }
        const p = idx.property
        if (!p) return getDefaultProperty().then((name) => ({ p: name, idx }))
        return { p, idx }
      })
      .then((ctx) => {
        if (!ctx) return
        const p = typeof ctx === "object" && "p" in ctx ? ctx.p : ctx
        setProperty(p)
        return callGuest<Showcase>("kamra.public_api.showcase", { property: p })
      })
      .then((d) => {
        if (!d) return
        adoptUiLocale((d as unknown as { ui_locale?: { currency_symbol?: string; locale?: string } }).ui_locale)
        setPrivacyTerms((d as unknown as { ui_locale?: { privacy_authority?: string } }).ui_locale)
        setData(d)
      })
      .catch(() => setLoadFailed(true))
  }, [navigate, propertySlug])

  // stay state lives in the URL - shareable, crawlable, UTM params kept
  useEffect(() => {
    const qs = new URLSearchParams(location.search)
    if (propertySlug) qs.set("property", propertySlug)
    const query = qs.toString()
    navigate(
      `/book/${search.check_in_date}/${checkOut}/${search.adults}/${search.children}${query ? `?${query}` : ""}`,
      { replace: true },
    )
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [search, checkOut])

  // SEO: title, description, canonical, and schema.org Hotel JSON-LD
  useEffect(() => {
    if (!data) return
    const p = data.property
    const minPrice = Math.min(...data.room_types.map((r) => r.base_price))
    document.title = p.meta_title || t("{property} in {city} · book direct from {price} per night", {
      property: p.property_name, city: p.city, price: money(minPrice),
    })
    setMetaTag(
      "description",
      p.meta_description ||
        t("{property} in {city}: {count} room types from {price} per night. Best-rate direct booking, pay at hotel. {description}", {
          property: p.property_name, city: p.city, count: data.room_types.length,
          price: money(minPrice), description: p.description ?? "",
        }).slice(0, 158),
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
    canonical.href = `${window.location.origin}/book${propertySlug ? `?property=${encodeURIComponent(propertySlug)}` : ""}`

    const isStr = p.property_kind === "Short Term Rental"
    const schemaType = isStr ? "VacationRental" : "Hotel"
    const offerType = isStr ? "Accommodation" : "HotelRoom"
    const jsonld = {
      "@context": "https://schema.org",
      "@type": schemaType,
      name: p.property_name,
      description: p.description ?? undefined,
      image: p.hero_image ?? undefined,
      logo: p.logo_url ?? undefined,
      telephone: p.phone
        ? formatPhoneTel(p.phone, p.country)
        : undefined,
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
        priceCurrency: locale().currency || undefined,
        price: rt.base_price,
        itemOffered: {
          "@type": offerType,
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
  }, [data, t])

  useEffect(() => {
    if (!property || catalogMode === "sites") return
    setLoadingRates(true)
    const t = setTimeout(fetchResults, 300)
    return () => clearTimeout(t)
  }, [property, search, checkOut, catalogMode, childAgesState, appliedVoucher])

  function fetchResults() {
    if (!property) return
    setLoadingRates(true)
    setRatesFailed(false)
    callGuest<StayResult[]>("kamra.public_api.search_stay", {
      property,
      check_in_date: search.check_in_date,
      check_out_date: checkOut,
      adults: search.adults,
      children: search.children,
      child_ages: agesToSend(childAges),
      pets: search.pets,
      voucher_code: appliedVoucher || undefined,
    }).then((rows) => {
      const map: Record<string, StayResult> = {}
      rows.forEach((r) => (map[r.room_type] = r))
      setResults(map)
      // a selection the new search can no longer sell is dropped
      setSelected((s) => {
        if (!s) return s
        const r = map[s.room_type]
        return canReserve(r) && plansOf(r).some((p) => p.meal_plan === s.meal_plan) ? s : null
      })
    }).catch(() => {
      setResults({})
      setRatesFailed(true)
    }).finally(() => setLoadingRates(false))
  }

  async function applyVoucher() {
    if (!property || !voucher.trim()) return
    try {
      const r = await callGuest<{ ok: boolean; message: string }>("kamra.public_api.check_voucher",
        { property, code: voucher.trim(), nights },
      )
      setVoucherMsg({ ok: r.ok, text: r.message })
      setAppliedVoucher(r.ok ? voucher.trim() : "")
    } catch (e) {
      setVoucherMsg({ ok: false, text: serverError(e) })
      setAppliedVoucher("")
    }
  }

  async function submitBooking() {
    if (!booking || !property || !selected) return
    setBusy(true)
    setError(null)
    try {
      const res = await callGuest<{
        reservation: string
        amount_after_tax: number
        advance_due: number
        balance_at_hotel: number
        status: string
      }>("kamra.public_api.book",
        {
          property,
          room_type: booking,
          check_in_date: search.check_in_date,
          check_out_date: checkOut,
          adults: search.adults,
          children: search.children,
          child_ages: agesToSend(childAges),
          pets: search.pets,
          ...form,
          meal_plan: selected.meal_plan,
          voucher_code: appliedVoucher,
          addons: Object.entries(addons)
            .filter(([, qty]) => qty > 0)
            .map(([experience, qty]) => ({ experience, qty })),
        },
      )
      setDone({
        reservation: res.reservation,
        amount: res.amount_after_tax,
        advance_due: Number(res.advance_due || 0),
        balance_at_hotel: Number(res.balance_at_hotel ?? res.amount_after_tax ?? 0),
        status: res.status,
      })
    } catch (e) {
      setError(serverError(e))
    } finally {
      setBusy(false)
    }
  }

  if (!data && catalogMode === "properties" && !loadFailed)
    return (
      <PropertyChooser
        properties={properties}
        stayPath={`/${search.check_in_date}/${checkOut}/${search.adults}/${search.children}`}
        query={new URLSearchParams([...new URLSearchParams(location.search)].filter(([k]) => k !== "property")).toString()}
      />
    )

  if (loadFailed)
    return (
      <div className="flex min-h-screen items-center justify-center bg-zinc-50 px-4">
        <div className="max-w-md rounded-2xl border border-zinc-200 bg-white p-8 text-center">
          <CalendarDays className="mx-auto size-10 text-zinc-300" aria-hidden />
          <h1 className="mt-4 text-xl font-semibold text-zinc-900">
            {propertySlug ? t("We couldn't find that property") : t("Online booking isn't available right now")}
          </h1>
          <p className="mt-2 text-sm text-zinc-500">
            {propertySlug
              ? t("The link may be out of date. See all the places you can book here.")
              : t("Please try again in a few minutes, or contact the property directly.")}
          </p>
          <div className="mt-6 flex justify-center gap-2">
            {propertySlug ? (
              <Button onClick={() => navigate("/book")}>{t("See all properties")}</Button>
            ) : (
              <Button onClick={() => window.location.reload()}>{t("Try again")}</Button>
            )}
          </div>
        </div>
      </div>
    )

  if (!data)
    return (
      <div className="min-h-screen bg-zinc-50" aria-busy="true" aria-label={t("Loading…")}>
        <div className="h-16 border-b border-zinc-200 bg-white" />
        <div className="mx-auto max-w-6xl animate-pulse px-4 py-6 sm:px-6">
          <div className="h-64 rounded-2xl bg-zinc-200 sm:h-[420px]" />
          <div className="mt-6 h-8 w-72 max-w-full rounded bg-zinc-200" />
          <div className="mt-3 h-4 w-96 max-w-full rounded bg-zinc-200" />
          <div className="mt-8 h-56 rounded-2xl bg-zinc-200" />
        </div>
      </div>
    )

  const p = data.property
  const minNights = p.minimum_nights || 1
  const isStr = p.property_kind === "Short Term Rental"
  const bookCta =
    p.booking_mode === "Request to Book"
      ? t("Request to book")
      : p.payment_mode === "Full online"
        ? t("Confirm & pay")
        : isStr
          ? t("Book this listing")
          : t("Book now")
  const locations = data.locations?.length
    ? data.locations
    : [{ name: p.property_name, address: p.address_line, google_maps_url: null,
         latitude: p.latitude, longitude: p.longitude, room_types: [] }]

  // Property photos for the hero: the hero image first, then the gallery,
  // then room / site covers so a page with any photo never shows a blank.
  const heroPhotos: Photo[] = [
    ...(p.hero_image ? [{ url: p.hero_image, caption: null }] : []),
    ...(p.gallery ?? []),
    ...data.room_types.flatMap((rt) => imagesOf(rt.media)),
    ...sites.filter((s) => s.cover_image).map((s) => ({ url: s.cover_image!, caption: s.name })),
  ].filter((ph, i, arr) => ph.url && arr.findIndex((x) => x.url === ph.url) === i)

  const fmtDay = (iso: string) =>
    (parseDate(iso) ?? new Date()).toLocaleDateString(lang, { weekday: "short", day: "numeric", month: "short" })
  const guestsLabel = tn(search.adults + search.children, "{n} guest", "{n} guests")
  const mealLabel = (mp: string) =>
    mp ? translate(data.meal_plans.find((m) => m.name === mp)?.label ?? mp) : t("Room only")

  // Cancellation terms from the property's real policy (the same rules as
  // cancellation_preview): free while more than free_cancel_days remain
  // before arrival. Tiered policies are not in the payload, so they get no
  // claim at all; peak dates sold non-refundable say so per room.
  const freeUntil = addDays(search.check_in_date, -p.free_cancel_days)
  const cancelTerms = (r?: StayResult): { free: boolean; text: string } | null =>
    r?.quote?.stay_rules?.non_refundable
      ? { free: false, text: t("Non-refundable") }
      : p.has_cancellation_tiers
        ? null
        : p.cancellation_fee === "None" || !p.free_cancel_days
          ? { free: true, text: t("Free cancellation") }
          : freeUntil >= todayPlus(0)
            ? { free: true, text: t("Free cancellation until {date}", { date: fmtDay(freeUntil) }) }
            : p.cancellation_fee === "Full Stay"
              ? { free: false, text: t("Non-refundable") }
              : { free: false, text: t("Cancellation fee: first night") }

  const trust: { icon: typeof Check; text: string }[] = [
    ...(p.has_cancellation_tiers ? [] : p.cancellation_fee === "None" || !p.free_cancel_days
      ? [{ icon: ShieldCheck, text: t("Free cancellation") }]
      : [{ icon: ShieldCheck, text: tn(p.free_cancel_days,
          "Free cancellation up to {n} day before arrival", "Free cancellation up to {n} days before arrival") }]),
    ...(p.payment_mode === "Pay at hotel" ? [{ icon: Wallet, text: t("No payment today, pay at the property") }] : []),
    ...(p.booking_mode !== "Request to Book" ? [{ icon: Zap, text: t("Instant confirmation") }] : []),
    { icon: Clock, text: t("Check-in from {in}, check-out by {out}", { in: p.checkin_time.slice(0, 5), out: p.checkout_time.slice(0, 5) }) },
  ]

  const mealChoices = [...new Set(Object.values(results).flatMap((r) => plansOf(r).map((pl) => pl.meal_plan)))]
  const sel = selected ? data.room_types.find((r) => r.name === selected.room_type) : null
  const selPlan = selected ? plansOf(results[selected.room_type]).find((pl) => pl.meal_plan === selected.meal_plan) : null
  const selTerms = selected ? cancelTerms(results[selected.room_type]) : null
  const roomsShown = data.room_types.filter((rt) => !availableOnly || canReserve(results[rt.name]))

  const summary = (compact: boolean) => sel && selPlan ? (
    <>
      {!compact && (
        <div className="flex gap-3">
          {imagesOf(sel.media)[0] && (
            <img src={imagesOf(sel.media)[0].url} alt="" className="size-16 shrink-0 rounded-lg object-cover" />
          )}
          <div className="min-w-0">
            <p className="font-semibold text-zinc-900">{sel.room_type_name}</p>
            <p className="text-sm text-zinc-500">{mealLabel(selPlan.meal_plan)}</p>
          </div>
        </div>
      )}
      {!compact && (
        <dl className="mt-4 space-y-1.5 border-t border-zinc-100 pt-4 text-sm">
          <div className="flex justify-between gap-3"><dt className="text-zinc-500">{t("Check-in")}</dt><dd className="font-medium text-zinc-800">{fmtDay(search.check_in_date)}</dd></div>
          <div className="flex justify-between gap-3"><dt className="text-zinc-500">{t("Check-out")}</dt><dd className="font-medium text-zinc-800">{fmtDay(checkOut)}</dd></div>
          <div className="flex justify-between gap-3"><dt className="text-zinc-500">{t("Guests")}</dt><dd className="font-medium text-zinc-800">{guestsLabel}</dd></div>
          {appliedVoucher && (
            <div className="flex justify-between gap-3"><dt className="text-zinc-500">{t("Promo code")}</dt><dd className="font-medium text-brand-700">{appliedVoucher.toUpperCase()}</dd></div>
          )}
        </dl>
      )}
      <div className={compact ? "" : "mt-4 border-t border-zinc-100 pt-4"}>
        <div className="flex items-baseline justify-between gap-3">
          <span className={compact ? "truncate text-sm font-medium text-zinc-700" : "text-sm text-zinc-500"}>
            {compact ? sel.room_type_name : tn(nights, "Total for {n} night", "Total for {n} nights")}
          </span>
          <span className="text-xl font-semibold tabular-nums text-zinc-900">{money(selPlan.amount_after_tax)}</span>
        </div>
        <p className="mt-0.5 text-end text-xs text-zinc-500">
          {(selPlan.advance_due || 0) > 0
            ? t("{amount} due now", { amount: money(selPlan.advance_due || 0) })
            : t("Taxes and fees included")}
        </p>
      </div>
    </>
  ) : null

  return (
    <div className="relative min-h-screen bg-zinc-50" style={accentVars(data?.property.brand_accent)}>
      {/* sticky header: who you are booking with, and the stay */}
      <header className="sticky top-0 z-30 border-b border-zinc-200 bg-white/95 backdrop-blur">
        <div className="mx-auto flex max-w-6xl items-center gap-3 px-4 py-2.5 sm:px-6">
          <div className="flex min-w-0 items-center gap-2.5">
            <div className="flex size-9 shrink-0 items-center justify-center overflow-hidden rounded-lg bg-brand-600 text-sm font-semibold text-white">
              {p.logo_url
                ? <img src={p.logo_url} alt={t("{property} logo", { property: p.property_name })} className="size-full object-cover" />
                : initials(p.property_name)}
            </div>
            <span className="hidden truncate font-semibold text-zinc-900 sm:block">{p.property_name}</span>
          </div>
          <button
            type="button"
            onClick={() => setEditing((e) => !e)}
            aria-expanded={editing}
            aria-controls="stay-editor"
            className="ms-auto flex min-w-0 items-center gap-2 rounded-full border border-zinc-300 bg-white py-1.5 ps-3.5 pe-1.5 text-sm shadow-sm hover:border-zinc-400 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-600 sm:ms-6"
          >
            <CalendarDays className="size-4 shrink-0 text-zinc-500" aria-hidden />
            <span className="truncate font-medium text-zinc-800">
              {fmtDay(search.check_in_date)}
              <ArrowRight className="mx-1 inline size-3.5 text-zinc-400 rtl:rotate-180" aria-label={t("to")} />
              {fmtDay(checkOut)}
            </span>
            <span className="hidden shrink-0 text-zinc-500 sm:inline">{guestsLabel}</span>
            <span className="flex size-7 shrink-0 items-center justify-center rounded-full bg-brand-600 text-white">
              <Search className="size-3.5" aria-hidden />
            </span>
          </button>
          <LanguageSwitcher className="ms-auto hidden md:flex" />
        </div>

        {editing && (
          <div id="stay-editor" className="border-t border-zinc-100 bg-white">
            <form
              className="mx-auto max-w-6xl px-4 py-4 sm:px-6"
              onSubmit={(e) => {
                e.preventDefault()
                setEditing(false)
                fetchResults()
                document.getElementById("stay-results")?.scrollIntoView({ behavior: "smooth", block: "start" })
              }}
            >
              <div className={`grid grid-cols-2 gap-3 ${p.pets_allowed ? "md:grid-cols-5" : "md:grid-cols-4"}`}>
                <label className="block">
                  <span className="mb-1 block text-xs font-medium text-zinc-500">{t("Check-in")}</span>
                  <input
                    type="date"
                    className={inputCls}
                    value={search.check_in_date}
                    min={todayPlus(0)}
                    onChange={(e) => {
                      const check_in_date = e.target.value
                      if (!parseDate(check_in_date)) return
                      const minCheckOut = addDays(check_in_date, minNights)
                      setSearch((s) => ({
                        ...s,
                        check_in_date,
                        check_out_date:
                          s.check_out_date > minCheckOut ? s.check_out_date : minCheckOut,
                      }))
                    }}
                  />
                </label>
                <label className="block">
                  <span className="mb-1 block text-xs font-medium text-zinc-500">{t("Check-out")}</span>
                  <input
                    type="date"
                    className={inputCls}
                    value={search.check_out_date}
                    min={addDays(search.check_in_date, minNights)}
                    onChange={(e) => {
                      if (parseDate(e.target.value) && e.target.value > search.check_in_date)
                        setSearch({ ...search, check_out_date: e.target.value })
                    }}
                  />
                </label>
                <label className="block">
                  <span className="mb-1 block text-xs font-medium text-zinc-500">{t("Adults")}</span>
                  <input
                    type="number"
                    min={1}
                    max={maxAdults || undefined}
                    className={inputCls}
                    value={search.adults}
                    onChange={(e) =>
                      setSearch({ ...search, adults: clampGuests(Number(e.target.value), 1, maxAdults) })
                    }
                  />
                  {maxAdults > 0 && search.adults >= maxAdults && (
                    <span className="mt-1 block text-xs text-zinc-500">{t("Sleeps up to {n}", { n: maxAdults })}</span>
                  )}
                </label>
                <label className="block">
                  <span className="mb-1 block text-xs font-medium text-zinc-500">{t("Children")}</span>
                  <input
                    type="number"
                    min={0}
                    max={maxChildren || undefined}
                    className={inputCls}
                    value={search.children}
                    onChange={(e) =>
                      setSearch({ ...search, children: clampGuests(Number(e.target.value), 0, maxChildren) })
                    }
                  />
                  {maxChildren > 0 && search.children >= maxChildren && (
                    <span className="mt-1 block text-xs text-zinc-500">{t("Up to {n} children", { n: maxChildren })}</span>
                  )}
                </label>
                {!!p.pets_allowed && (
                  <label className="block">
                    <span className="mb-1 block text-xs font-medium text-zinc-500">{t("Pets")}</span>
                    <input
                      type="number"
                      min={0}
                      className={inputCls}
                      value={search.pets}
                      onChange={(e) => setSearch({ ...search, pets: Math.max(0, Number(e.target.value) || 0) })}
                    />
                    {(p.pet_charge || 0) > 0 && (
                      <span className="mt-1 block text-xs text-zinc-500">
                        {money(p.pet_charge || 0)} {petChargeBasis(p.pet_charge_basis, t)}
                      </span>
                    )}
                  </label>
                )}
              </div>
              <div className="mt-3">
                <ChildAges ages={childAges} onChange={setChildAges} selectCls={inputCls} />
              </div>
              <div className="mt-3 flex flex-col gap-3 sm:flex-row sm:items-end">
                <label className="block sm:w-72">
                  <span className="mb-1 block text-xs font-medium text-zinc-500">{t("Promo code")}</span>
                  <div className="flex gap-2">
                    <input className={inputCls} placeholder={t("Have a code?")}
                      value={voucher}
                      onChange={(e) => {
                        setVoucher(e.target.value)
                        setVoucherMsg(null)
                      }} />
                    <Button type="button" variant="outline" className="shrink-0 px-4"
                      disabled={!voucher.trim()} onClick={applyVoucher}>
                      {t("Apply")}
                    </Button>
                  </div>
                </label>
                <p className="text-xs text-zinc-500 sm:pb-3">
                  {tn(nights, "{n} night", "{n} nights")}
                  {minNights > 1 ? `, ${t("{n}-night minimum", { n: minNights })}` : ""}
                </p>
                <Button type="submit" className="justify-center gap-2 px-6 py-2.5 text-base sm:ms-auto">
                  <Search className="size-4" aria-hidden />
                  {t("Check availability")}
                </Button>
              </div>
              {voucherMsg && (
                <p role="status" className={"mt-2 text-sm " + (voucherMsg.ok ? "text-brand-700" : "text-rose-600")}>
                  {translate(voucherMsg.text)}
                </p>
              )}
            </form>
          </div>
        )}
      </header>

      <main className={"mx-auto max-w-6xl px-4 pt-4 sm:px-6 sm:pt-6 " + (sel ? "pb-32 lg:pb-16" : "pb-16")}>
        {/* hero: one large photo and four small, or a brand panel */}
        {heroPhotos.length ? (
          <div className="relative">
            <div className="grid h-64 grid-cols-1 gap-2 overflow-hidden rounded-2xl sm:h-[420px] md:grid-cols-4 md:grid-rows-2">
              {heroPhotos.slice(0, 5).map((ph, i) => (
                <button
                  key={ph.url}
                  type="button"
                  onClick={() => setLightbox({ photos: heroPhotos, start: i, title: p.property_name })}
                  className={
                    "relative overflow-hidden bg-zinc-200 focus-visible:outline-2 focus-visible:-outline-offset-4 focus-visible:outline-white " +
                    (i > 0 ? "hidden md:block" : heroPhotos.length >= 5 ? "md:col-span-2 md:row-span-2" : "md:col-span-4 md:row-span-2")
                  }
                  aria-label={t("Open photo {n} of {name}", { n: i + 1, name: p.property_name })}
                >
                  <img src={ph.url} alt={ph.caption ? translate(ph.caption) : ""}
                    className="size-full object-cover transition duration-500 hover:scale-[1.02]"
                    loading={i === 0 ? "eager" : "lazy"} />
                </button>
              )).filter((_, i) => heroPhotos.length >= 5 || i === 0)}
            </div>
            {heroPhotos.length > 1 && (
              <button
                type="button"
                onClick={() => setLightbox({ photos: heroPhotos, start: 0, title: p.property_name })}
                className="absolute bottom-3 end-3 inline-flex items-center gap-2 rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm font-medium text-zinc-800 shadow-sm hover:bg-zinc-50"
              >
                <Images className="size-4" aria-hidden />
                {t("See all {n} photos", { n: heroPhotos.length })}
              </button>
            )}
          </div>
        ) : (
          <div className="flex h-40 items-end rounded-2xl bg-brand-900 p-6 sm:h-56">
            <span className="text-5xl font-semibold tracking-tight text-white/90">{initials(p.property_name)}</span>
          </div>
        )}

        <div className="mt-6 lg:grid lg:grid-cols-[minmax(0,1fr)_320px] lg:gap-10">
          <div className="min-w-0">
            {/* who and where */}
            <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-zinc-500">
              {p.star_category && (
                <span className="inline-flex items-center gap-1 font-medium text-zinc-700">
                  <Star className="size-3.5 fill-amber-400 text-amber-400" aria-hidden />
                  {translate(p.star_category)}
                </span>
              )}
              <span className="inline-flex items-center gap-1">
                <MapPin className="size-3.5" aria-hidden />
                {[p.address_line, p.city, translate(p.state)].filter(Boolean).join(", ")}
              </span>
            </div>
            <h1 className="mt-1.5 text-3xl font-semibold tracking-tight text-zinc-900 sm:text-4xl">
              {p.property_name}
            </h1>
            {p.description && (
              <p className="mt-3 max-w-2xl text-[15px] leading-relaxed text-zinc-600">{p.description}</p>
            )}
            <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1 text-sm">
              {p.phone && (
                <a href={`tel:${formatPhoneTel(p.phone, p.country)}`}
                  className="inline-flex items-center gap-1 text-zinc-600 underline-offset-2 hover:underline">
                  <Phone className="size-3.5" aria-hidden />
                  {formatPhoneDisplay(p.phone, p.country)}
                </a>
              )}
              {p.google_reviews_url && (
                <a href={p.google_reviews_url} target="_blank" rel="noreferrer"
                  className="inline-flex items-center gap-1 text-zinc-600 underline-offset-2 hover:underline">
                  {t("Google Reviews")} <ExternalLink className="size-3.5" aria-hidden />
                </a>
              )}
              {p.tripadvisor_url && (
                <a href={p.tripadvisor_url} target="_blank" rel="noreferrer"
                  className="inline-flex items-center gap-1 text-zinc-600 underline-offset-2 hover:underline">
                  {t("TripAdvisor")} <ExternalLink className="size-3.5" aria-hidden />
                </a>
              )}
            </div>
            {p.amenities.length > 0 && (
              <ul className="mt-5 flex flex-wrap gap-2" aria-label={t("Amenities")}>
                {p.amenities.map((a) => (
                  <li key={a} className="inline-flex items-center gap-1.5 rounded-full border border-zinc-200 bg-white px-3 py-1 text-sm text-zinc-700">
                    <Check className="size-3.5 text-brand-600" aria-hidden />
                    {translate(a)}
                  </li>
                ))}
              </ul>
            )}

            {/* what booking here gets you - each line from a real setting */}
            <ul className="mt-6 grid gap-x-6 gap-y-3 rounded-2xl bg-brand-50 p-5 sm:grid-cols-2">
              {trust.map(({ icon: Icon, text }) => (
                <li key={text} className="flex items-start gap-2.5 text-sm text-zinc-800">
                  <Icon className="mt-0.5 size-4 shrink-0 text-brand-700" aria-hidden />
                  {text}
                </li>
              ))}
            </ul>

            {catalogMode === "sites" && sites.length > 0 ? (
              <section id="stay-results" className="mt-10 scroll-mt-20">
                <h2 className="text-2xl font-semibold tracking-tight text-zinc-900">{t("Places to stay")}</h2>
                <p className="mt-1 text-sm text-zinc-500">{t("Pick a villa, then choose a room or the whole house.")}</p>
                <div className="mt-5 grid gap-6 sm:grid-cols-2">
                  {sites.map((site) => {
                    const stayPath = site.slug
                      ? `/stay/${site.slug}/${search.check_in_date}/${checkOut}/${search.adults}/${search.children}`
                      : "/book"
                    const count = site.listing_count ?? site.room_types.length
                    return (
                      <Link
                        key={site.slug ?? site.name}
                        to={stayPath}
                        className="group overflow-hidden rounded-2xl border border-zinc-200 bg-white transition hover:border-zinc-300 hover:shadow-lg"
                      >
                        <div className="relative aspect-[4/3] overflow-hidden bg-zinc-100">
                          {site.cover_image ? (
                            <img src={site.cover_image} alt="" loading="lazy"
                              className="size-full object-cover transition duration-500 group-hover:scale-[1.03]" />
                          ) : (
                            <div className="flex size-full items-center justify-center bg-brand-900 text-white">
                              <span className="text-4xl font-semibold tracking-tight">{initials(site.name)}</span>
                            </div>
                          )}
                        </div>
                        <div className="p-5">
                          <h3 className="text-lg font-semibold text-zinc-900">{site.name}</h3>
                          {(site.address || site.city) && (
                            <p className="mt-1 inline-flex items-start gap-1.5 text-sm text-zinc-500">
                              <MapPin className="mt-0.5 size-3.5 shrink-0" aria-hidden />
                              <span>{site.address || [site.city, site.state].filter(Boolean).join(", ")}</span>
                            </p>
                          )}
                          <div className="mt-4 flex items-end justify-between gap-2 border-t border-zinc-100 pt-4">
                            <p className="text-sm text-zinc-500">
                              <span className="text-lg font-semibold text-zinc-900">{money(site.from_rate)}</span>
                              {" "}/ {t("night")}
                            </p>
                            <span className="inline-flex items-center gap-1 text-sm font-medium text-brand-700">
                              {tn(count, "{n} listing", "{n} listings")}
                              <ChevronRight className="size-4 rtl:rotate-180" aria-hidden />
                            </span>
                          </div>
                        </div>
                      </Link>
                    )
                  })}
                </div>
              </section>
            ) : (
              <section id="stay-results" className="mt-10 scroll-mt-20" aria-busy={loadingRates}>
                <div className="flex flex-wrap items-end justify-between gap-3">
                  <div>
                    <h2 className="text-2xl font-semibold tracking-tight text-zinc-900">
                      {isStr ? t("Choose your stay") : t("Choose your room")}
                    </h2>
                    <p className="mt-1 text-sm text-zinc-500">
                      {fmtDay(search.check_in_date)} {t("to")} {fmtDay(checkOut)}, {tn(nights, "{n} night", "{n} nights")}, {guestsLabel}
                    </p>
                  </div>
                  <button type="button" onClick={() => { setEditing(true); window.scrollTo({ top: 0, behavior: "smooth" }) }}
                    className="text-sm font-medium text-brand-700 underline-offset-2 hover:underline">
                    {t("Change dates or guests")}
                  </button>
                </div>

                {/* filters */}
                <div className="mt-4 flex flex-wrap items-center gap-2">
                  {mealChoices.length > 1 && (
                    <div className="flex flex-wrap gap-2" role="group" aria-label={t("Meal plan")}>
                      {[null, ...mealChoices].map((mp) => (
                        <button key={mp ?? "all"} type="button"
                          aria-pressed={mealFilter === mp}
                          onClick={() => setMealFilter(mp)}
                          className={"rounded-full border px-3 py-1.5 text-sm transition " +
                            (mealFilter === mp
                              ? "border-brand-600 bg-brand-600 text-white"
                              : "border-zinc-300 bg-white text-zinc-700 hover:border-zinc-400")}>
                          {mp === null ? t("All rates") : mealLabel(mp)}
                        </button>
                      ))}
                    </div>
                  )}
                  <label className="ms-auto inline-flex cursor-pointer items-center gap-2 text-sm text-zinc-700">
                    <input type="checkbox" className="peer sr-only" checked={availableOnly}
                      onChange={(e) => setAvailableOnly(e.target.checked)} />
                    <span className="relative h-5 w-9 rounded-full bg-zinc-300 transition peer-checked:bg-brand-600 peer-focus-visible:outline-2 peer-focus-visible:outline-offset-2 peer-focus-visible:outline-brand-600 after:absolute after:start-0.5 after:top-0.5 after:size-4 after:rounded-full after:bg-white after:transition peer-checked:after:translate-x-4 rtl:peer-checked:after:-translate-x-4" aria-hidden />
                    {t("Available only")}
                  </label>
                </div>

                {ratesFailed && (
                  <p role="alert" className="mt-4 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
                    {t("We couldn't load prices for these dates. Try different dates, or contact the property.")}
                  </p>
                )}

                <div className="mt-5 space-y-5">
                  {roomsShown.length === 0 && (
                    <div className="rounded-2xl border border-dashed border-zinc-300 bg-white px-6 py-10 text-center">
                      <p className="font-medium text-zinc-800">{t("Nothing is available for these dates")}</p>
                      <p className="mt-1 text-sm text-zinc-500">{t("Try other dates, or fewer guests per room.")}</p>
                      <Button className="mt-4" variant="outline" onClick={() => { setEditing(true); window.scrollTo({ top: 0, behavior: "smooth" }) }}>
                        {t("Change dates or guests")}
                      </Button>
                    </div>
                  )}
                  {roomsShown.map((rt) => {
                    const r = results[rt.name]
                    const photos: Photo[] = imagesOf(rt.media)
                    const plans = plansOf(r).filter((pl) => mealFilter === null || pl.meal_plan === mealFilter)
                    const reservable = canReserve(r) && !agesMissing
                    const soldOut = r && r.rooms_left === 0
                    const terms = cancelTerms(r)
                    return (
                      <article key={rt.name}
                        className="overflow-hidden rounded-2xl border border-zinc-200 bg-white md:grid md:grid-cols-[minmax(0,5fr)_minmax(0,7fr)]">
                        <div className="md:border-e md:border-zinc-100">
                          <PhotoStrip photos={photos} name={rt.room_type_name}
                            onOpen={(i) => setLightbox({ photos, start: i, title: rt.room_type_name })} />
                          <div className="p-5">
                            <h3 className="text-lg font-semibold text-zinc-900">{rt.room_type_name}</h3>
                            {locations.length > 1 && rt.location_name && (
                              <p className="mt-0.5 inline-flex items-center gap-1 text-xs font-medium text-brand-700">
                                <MapPin className="size-3.5" aria-hidden />
                                {rt.location_name}
                              </p>
                            )}
                            <ul className="mt-2 space-y-1 text-sm text-zinc-600">
                              <li className="flex items-center gap-2">
                                <Users className="size-4 shrink-0 text-zinc-400" aria-hidden />
                                {rt.children_capacity > 0
                                  ? tn(rt.children_capacity, "Sleeps {adults} adults and {n} child", "Sleeps {adults} adults and {n} children", { adults: rt.adults_capacity })
                                  : t("Up to {n} adults", { n: rt.adults_capacity })}
                              </li>
                              {rt.bed_type && (
                                <li className="flex items-center gap-2">
                                  <BedDouble className="size-4 shrink-0 text-zinc-400" aria-hidden />
                                  {t("{type} bed", { type: translate(rt.bed_type) })}
                                </li>
                              )}
                              {rt.room_view && (
                                <li className="flex items-center gap-2">
                                  <Eye className="size-4 shrink-0 text-zinc-400" aria-hidden />
                                  {t("{view} view", { view: translate(rt.room_view) })}
                                </li>
                              )}
                            </ul>
                            {rt.amenities.length > 0 && (
                              <ul className="mt-3 flex flex-wrap gap-1.5">
                                {rt.amenities.slice(0, 4).map((a) => (
                                  <li key={a} className="rounded-md bg-zinc-100 px-2 py-0.5 text-xs text-zinc-600">{translate(a)}</li>
                                ))}
                              </ul>
                            )}
                            {(rt.description || rt.amenities.length > 4) && (
                              <details className="group mt-3 text-sm">
                                <summary className="inline-flex cursor-pointer list-none items-center gap-1 font-medium text-brand-700 [&::-webkit-details-marker]:hidden">
                                  {t("Room details")}
                                  <ChevronDown className="size-4 transition group-open:rotate-180" aria-hidden />
                                </summary>
                                {rt.description && <p className="mt-2 leading-relaxed text-zinc-600">{rt.description}</p>}
                                {rt.amenities.length > 0 && (
                                  <ul className="mt-2 grid grid-cols-2 gap-x-3 gap-y-1">
                                    {rt.amenities.map((a) => (
                                      <li key={a} className="flex items-center gap-1.5 text-zinc-600">
                                        <Check className="size-3.5 shrink-0 text-brand-600" aria-hidden />
                                        {translate(a)}
                                      </li>
                                    ))}
                                  </ul>
                                )}
                                {rt.listing_slug && (
                                  <Link to={`/stay/${rt.listing_slug}`} className="mt-3 inline-flex items-center gap-1 font-medium text-zinc-700 underline-offset-2 hover:underline">
                                    {t("View listing")}
                                    <ChevronRight className="size-4 rtl:rotate-180" aria-hidden />
                                  </Link>
                                )}
                              </details>
                            )}
                          </div>
                        </div>

                        {/* rates for this room */}
                        <div className="border-t border-zinc-100 p-4 sm:p-5 md:border-t-0">
                          {!r && loadingRates ? (
                            <div className="space-y-3" aria-hidden>
                              {[0, 1].map((k) => (
                                <div key={k} className="h-24 animate-pulse rounded-xl bg-zinc-100" />
                              ))}
                            </div>
                          ) : !r ? (
                            <p className="text-sm text-zinc-500">{t("From {amount} per night", { amount: money(rt.base_price) })}</p>
                          ) : !canReserve(r) ? (
                            <div className="flex h-full flex-col items-start justify-center gap-2 rounded-xl bg-zinc-50 p-5">
                              <p className="font-medium text-zinc-800">
                                {soldOut ? t("Sold out for these dates") : t("Not available for this search")}
                              </p>
                              <StayNotice row={r} />
                              <button type="button" onClick={() => { setEditing(true); window.scrollTo({ top: 0, behavior: "smooth" }) }}
                                className="text-sm font-medium text-brand-700 underline-offset-2 hover:underline">
                                {t("Try other dates")}
                              </button>
                            </div>
                          ) : (
                            <>
                              <div className="mb-3 flex flex-wrap items-center gap-2">
                                {r.rooms_left <= 3 && (
                                  <Badge tone="rose">
                                    {tn(r.rooms_left, "Only {n} room left for these dates", "Only {n} rooms left for these dates")}
                                  </Badge>
                                )}
                                <StayNotice row={r} />
                              </div>
                              {plans.length === 0 && (
                                <p className="text-sm text-zinc-500">{t("No rate with this meal plan. Show all rates to see the others.")}</p>
                              )}
                              <ul className="divide-y divide-zinc-200 overflow-hidden rounded-xl border border-zinc-200">
                                {plans.map((pl) => {
                                  const on = selected?.room_type === rt.name && selected.meal_plan === pl.meal_plan
                                  return (
                                    <li key={pl.meal_plan}
                                      className={"p-4 transition " + (on ? "bg-brand-50 shadow-[inset_3px_0_0_var(--color-brand-600)] rtl:shadow-[inset_-3px_0_0_var(--color-brand-600)]" : "")}>
                                      <div className="flex flex-wrap items-center gap-x-4 gap-y-3">
                                        <div className="min-w-0 flex-1 basis-52 space-y-1">
                                          <p className="font-medium text-zinc-900">{mealLabel(pl.meal_plan)}</p>
                                          {terms && (
                                            <p className={"flex items-center gap-1.5 text-sm " + (terms.free ? "text-brand-700" : "text-zinc-500")}>
                                              <ShieldCheck className="size-3.5 shrink-0" aria-hidden />
                                              {terms.text}
                                            </p>
                                          )}
                                          <p className="flex items-center gap-1.5 text-sm text-zinc-500">
                                            <Wallet className="size-3.5 shrink-0" aria-hidden />
                                            {(pl.advance_due || 0) > 0
                                              ? t("{amount} due now", { amount: money(pl.advance_due || 0) })
                                              : t("Pay at the property")}
                                          </p>
                                        </div>
                                        <div className="ms-auto flex items-center gap-4">
                                          <div className="text-end">
                                            {pl.list_amount && pl.list_amount > pl.amount_after_tax && (
                                              <p className="text-sm text-zinc-400 line-through tabular-nums">{money(pl.list_amount)}</p>
                                            )}
                                            <p className="text-xl font-semibold tabular-nums text-zinc-900">{money(pl.amount_after_tax)}</p>
                                            <p className="text-xs text-zinc-500">
                                              {tn(nights, "Total for {n} night, taxes and fees included", "Total for {n} nights, taxes and fees included")}
                                            </p>
                                            <p className="text-xs text-zinc-500">
                                              {t("{amount} per night", { amount: money(pl.amount_after_tax / nights) })}
                                            </p>
                                          </div>
                                          <Button
                                            variant={on ? "outline" : "primary"}
                                            className="min-w-24 justify-center whitespace-nowrap px-4 py-2"
                                            disabled={!reservable}
                                            aria-pressed={on}
                                            onClick={() => setSelected(on ? null : { room_type: rt.name, meal_plan: pl.meal_plan })}
                                          >
                                            {on ? <><Check className="size-4" aria-hidden />{t("Selected")}</> : t("Select")}
                                          </Button>
                                        </div>
                                      </div>
                                    </li>
                                  )
                                })}
                              </ul>
                              {(r.quote?.totals?.deposit_required || 0) > 0 && (
                                <p className="mt-3 text-xs text-zinc-500">
                                  {t("Refundable deposit of {amount}, payable separately", { amount: money(r.quote?.totals?.deposit_required || 0) })}
                                </p>
                              )}
                              {(r.quote?.cleaning_fee || 0) > 0 && (
                                <p className="mt-1 text-xs text-zinc-500">
                                  {t("Includes {amount} cleaning fee", { amount: money(r.quote?.cleaning_fee || 0) })}
                                </p>
                              )}
                              {(r.quote?.pet_charge || 0) > 0 && (
                                <p className="mt-1 text-xs text-zinc-500">
                                  {tn(search.pets, "Includes {amount} for {n} pet", "Includes {amount} for {n} pets", {
                                    amount: money(r.quote?.pet_charge || 0),
                                  })}
                                </p>
                              )}
                              {agesMissing && (
                                <p className="mt-2 text-xs text-amber-700">{t("Choose each child's age; this determines the price.")}</p>
                              )}
                            </>
                          )}
                        </div>
                      </article>
                    )
                  })}
                </div>
              </section>
            )}

            {catalogMode !== "sites" && (
              <>
                <section className="mt-14 grid gap-8 border-t border-zinc-200 pt-10 md:grid-cols-2">
                  <div>
                    <h2 className="text-xl font-semibold text-zinc-900">
                      {isStr ? t("Stay policies") : t("Hotel Policies & Rules")}
                    </h2>
                    <dl className="mt-4 divide-y divide-zinc-100 rounded-2xl border border-zinc-200 bg-white px-5 text-sm">
                      <div className="flex justify-between gap-4 py-3">
                        <dt className="text-zinc-500">{t("Check-in")}</dt>
                        <dd className="font-medium text-zinc-800">{t("From {time}", { time: p.checkin_time?.slice(0, 5) })}</dd>
                      </div>
                      <div className="flex justify-between gap-4 py-3">
                        <dt className="text-zinc-500">{t("Check-out")}</dt>
                        <dd className="font-medium text-zinc-800">{t("By {time}", { time: p.checkout_time?.slice(0, 5) })}</dd>
                      </div>
                      {(p.minimum_nights || 1) > 1 && (
                        <div className="flex justify-between gap-4 py-3">
                          <dt className="text-zinc-500">{t("Minimum stay")}</dt>
                          <dd className="font-medium text-zinc-800">{tn(p.minimum_nights, "{n} night", "{n} nights")}</dd>
                        </div>
                      )}
                      {(p.cleaning_fee || 0) > 0 && (
                        <div className="flex justify-between gap-4 py-3">
                          <dt className="text-zinc-500">{t("Cleaning fee")}</dt>
                          <dd className="font-medium text-zinc-800">{t("{amount} (one-time)", { amount: money(p.cleaning_fee) })}</dd>
                        </div>
                      )}
                      {(p.security_deposit_amount || 0) > 0 && (
                        <div className="flex justify-between gap-4 py-3">
                          <dt className="text-zinc-500">{t("Security deposit")}</dt>
                          <dd className="font-medium text-zinc-800">{t("{amount} (refundable)", { amount: money(p.security_deposit_amount) })}</dd>
                        </div>
                      )}
                      <div className="flex justify-between gap-4 py-3">
                        <dt className="text-zinc-500">{t("Cancellation")}</dt>
                        <dd className="max-w-[60%] text-end font-medium text-zinc-800">
                          {(p.free_cancel_days || 0) > 0
                            ? tn(p.free_cancel_days, "Free cancellation up to {n} day before arrival", "Free cancellation up to {n} days before arrival")
                            : t("According to the property policy")}
                          {p.cancellation_fee && p.cancellation_fee !== "None"
                            ? `, ${t("fee: {amount}", { amount: translate(p.cancellation_fee) })}`
                            : ""}
                        </dd>
                      </div>
                      {!!p.pets_allowed && (p.pet_charge || 0) > 0 && (
                        <div className="flex justify-between gap-4 py-3">
                          <dt className="text-zinc-500">{t("Pet charge")}</dt>
                          <dd className="font-medium text-zinc-800">{money(p.pet_charge || 0)} {petChargeBasis(p.pet_charge_basis, t)}</dd>
                        </div>
                      )}
                      {([
                        [t("House Rules"), p.house_rules],
                        [t("Pets Policy"), p.pets_policy],
                        [t("Children & Extra Beds"), p.children_policy],
                        [t("Extra Bed Policy"), p.extra_bed_policy],
                      ] as const).filter(([, v]) => v).map(([label, v]) => (
                        <div key={label} className="py-3">
                          <dt className="font-medium text-zinc-700">{label}</dt>
                          <dd className="mt-1 whitespace-pre-line text-zinc-600">{v}</dd>
                        </div>
                      ))}
                    </dl>
                  </div>

                  {/* Map & Directions - one card per villa/site when the property
                      spans multiple addresses, one card when it doesn't. */}
                  <div>
                    <h2 className="text-xl font-semibold text-zinc-900">
                      {locations.length > 1 ? t("Our Locations") : t("Location & Directions")}
                    </h2>
                    <div className="mt-4 space-y-4">
                      {locations.map((loc, i) => (
                        <div key={loc.name + i} className="space-y-3 rounded-2xl border border-zinc-200 bg-white p-5">
                          {locations.length > 1 && (
                            <p className="text-sm font-semibold text-zinc-800">{loc.name}</p>
                          )}
                          {loc.latitude && loc.longitude ? (
                            <iframe
                              title={t("{name} map", { name: loc.name })}
                              width="100%"
                              height="220"
                              loading="lazy"
                              src={`https://maps.google.com/maps?q=${loc.latitude},${loc.longitude}&t=&z=15&ie=UTF8&iwloc=&output=embed`}
                              className="rounded-lg border border-zinc-200"
                            />
                          ) : null}
                          <p className="flex items-start gap-2 text-sm font-medium text-zinc-800">
                            <MapPin className="mt-0.5 size-4 shrink-0 text-brand-600" aria-hidden />
                            {loc.address || `${p.city}, ${p.state}`}
                          </p>
                          {loc.google_maps_url && (
                            <a href={loc.google_maps_url} target="_blank" rel="noreferrer"
                              className="inline-flex items-center gap-1 text-xs font-medium text-brand-700 hover:underline">
                              {t("Open in Google Maps")} <ExternalLink className="size-3" aria-hidden />
                            </a>
                          )}
                          {locations.length > 1 && loc.room_types.length > 0 && (
                            <p className="border-t border-zinc-100 pt-3 text-xs text-zinc-500">
                              {t("Rooms here:")}{" "}
                              {loc.room_types
                                .map((rt) => data.room_types.find((r) => r.name === rt)?.room_type_name || rt)
                                .join(", ")}
                            </p>
                          )}
                          {locations.length <= 1 && p.driving_directions && (
                            <div className="border-t border-zinc-100 pt-3 text-sm text-zinc-600">
                              <span className="mb-1 block font-medium text-zinc-700">{t("Driving Directions")}</span>
                              <p className="whitespace-pre-line leading-relaxed">{p.driving_directions}</p>
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                </section>

                {p.faqs && p.faqs.length > 0 && (
                  <section className="mt-14 border-t border-zinc-200 pt-10">
                    <h2 className="text-xl font-semibold text-zinc-900">{t("Frequently Asked Questions")}</h2>
                    <div className="mt-4 divide-y divide-zinc-200 rounded-2xl border border-zinc-200 bg-white">
                      {p.faqs.map((faq, i) => (
                        <details key={i} className="group px-5 py-4">
                          <summary className="flex cursor-pointer list-none items-center justify-between gap-4 font-medium text-zinc-800 [&::-webkit-details-marker]:hidden">
                            {faq.question}
                            <ChevronDown className="size-4 shrink-0 text-zinc-500 transition group-open:rotate-180" aria-hidden />
                          </summary>
                          <p className="mt-2 text-sm leading-relaxed text-zinc-600">{faq.answer}</p>
                        </details>
                      ))}
                    </div>
                  </section>
                )}
              </>
            )}

            <div className="mt-12 flex flex-col items-center gap-3">
              <LanguageSwitcher className="md:hidden" />
              <p className="text-center text-xs text-zinc-400">
                {t("Powered by Kamra - the open-source, agent-ready hotel PMS")}
              </p>
            </div>
          </div>

          {/* booking summary: a sidebar on desktop */}
          {catalogMode !== "sites" && (
            <aside className="hidden lg:block">
              <div className="sticky top-20 rounded-2xl border border-zinc-200 bg-white p-5 shadow-sm">
                <h2 className="text-base font-semibold text-zinc-900">{t("Your stay")}</h2>
                {sel && selPlan ? (
                  <div className="mt-4">
                    {summary(false)}
                    <Button className="mt-5 w-full justify-center py-2.5 text-base" onClick={() => setBooking(sel.name)}>
                      {t("Continue")}
                    </Button>
                  </div>
                ) : (
                  <div className="mt-3 text-sm text-zinc-500">
                    <p>{fmtDay(search.check_in_date)} {t("to")} {fmtDay(checkOut)}</p>
                    <p>{tn(nights, "{n} night", "{n} nights")}, {guestsLabel}</p>
                    <p className="mt-4 rounded-xl bg-zinc-50 p-4 text-zinc-600">{t("Select a room and rate to see your total here.")}</p>
                  </div>
                )}
              </div>
            </aside>
          )}
        </div>
      </main>

      {/* booking summary: a bottom bar on phones and tablets */}
      {sel && selPlan && !booking && (
        <div className="fixed inset-x-0 bottom-0 z-30 border-t border-zinc-200 bg-white/95 px-4 py-3 pb-[max(0.75rem,env(safe-area-inset-bottom))] shadow-[0_-4px_16px_rgba(0,0,0,0.06)] backdrop-blur lg:hidden">
          <div className="mx-auto flex max-w-6xl items-center gap-4">
            <div className="min-w-0 flex-1">{summary(true)}</div>
            <Button className="shrink-0 px-6 py-2.5 text-base" onClick={() => setBooking(sel.name)}>
              {t("Continue")}
            </Button>
          </div>
        </div>
      )}

      {lightbox && (
        <Lightbox photos={lightbox.photos} start={lightbox.start} title={lightbox.title}
          onClose={() => setLightbox(null)} />
      )}

      {booking && sel && selPlan && (
        <Sheet
          wide
          title={done ? (done.status === "Requested" ? t("Request sent") : t("Booking confirmed")) : t("Complete your booking")}
          description={done ? undefined : `${sel.room_type_name}, ${mealLabel(selPlan.meal_plan)}`}
          onClose={() => {
            setBooking(null)
            if (done) {
              setDone(null)
              setSelected(null)
              fetchResults()
            }
          }}
          footer={
            done ? (
              <Button className="w-full justify-center py-2.5" onClick={() => { setBooking(null); setDone(null); setSelected(null); fetchResults() }}>
                {t("Done")}
              </Button>
            ) : (
              <div className="w-full space-y-2">
                <PrivacyNotice propertyName={p.property_name} contact={p.privacy_contact}
                  retentionMonths={p.guest_retention_months} />
                <Button
                  className="w-full justify-center py-2.5 text-base"
                  disabled={busy || !form.guest_name.trim() || !form.phone.trim()}
                  onClick={submitBooking}
                >
                  {busy ? t("Booking…") : bookCta}
                </Button>
              </div>
            )
          }
        >
          {done ? (
            <div className="mx-auto max-w-lg py-4 text-center">
              <div className="mx-auto flex size-14 items-center justify-center rounded-full bg-brand-50">
                <Check className="size-7 text-brand-700" aria-hidden />
              </div>
              <p className="mt-4 text-sm text-zinc-500">{t("Booking number")}</p>
              <p className="text-2xl font-semibold tracking-tight text-zinc-900">{done.reservation}</p>
              <dl className="mt-6 divide-y divide-zinc-100 rounded-2xl border border-zinc-200 px-5 text-start text-sm">
                <div className="flex justify-between gap-4 py-3"><dt className="text-zinc-500">{isStr ? t("Listing") : t("Room")}</dt><dd className="text-end font-medium text-zinc-800">{sel.room_type_name}, {mealLabel(selPlan.meal_plan)}</dd></div>
                <div className="flex justify-between gap-4 py-3"><dt className="text-zinc-500">{t("Dates")}</dt><dd className="text-end font-medium text-zinc-800">{fmtDay(search.check_in_date)} {t("to")} {fmtDay(checkOut)}</dd></div>
                <div className="flex justify-between gap-4 py-3"><dt className="text-zinc-500">{t("Guests")}</dt><dd className="text-end font-medium text-zinc-800">{guestsLabel}</dd></div>
                <div className="flex justify-between gap-4 py-3"><dt className="text-zinc-500">{t("Total")}</dt><dd className="text-end font-semibold text-zinc-900">{money(done.amount)}</dd></div>
                {done.advance_due > 0 && (
                  <div className="flex justify-between gap-4 py-3"><dt className="text-zinc-500">{t("Due now")}</dt><dd className="text-end font-semibold text-zinc-900">{money(done.advance_due)}</dd></div>
                )}
                {done.balance_at_hotel > 0 && (
                  <div className="flex justify-between gap-4 py-3"><dt className="text-zinc-500">{t("Pay at the property")}</dt><dd className="text-end font-medium text-zinc-800">{money(done.balance_at_hotel)}</dd></div>
                )}
              </dl>
              <p className="mt-5 text-sm leading-relaxed text-zinc-600">
                {done.status === "Pending Payment"
                  ? `${t("Your rooms are held until the advance is received.")} `
                  : ""}
                {done.status === "Requested"
                  ? t("Your request goes to the property to confirm.")
                  : t("We've saved your number; the front desk will reach out with payment details and before arrival.")}
              </p>
            </div>
          ) : (
            <div className="space-y-6">
              {/* what they are booking */}
              <div className="flex flex-wrap items-center justify-between gap-4 rounded-2xl bg-zinc-50 p-4">
                <div className="flex min-w-0 items-center gap-3">
                  {imagesOf(sel.media)[0] && (
                    <img src={imagesOf(sel.media)[0].url} alt="" className="size-14 shrink-0 rounded-lg object-cover" />
                  )}
                  <div className="min-w-0 text-sm">
                    <p className="font-semibold text-zinc-900">{sel.room_type_name}</p>
                    <p className="text-zinc-500">
                      {fmtDay(search.check_in_date)} {t("to")} {fmtDay(checkOut)}, {guestsLabel}
                    </p>
                    {selTerms && <p className={selTerms.free ? "text-brand-700" : "text-zinc-500"}>{selTerms.text}</p>}
                  </div>
                </div>
                <div className="text-end">
                  {selPlan.list_amount && selPlan.list_amount > selPlan.amount_after_tax && (
                    <p className="text-sm text-zinc-400 line-through tabular-nums">{money(selPlan.list_amount)}</p>
                  )}
                  <p className="text-xl font-semibold tabular-nums text-zinc-900">{money(selPlan.amount_after_tax)}</p>
                  <p className="text-xs text-zinc-500">{t("Taxes and fees included")}</p>
                </div>
              </div>

              <fieldset className="grid gap-4 sm:grid-cols-2">
                <legend className="mb-3 text-base font-semibold text-zinc-900">{t("Your details")}</legend>
                <label className="block">
                  <span className="mb-1.5 block text-sm font-medium text-zinc-600">{t("Full name")}</span>
                  <input className={inputCls} value={form.guest_name} autoFocus autoComplete="name" required
                    onChange={(e) => setForm({ ...form, guest_name: e.target.value })} />
                </label>
                <label className="block">
                  <span className="mb-1.5 block text-sm font-medium text-zinc-600">{t("Phone")}</span>
                  <input className={inputCls} value={form.phone} placeholder="+…" type="tel" autoComplete="tel" required
                    onChange={(e) => setForm({ ...form, phone: e.target.value })} />
                </label>
                <label className="block sm:col-span-2">
                  <span className="mb-1.5 block text-sm font-medium text-zinc-600">{t("Email (optional)")}</span>
                  <input className={inputCls} type="email" autoComplete="email" value={form.email}
                    onChange={(e) => setForm({ ...form, email: e.target.value })} />
                </label>
                <label className="block sm:col-span-2">
                  <span className="mb-1.5 block text-sm font-medium text-zinc-600">{t("Special requests")}</span>
                  <textarea className={inputCls} rows={2} value={form.special_requests}
                    onChange={(e) => setForm({ ...form, special_requests: e.target.value })} />
                </label>
              </fieldset>

              {data.experiences.length > 0 && (
                <div>
                  <h3 className="mb-3 text-base font-semibold text-zinc-900">{t("Add experiences")}</h3>
                  <div className="grid gap-2 sm:grid-cols-2">
                    {data.experiences.map((exp) => {
                      const qty = addons[exp.name] || 0
                      const on = qty > 0
                      return (
                        <div
                          key={exp.name}
                          className={
                            "flex items-center gap-3 rounded-xl border p-2.5 " +
                            (on ? "border-brand-600 bg-brand-50" : "border-zinc-200")
                          }
                        >
                          {exp.image_url && (
                            <img src={exp.image_url} alt="" loading="lazy" className="size-12 shrink-0 rounded-lg object-cover" />
                          )}
                          <div className="min-w-0 flex-1">
                            <div className="flex items-center gap-1.5">
                              <span className="truncate text-sm font-medium text-zinc-800">{exp.experience_name}</span>
                              {exp.category && (
                                <span className="shrink-0 rounded-full bg-zinc-100 px-1.5 py-0.5 text-[10px] text-zinc-500">
                                  {translate(exp.category)}
                                </span>
                              )}
                            </div>
                            <div className="truncate text-xs text-zinc-500">
                              {money(exp.price)}
                              {exp.duration ? `, ${exp.duration}` : ""}
                            </div>
                          </div>
                          {on ? (
                            <div className="flex shrink-0 items-center gap-1.5">
                              <button type="button" aria-label={t("Remove one")}
                                className="size-7 rounded-lg border border-zinc-300 text-zinc-600 hover:bg-white"
                                onClick={() => setAddons((a) => ({ ...a, [exp.name]: qty - 1 }))}>
                                −
                              </button>
                              <span className="w-5 text-center text-sm tabular-nums">{qty}</span>
                              <button type="button" aria-label={t("Add one")}
                                className="size-7 rounded-lg border border-zinc-300 text-zinc-600 hover:bg-white"
                                onClick={() => setAddons((a) => ({ ...a, [exp.name]: qty + 1 }))}>
                                +
                              </button>
                            </div>
                          ) : (
                            <button type="button"
                              className="shrink-0 rounded-lg border border-brand-600 px-3 py-1.5 text-xs font-medium text-brand-700 hover:bg-brand-50"
                              onClick={() => setAddons((a) => ({ ...a, [exp.name]: 1 }))}>
                              {t("Add")}
                            </button>
                          )}
                        </div>
                      )
                    })}
                  </div>
                  {(() => {
                    const addonTotal = data.experiences.reduce((s, e) => s + (addons[e.name] || 0) * e.price, 0)
                    return addonTotal > 0 ? (
                      <p className="mt-2 text-end text-xs text-zinc-500">
                        {t("Experiences: +{amount} · added to your bill at the hotel", { amount: money(addonTotal) })}
                      </p>
                    ) : null
                  })()}
                </div>
              )}

              <div className="space-y-3">
                <h3 className="text-base font-semibold text-zinc-900">{t("Payment")}</h3>
                <div className="flex items-start gap-3 rounded-xl border border-zinc-200 p-4 text-sm text-zinc-700">
                  <Wallet className="mt-0.5 size-4 shrink-0 text-brand-700" aria-hidden />
                  <p>
                    {p.payment_mode === "Full online"
                      ? t("The full amount is paid online to confirm this booking.")
                      : p.payment_mode === "Advance percent"
                        ? t("A {percent}% advance is collected to confirm; the rest is paid at the hotel.", { percent: p.advance_percent })
                        : p.payment_mode === "Registration fee"
                          ? t("A registration fee of {amount} is collected to confirm; the rest is paid at the hotel.", { amount: money(p.registration_fee) })
                          : t("No payment today, pay at the property")}
                  </p>
                </div>
                {(p.security_deposit_amount || 0) > 0 && (
                  <p className="text-xs text-zinc-500">
                    {t("A refundable security deposit of {amount} may be collected separately.", { amount: money(p.security_deposit_amount) })}
                  </p>
                )}
                <label className="flex items-start gap-2 text-sm text-zinc-600">
                  <input type="checkbox" className="mt-0.5 size-4 accent-brand-600"
                    checked={Boolean(form.marketing_consent)}
                    onChange={(e) => setForm({ ...form, marketing_consent: e.target.checked ? 1 : 0 })} />
                  {t("Send me offers on WhatsApp. Reply STOP at any time to opt out.")}
                </label>
              </div>

              {error && (
                <div role="alert" className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
                  {translate(error)}
                </div>
              )}
            </div>
          )}
        </Sheet>
      )}
    </div>
  )
}
