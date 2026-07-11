import { useEffect, useState } from "react"
import { getLang, type Lang } from "./dir"

/** Arabic strings, keyed by the English source. Grows incrementally - any
 * key without a translation falls back to English, so the app never breaks
 * as coverage expands. Covers the app/nav labels and common actions first. */
const AR: Record<string, string> = {
  // apps
  "Front Desk": "الاستقبال",
  "Housekeeping": "التدبير المنزلي",
  "Operations": "العمليات",
  "F&B": "المأكولات والمشروبات",
  "Events": "الفعاليات",
  "Revenue": "الإيرادات",
  "Finance": "المالية",
  "Booking Engine": "محرك الحجز",
  "Admin": "الإدارة",
  // front desk nav
  "Today": "اليوم",
  "Dashboard": "لوحة التحكم",
  "Copilot": "المساعد",
  "Reservations": "الحجوزات",
  "Central Reservations": "الحجوزات المركزية",
  "Tape Chart": "مخطط الغرف",
  "Calendar": "التقويم",
  "Guests": "الضيوف",
  "Room Blocks": "حجب الغرف",
  // housekeeping / ops
  "Room Board": "لوحة الغرف",
  "Lost & Found": "المفقودات",
  "Guest Requests": "طلبات الضيوف",
  "SLA Report": "تقرير مستوى الخدمة",
  "Shifts": "الورديات",
  // f&b
  "Restaurant POS": "نقطة بيع المطعم",
  "Kitchen Display": "شاشة المطبخ",
  "Menu": "القائمة",
  "Outlets": "المنافذ",
  // finance / revenue
  "Billing": "الفوترة",
  "Reports": "التقارير",
  "Rate Plans": "خطط الأسعار",
  "Seasons": "المواسم",
  "Vouchers": "القسائم",
  "Companies": "الشركات",
  // common actions
  "Search": "بحث",
  "Save": "حفظ",
  "Cancel": "إلغاء",
  "Confirm": "تأكيد",
  "Check in": "تسجيل الوصول",
  "Check out": "تسجيل المغادرة",
  "Arrivals": "الوصول",
  "Departures": "المغادرة",
  "In house": "داخل الفندق",
  "Occupancy": "الإشغال",
  "Revenue today": "إيرادات اليوم",
  "New booking": "حجز جديد",
  "Sign out": "تسجيل الخروج",
}

const DICT: Record<Lang, Record<string, string>> = { en: {}, ar: AR }

/** Translate an English string for the current language (falls back to it). */
export function t(s: string): string {
  return DICT[getLang()][s] ?? s
}

/** Subscribe a component to the language: re-renders on change, returns a
 * bound translator. */
export function useT() {
  const [lang, setL] = useState<Lang>(getLang())
  useEffect(() => {
    const on = () => setL(getLang())
    window.addEventListener("kamra:lang", on)
    return () => window.removeEventListener("kamra:lang", on)
  }, [])
  return { lang, t: (s: string) => DICT[lang][s] ?? s }
}
