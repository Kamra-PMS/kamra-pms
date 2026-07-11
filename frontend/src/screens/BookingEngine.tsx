import { useCallback, useEffect, useState } from "react"
import { useParams } from "react-router-dom"
import { Globe, Plus, Trash2, Eye } from "lucide-react"

import { getCurrentProperty, frappeFetch } from "../lib/api"
import ImageField from "../components/ImageField"
import { PRESETS, accentHex } from "../lib/accents"
import { serverError, updateResource } from "../lib/resource"
import { Button } from "../components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card"

type Doc = Record<string, any>

const inputCls =
  "w-full rounded-lg border border-zinc-300 bg-white px-3 py-1.5 text-sm " +
  "focus:outline-2 focus:outline-offset-1 focus:outline-brand-600"

export default function BookingEngine() {
  const property = getCurrentProperty()
  const { section = "profile" } = useParams()

  const [doc, setDoc] = useState<Doc | null>(null)
  const [busy, setBusy] = useState(false)
  const [state, setState] = useState<"idle" | "saved" | string>("idle")

  const load = useCallback(() => {
    frappeFetch<{ data: Doc }>(`/api/resource/Property/${encodeURIComponent(property)}`)
      .then((r) => setDoc(r.data))
      .catch((e) => setState(serverError(e)))
  }, [property])

  useEffect(load, [load])

  if (!doc)
    return <p className="py-20 text-center text-zinc-400">Loading Booking Engine Settings…</p>

  async function save() {
    setBusy(true)
    setState("idle")
    try {
      // Clean child table objects before sending to Frappe PUT API
      const cleanGallery = (doc?.gallery || [])
        .filter((g: any) => g.url?.trim())
        .map((g: any) => ({
          url: g.url.trim(),
          caption: g.caption || null,
        }))

      const cleanFaqs = (doc?.faqs || [])
        .filter((f: any) => f.question?.trim() && f.answer?.trim())
        .map((f: any) => ({
          question: f.question.trim(),
          answer: f.answer.trim(),
        }))

      const payload = {
        ...doc,
        gallery: cleanGallery,
        faqs: cleanFaqs,
      }

      await updateResource("Property", property, payload)
      setState("saved")
      load()
    } catch (e) {
      setState(serverError(e))
    } finally {
      setBusy(false)
    }
  }

  const updateField = (name: string, value: any) => {
    setState("idle")
    setDoc((d) => ({ ...d!, [name]: value }))
  }

  const sections = [
    { id: "profile", label: "Hotel Profile" },
    { id: "amenities", label: "Amenities" },
    { id: "photos", label: "Photos" },
    { id: "policies", label: "Policies" },
    { id: "payments", label: "Payments" },
    { id: "faq", label: "FAQ" },
    { id: "seo", label: "SEO" },
  ]

  return (
    <div className="space-y-6">
      {/* Header card with toggle and live preview */}
      <Card className="border-brand-100 bg-brand-50/20">
        <CardContent className="flex flex-wrap items-center justify-between gap-4 p-6">
          <div className="space-y-1">
            <h1 className="text-xl font-bold flex items-center gap-2 text-zinc-800">
              <Globe className="size-5 text-brand-600" />
              Booking Engine Console
            </h1>
            <p className="text-xs text-zinc-500">
              Configure your direct-booking page settings.
            </p>
          </div>
          <div className="flex items-center gap-3">
            <label className="flex items-center gap-2 rounded-lg border border-zinc-200 bg-white px-3 py-1.5 text-sm font-medium text-zinc-700 shadow-sm cursor-pointer hover:bg-zinc-50">
              <input
                type="checkbox"
                className="size-4 accent-brand-600 rounded"
                checked={Boolean(Number(doc.booking_engine_enabled ?? 0))}
                onChange={(e) => updateField("booking_engine_enabled", e.target.checked ? 1 : 0)}
              />
              Engine Live
            </label>
            <a
              href={`/book`}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1.5 rounded-lg bg-white border border-zinc-200 px-3.5 py-1.5 text-sm font-medium text-zinc-700 shadow-sm hover:bg-zinc-50"
            >
              <Eye className="size-4 text-zinc-500" />
              Preview Page
            </a>
          </div>
        </CardContent>
      </Card>

      {/* The app sidebar already lists the sections, so this screen just
          renders the active one (from the URL) full-width - no second nav. */}
      <div>
        <div>
          <Card>
            <CardHeader>
              <CardTitle>{sections.find((s) => s.id === section)?.label}</CardTitle>
              <p className="mt-1 text-xs text-zinc-400">
                Customize settings visible on the booking flow.
              </p>
            </CardHeader>
            <CardContent className="space-y-4">
              {section === "profile" && (
                <div className="space-y-4">
                  <div className="grid gap-4 sm:grid-cols-2">
                    <label className="block">
                      <span className="mb-1 block text-sm font-medium text-zinc-600">Property Name</span>
                      <input
                        className={inputCls}
                        value={doc.property_name ?? ""}
                        onChange={(e) => updateField("property_name", e.target.value)}
                      />
                    </label>
                    <label className="block">
                      <span className="mb-1 block text-sm font-medium text-zinc-600">Legal Name</span>
                      <input
                        className={inputCls}
                        value={doc.legal_name ?? ""}
                        onChange={(e) => updateField("legal_name", e.target.value)}
                      />
                    </label>
                  </div>

                  <label className="block">
                    <span className="mb-1 block text-sm font-medium text-zinc-600">About (Description)</span>
                    <textarea
                      rows={3}
                      className={inputCls}
                      value={doc.showcase_description ?? ""}
                      onChange={(e) => updateField("showcase_description", e.target.value)}
                    />
                  </label>

                  <div className="grid gap-4 sm:grid-cols-3">
                    <label className="block">
                      <span className="mb-1 block text-sm font-medium text-zinc-600">Phone</span>
                      <input
                        className={inputCls}
                        value={doc.phone ?? ""}
                        onChange={(e) => updateField("phone", e.target.value)}
                      />
                    </label>
                    <label className="block">
                      <span className="mb-1 block text-sm font-medium text-zinc-600">Email</span>
                      <input
                        className={inputCls}
                        type="email"
                        value={doc.email ?? ""}
                        onChange={(e) => updateField("email", e.target.value)}
                      />
                    </label>
                    <label className="block">
                      <span className="mb-1 block text-sm font-medium text-zinc-600">Website</span>
                      <input
                        className={inputCls}
                        value={doc.website ?? ""}
                        onChange={(e) => updateField("website", e.target.value)}
                      />
                    </label>
                  </div>

                  <div className="border-t border-zinc-100 pt-4">
                    <h3 className="text-sm font-semibold text-zinc-700 mb-2">Location & Map</h3>
                    <div className="grid gap-4 sm:grid-cols-2">
                      <label className="block">
                        <span className="mb-1 block text-sm font-medium text-zinc-600">Address Line</span>
                        <input
                          className={inputCls}
                          value={doc.address_line ?? ""}
                          onChange={(e) => updateField("address_line", e.target.value)}
                        />
                      </label>
                      <div className="grid grid-cols-2 gap-2">
                        <label className="block">
                          <span className="mb-1 block text-sm font-medium text-zinc-600">City</span>
                          <input
                            className={inputCls}
                            value={doc.city ?? ""}
                            onChange={(e) => updateField("city", e.target.value)}
                          />
                        </label>
                        <label className="block">
                          <span className="mb-1 block text-sm font-medium text-zinc-600">State</span>
                          <input
                            className={inputCls}
                            value={doc.state ?? ""}
                            onChange={(e) => updateField("state", e.target.value)}
                          />
                        </label>
                      </div>
                    </div>

                    <div className="grid gap-4 sm:grid-cols-3 mt-3">
                      <label className="block">
                        <span className="mb-1 block text-sm font-medium text-zinc-600">Country</span>
                        <input
                          className={inputCls}
                          value={doc.country ?? ""}
                          onChange={(e) => updateField("country", e.target.value)}
                        />
                      </label>
                      <label className="block">
                        <span className="mb-1 block text-sm font-medium text-zinc-600">PIN Code</span>
                        <input
                          className={inputCls}
                          value={doc.pincode ?? ""}
                          onChange={(e) => updateField("pincode", e.target.value)}
                        />
                      </label>
                      <label className="block">
                        <span className="mb-1 block text-sm font-medium text-zinc-600">Category</span>
                        <select
                          className={inputCls}
                          value={doc.star_category ?? ""}
                          onChange={(e) => updateField("star_category", e.target.value)}
                        >
                          {["", "1 Star", "2 Star", "3 Star", "4 Star", "5 Star", "Boutique", "Homestay"].map((c) => (
                            <option key={c} value={c}>
                              {c || "None"}
                            </option>
                          ))}
                        </select>
                      </label>
                    </div>

                    <div className="grid gap-4 sm:grid-cols-2 mt-3">
                      <label className="block">
                        <span className="mb-1 block text-sm font-medium text-zinc-600">Latitude</span>
                        <input
                          className={inputCls}
                          type="number"
                          step="any"
                          value={doc.latitude ?? ""}
                          onChange={(e) => updateField("latitude", e.target.value === "" ? null : Number(e.target.value))}
                        />
                      </label>
                      <label className="block">
                        <span className="mb-1 block text-sm font-medium text-zinc-600">Longitude</span>
                        <input
                          className={inputCls}
                          type="number"
                          step="any"
                          value={doc.longitude ?? ""}
                          onChange={(e) => updateField("longitude", e.target.value === "" ? null : Number(e.target.value))}
                        />
                      </label>
                    </div>

                    <label className="block mt-3">
                      <span className="mb-1 block text-sm font-medium text-zinc-600">Driving Directions</span>
                      <textarea
                        rows={2}
                        className={inputCls}
                        value={doc.driving_directions ?? ""}
                        onChange={(e) => updateField("driving_directions", e.target.value)}
                      />
                    </label>

                    {doc.latitude && doc.longitude && (
                      <div className="mt-4">
                        <span className="mb-1.5 block text-xs font-semibold text-zinc-500 uppercase tracking-wider">Map Preview</span>
                        <iframe
                          title="Embedded Location Map"
                          width="100%"
                          height="220"
                          src={`https://maps.google.com/maps?q=${doc.latitude},${doc.longitude}&t=&z=15&ie=UTF8&iwloc=&output=embed`}
                          className="rounded-lg border border-zinc-200"
                        />
                      </div>
                    )}
                  </div>

                  <div className="border-t border-zinc-100 pt-4 grid gap-4 sm:grid-cols-2">
                    <label className="block">
                      <span className="mb-1 block text-sm font-medium text-zinc-600">Google Reviews URL</span>
                      <input
                        className={inputCls}
                        value={doc.google_reviews_url ?? ""}
                        onChange={(e) => updateField("google_reviews_url", e.target.value)}
                      />
                    </label>
                    <label className="block">
                      <span className="mb-1 block text-sm font-medium text-zinc-600">TripAdvisor URL</span>
                      <input
                        className={inputCls}
                        value={doc.tripadvisor_url ?? ""}
                        onChange={(e) => updateField("tripadvisor_url", e.target.value)}
                      />
                    </label>
                  </div>
                </div>
              )}

              {section === "amenities" && (
                <label className="block">
                  <span className="mb-1 block text-sm font-medium text-zinc-600">
                    Property-level Amenities (one per line)
                  </span>
                  <textarea
                    rows={8}
                    className={inputCls}
                    placeholder={"Swimming Pool\nFree Parking\nComplimentary Wi-Fi\nFine-dining Restaurant\nSpa & Wellness"}
                    value={doc.property_amenities ?? ""}
                    onChange={(e) => updateField("property_amenities", e.target.value)}
                  />
                </label>
              )}

              {section === "photos" && (
                <div className="space-y-4">
                  <ImageField
                    label="Logo"
                    hint="Square, 512×512px · PNG or SVG with a transparent background. Shown on the booking page and invoices."
                    accept="image/png,image/svg+xml,image/webp"
                    value={doc.logo_url ?? ""}
                    onChange={(v) => updateField("logo_url", v)}
                  />

                  <ImageField
                    label="Hero showcase image"
                    hint="1920×1080px (16:9 landscape) · JPG or WebP, under 2 MB. The big photo at the top of the booking page."
                    value={doc.hero_image ?? ""}
                    onChange={(v) => updateField("hero_image", v)}
                  />

                  <div className="block">
                    <span className="mb-1 block text-sm font-medium text-zinc-600">
                      Booking page accent
                    </span>
                    <div className="flex flex-wrap items-center gap-2">
                      <input
                        type="color"
                        aria-label="Accent colour"
                        className="size-10 cursor-pointer rounded-lg border border-zinc-300 bg-white p-0.5"
                        value={accentHex(doc.brand_accent)}
                        onChange={(e) => updateField("brand_accent", e.target.value)}
                      />
                      <input
                        className={inputCls + " !w-32 font-mono"}
                        placeholder="#0f6b54"
                        value={doc.brand_accent ?? ""}
                        onChange={(e) => updateField("brand_accent", e.target.value)}
                      />
                      <span className="text-xs text-zinc-400">or a quick preset:</span>
                      {PRESETS.map((p) => (
                        <button
                          key={p.name}
                          type="button"
                          title={p.name}
                          aria-label={p.name}
                          className={
                            "size-6 rounded-full border-2 " +
                            (accentHex(doc.brand_accent).toLowerCase() === p.hex
                              ? "border-zinc-800"
                              : "border-white shadow")
                          }
                          style={{ background: p.hex }}
                          onClick={() => updateField("brand_accent", p.hex)}
                        />
                      ))}
                    </div>
                    <p className="mt-1 text-xs text-zinc-400">
                      Buttons, links and highlights on the guest page take this
                      colour — pick any hex to match the hotel's branding.
                    </p>
                  </div>

                  <div className="border-t border-zinc-100 pt-4">
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-sm font-semibold text-zinc-700">
                        Photo Gallery
                        <span className="ml-2 text-xs font-normal text-zinc-400">
                          1600×900px (16:9), JPG/WebP — same shape keeps the grid tidy
                        </span>
                      </span>
                      <Button
                        variant="outline"
                        onClick={() => {
                          const gallery = [...(doc.gallery || []), { url: "", caption: "" }]
                          updateField("gallery", gallery)
                        }}
                      >
                        <Plus className="size-4" /> Add Photo
                      </Button>
                    </div>

                    <div className="space-y-2">
                      {(doc.gallery || []).map((photo: any, index: number) => (
                        <div key={index} className="flex gap-2">
                          <div className="min-w-0 flex-1">
                            <ImageField
                              hint=""
                              placeholder="Upload, or paste a photo URL"
                              value={photo.url ?? ""}
                              onChange={(v) => {
                                const gallery = (doc.gallery || []).map((g: any, idx: number) =>
                                  idx === index ? { ...g, url: v } : g
                                )
                                updateField("gallery", gallery)
                              }}
                            />
                          </div>
                          <input
                            className="w-48 rounded-lg border border-zinc-300 px-3 py-1.5 text-sm"
                            placeholder="Caption"
                            value={photo.caption ?? ""}
                            onChange={(e) => {
                              const gallery = (doc.gallery || []).map((g: any, idx: number) =>
                                idx === index ? { ...g, caption: e.target.value } : g
                              )
                              updateField("gallery", gallery)
                            }}
                          />
                          <button
                            onClick={() => {
                              const gallery = (doc.gallery || []).filter((_: any, idx: number) => idx !== index)
                              updateField("gallery", gallery)
                            }}
                            className="rounded-lg px-2 text-rose-500 hover:bg-rose-50"
                          >
                            <Trash2 className="size-4" />
                          </button>
                        </div>
                      ))}
                    </div>

                    {/* Previews */}
                    {(doc.gallery || []).filter((g: any) => g.url?.trim()).length > 0 && (
                      <div className="mt-4 flex gap-3 overflow-x-auto pb-2">
                        {(doc.gallery || [])
                          .filter((g: any) => g.url?.trim())
                          .map((g: any, index: number) => (
                            <div key={index} className="relative size-20 shrink-0 border border-zinc-100 rounded-lg overflow-hidden bg-zinc-50">
                              <img src={g.url} alt="" className="size-full object-cover" />
                            </div>
                          ))}
                      </div>
                    )}
                  </div>
                </div>
              )}

              {section === "payments" && (
                <div className="space-y-4">
                  <p className="text-sm text-zinc-500">
                    What guests pay online when booking on your public page.
                    Existing bookings keep the terms they were made under - a
                    change here only affects new bookings.
                  </p>
                  <label className="block">
                    <span className="mb-1 block text-sm font-medium text-zinc-600">
                      Collect on booking
                    </span>
                    <select
                      className={inputCls}
                      value={doc.booking_payment_mode ?? "Pay at hotel"}
                      onChange={(e) => updateField("booking_payment_mode", e.target.value)}
                    >
                      <option>Pay at hotel</option>
                      <option>Advance percent</option>
                      <option>Registration fee</option>
                      <option>Full online</option>
                    </select>
                  </label>
                  {doc.booking_payment_mode === "Advance percent" && (
                    <label className="block max-w-xs">
                      <span className="mb-1 block text-sm font-medium text-zinc-600">
                        Advance percentage
                      </span>
                      <input
                        type="number" min={0} max={100} className={inputCls}
                        value={doc.advance_percent ?? ""}
                        onChange={(e) => updateField("advance_percent", Number(e.target.value))}
                      />
                      <span className="mt-1 block text-xs text-zinc-400">
                        Collected upfront; the rest is paid at the hotel.
                      </span>
                    </label>
                  )}
                  {doc.booking_payment_mode === "Registration fee" && (
                    <label className="block max-w-xs">
                      <span className="mb-1 block text-sm font-medium text-zinc-600">
                        Registration fee (₹)
                      </span>
                      <input
                        type="number" min={0} className={inputCls}
                        value={doc.registration_fee ?? ""}
                        onChange={(e) => updateField("registration_fee", Number(e.target.value))}
                      />
                    </label>
                  )}
                  <div className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800">
                    Online collection uses whatever payment gateway is configured
                    in the Payments app (Razorpay, Stripe, etc.). Until a gateway
                    is connected, the advance is recorded as due and settled at
                    the desk.
                  </div>
                </div>
              )}

              {section === "policies" && (
                <div className="space-y-4">
                  <div className="grid gap-4 sm:grid-cols-2">
                    <label className="block">
                      <span className="mb-1 block text-sm font-medium text-zinc-600">Check-in Time</span>
                      <input
                        className={inputCls}
                        type="time"
                        value={doc.checkin_time ?? "14:00"}
                        onChange={(e) => updateField("checkin_time", e.target.value)}
                      />
                    </label>
                    <label className="block">
                      <span className="mb-1 block text-sm font-medium text-zinc-600">Check-out Time</span>
                      <input
                        className={inputCls}
                        type="time"
                        value={doc.checkout_time ?? "11:00"}
                        onChange={(e) => updateField("checkout_time", e.target.value)}
                      />
                    </label>
                  </div>

                  <div className="grid gap-4 sm:grid-cols-2 border-t border-zinc-100 pt-4">
                    <label className="block">
                      <span className="mb-1 block text-sm font-medium text-zinc-600">Free cancellation window (days before arrival)</span>
                      <input
                        className={inputCls}
                        type="number"
                        value={doc.free_cancel_days ?? 0}
                        onChange={(e) => updateField("free_cancel_days", Number(e.target.value))}
                      />
                    </label>
                    <label className="block">
                      <span className="mb-1 block text-sm font-medium text-zinc-600">Late cancellation fee basis</span>
                      <select
                        className={inputCls}
                        value={doc.cancellation_fee ?? "First Night"}
                        onChange={(e) => updateField("cancellation_fee", e.target.value)}
                      >
                        {["None", "First Night", "Full Stay"].map((o) => (
                          <option key={o} value={o}>
                            {o}
                          </option>
                        ))}
                      </select>
                    </label>
                  </div>

                  <div className="grid gap-4 sm:grid-cols-2">
                    <label className="block">
                      <span className="mb-1 block text-sm font-medium text-zinc-600">No-show charge basis</span>
                      <select
                        className={inputCls}
                        value={doc.no_show_charge ?? "First Night"}
                        onChange={(e) => updateField("no_show_charge", e.target.value)}
                      >
                        {["None", "First Night", "Full Stay"].map((o) => (
                          <option key={o} value={o}>
                            {o}
                          </option>
                        ))}
                      </select>
                    </label>
                    <label className="block">
                      <span className="mb-1 block text-sm font-medium text-zinc-600">Deposit expected (%)</span>
                      <input
                        className={inputCls}
                        type="number"
                        value={doc.deposit_pct ?? 0}
                        onChange={(e) => updateField("deposit_pct", Number(e.target.value))}
                      />
                    </label>
                  </div>

                  <div className="border-t border-zinc-100 pt-4 space-y-3">
                    <label className="block">
                      <span className="mb-1 block text-sm font-medium text-zinc-600">House Rules</span>
                      <textarea
                        rows={2}
                        className={inputCls}
                        placeholder="No loud music after 10 PM. Swimming pool requires proper swimwear."
                        value={doc.house_rules ?? ""}
                        onChange={(e) => updateField("house_rules", e.target.value)}
                      />
                    </label>
                    <label className="block">
                      <span className="mb-1 block text-sm font-medium text-zinc-600">Pets Policy</span>
                      <textarea
                        rows={2}
                        className={inputCls}
                        placeholder="Pets allowed on request. Charges may apply."
                        value={doc.pets_policy ?? ""}
                        onChange={(e) => updateField("pets_policy", e.target.value)}
                      />
                    </label>
                    <label className="block">
                      <span className="mb-1 block text-sm font-medium text-zinc-600">Children & Occupancy Policy</span>
                      <textarea
                        rows={2}
                        className={inputCls}
                        placeholder="Children under 5 stay free using existing beds."
                        value={doc.children_policy ?? ""}
                        onChange={(e) => updateField("children_policy", e.target.value)}
                      />
                    </label>
                    <label className="block">
                      <span className="mb-1 block text-sm font-medium text-zinc-600">Extra Bed Policy</span>
                      <textarea
                        rows={2}
                        className={inputCls}
                        placeholder="Extra bed available for select rooms at ₹1,000 per night."
                        value={doc.extra_bed_policy ?? ""}
                        onChange={(e) => updateField("extra_bed_policy", e.target.value)}
                      />
                    </label>
                  </div>
                </div>
              )}

              {section === "faq" && (
                <div className="space-y-4">
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-semibold text-zinc-700">FAQ Directory</span>
                    <Button
                      variant="outline"
                      onClick={() => {
                        const faqs = [...(doc.faqs || []), { question: "", answer: "" }]
                        updateField("faqs", faqs)
                      }}
                    >
                      <Plus className="size-4" /> Add FAQ
                    </Button>
                  </div>

                  <div className="space-y-4">
                    {(doc.faqs || []).map((faq: any, index: number) => (
                      <div key={index} className="p-4 border border-zinc-200 rounded-xl space-y-3 relative bg-zinc-50/30">
                        <button
                          onClick={() => {
                            const faqs = (doc.faqs || []).filter((_: any, idx: number) => idx !== index)
                            updateField("faqs", faqs)
                          }}
                          className="absolute top-2 right-2 rounded-lg p-1.5 text-rose-500 hover:bg-rose-50"
                          aria-label="Delete FAQ"
                        >
                          <Trash2 className="size-4" />
                        </button>
                        <label className="block pr-8">
                          <span className="mb-1 block text-xs font-semibold text-zinc-500 uppercase tracking-wider">Question</span>
                          <input
                            className={inputCls}
                            placeholder="What is check-in time?"
                            value={faq.question ?? ""}
                            onChange={(e) => {
                              const faqs = (doc.faqs || []).map((f: any, idx: number) =>
                                idx === index ? { ...f, question: e.target.value } : f
                              )
                              updateField("faqs", faqs)
                            }}
                          />
                        </label>
                        <label className="block">
                          <span className="mb-1 block text-xs font-semibold text-zinc-500 uppercase tracking-wider">Answer</span>
                          <textarea
                            rows={2}
                            className={inputCls}
                            placeholder="Standard check-in is at 2:00 PM, and checkout is 11:00 AM."
                            value={faq.answer ?? ""}
                            onChange={(e) => {
                              const faqs = (doc.faqs || []).map((f: any, idx: number) =>
                                idx === index ? { ...f, answer: e.target.value } : f
                              )
                              updateField("faqs", faqs)
                            }}
                          />
                        </label>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {section === "seo" && (
                <div className="space-y-4">
                  <label className="block">
                    <span className="mb-1 block text-sm font-medium text-zinc-600">Meta Title</span>
                    <input
                      className={inputCls}
                      placeholder="Grand Kamra Palace | Luxury Stay in Udaipur"
                      value={doc.meta_title ?? ""}
                      onChange={(e) => updateField("meta_title", e.target.value)}
                    />
                  </label>

                  <label className="block">
                    <span className="mb-1 block text-sm font-medium text-zinc-600">Meta Description</span>
                    <textarea
                      rows={3}
                      className={inputCls}
                      placeholder="Book directly for best rates at Grand Kamra Palace, Udaipur. Located right on Lake Pichola with luxury amenities, rooftop pool, and five-star dine-in options."
                      value={doc.meta_description ?? ""}
                      onChange={(e) => updateField("meta_description", e.target.value)}
                    />
                  </label>

                  <div className="grid gap-4 sm:grid-cols-2">
                    <ImageField
                      label="OG image (share card)"
                      hint="Exactly 1200×630px · JPG or PNG. What WhatsApp, Google and social previews show."
                      value={doc.og_image ?? ""}
                      onChange={(v) => updateField("og_image", v)}
                    />
                    <label className="block">
                      <span className="mb-1 block text-sm font-medium text-zinc-600">Page Slug Prefix</span>
                      <input
                        className={inputCls}
                        placeholder="e.g. grand-kamra-palace"
                        value={doc.page_slug ?? ""}
                        onChange={(e) => updateField("page_slug", e.target.value)}
                      />
                    </label>
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </div>

      {/* Save bar */}
      <Card>
        <CardContent className="flex items-center gap-4 py-4 justify-end">
          {state === "saved" && (
            <span className="text-sm font-medium text-emerald-600">Settings Saved Successfully</span>
          )}
          {state !== "idle" && state !== "saved" && (
            <span className="text-sm font-medium text-rose-600">{state}</span>
          )}
          <Button disabled={busy} onClick={save} className="px-6 py-2">
            {busy ? "Saving…" : "Save Changes"}
          </Button>
        </CardContent>
      </Card>
    </div>
  )
}
