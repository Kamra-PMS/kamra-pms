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
  "Kamra Agent": "وكيل كامرا",
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
  "Laundry": "الغسيل",
  "Phone App": "تطبيق الهاتف",
  "WhatsApp": "واتساب",
  "Channels": "القنوات",
  "Banquets": "المآدب",
  "Month Availability": "توفر الشهر",
  "Function Diary": "يومية المناسبات",
  "Registers": "السجلات",
  "Menus & Services": "القوائم والخدمات",
  "All Functions": "كل المناسبات",
  "Revenue Reports": "تقارير الإيرادات",
  "Channel Manager": "مدير القنوات",
  "OTA Room Mappings": "ربط غرف OTA",
  "Guardrails": "حدود الأسعار",
  "Meal Plans": "خطط الوجبات",
  "Travel Agents": "وكلاء السفر",
  "Accounting Export": "تصدير المحاسبة",
  "Hotel Profile": "ملف الفندق",
  "Amenities": "المرافق",
  "Photos": "الصور",
  "Policies": "السياسات",
  "Payments": "المدفوعات",
  "FAQ": "الأسئلة الشائعة",
  "SEO": "تحسين محركات البحث",
  "Settings": "الإعدادات",
  "Rooms": "الغرف",
  "Room Types": "أنواع الغرف",
  "Activity Log": "سجل النشاط",
  "Marketplace": "السوق",
  "Developers": "المطورون",
  "New Property": "عقار جديد",
  "Manage Users": "إدارة المستخدمين",
  "Frappe Desk": "مكتب فراب",
  "Kitchen Inventory": "مخزون المطبخ",
  "Banquets & Groups": "المآدب والمجموعات",
  "Group bookings": "حجوزات المجموعات",
  "Halls & Venues": "القاعات والأماكن",
  "Group": "مجموعة",
  "New booking": "حجز جديد",
  "Sign out": "تسجيل الخروج",
  "About this install": "حول هذا التثبيت",
  "Email": "البريد الإلكتروني",
  "Email or username": "البريد الإلكتروني أو اسم المستخدم",
  "Password": "كلمة المرور",
  "Sign in": "تسجيل الدخول",
  "Signing in...": "جارٍ تسجيل الدخول...",
  "Wrong email or password.": "البريد الإلكتروني أو كلمة المرور غير صحيحة.",
  "Wrong email, username, or password.": "البريد الإلكتروني أو اسم المستخدم أو كلمة المرور غير صحيحة.",
  "New": "جديد",
  "Delete": "حذف",
  "Export": "تصدير",
  "Columns": "الأعمدة",
  "Search…": "بحث…",
  "Saving…": "جارٍ الحفظ…",
  "Saved": "تم الحفظ",
  "Clear": "مسح",
  "Done": "تم",
  "Property": "العقار",
  "Front desk hours": "ساعات الاستقبال",
  "Tax": "الضريبة",
  "Guest privacy": "خصوصية الضيف",
  "Booking page": "صفحة الحجز",
  "AI assistant (bring your own key)": "مساعد الذكاء الاصطناعي (مفتاحك الخاص)",
  "Revenue controls": "ضوابط الإيرادات",
  "Laundry rate card": "بطاقة أسعار الغسيل",
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
