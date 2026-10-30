import { readFileSync, existsSync } from "node:fs"
import { fileURLToPath } from "node:url"
import { dirname, join } from "node:path"
import { defineConfig } from "vitepress"

const here = dirname(fileURLToPath(import.meta.url))
const docsRoot = join(here, "..")

type DocVersion = { version: string; label: string; path: string }

const versionsFile = JSON.parse(
  readFileSync(join(docsRoot, "versions.json"), "utf8"),
) as { latest: string; versions: DocVersion[] }

const overridePath = join(here, "version.override.json")
const override = existsSync(overridePath)
  ? (JSON.parse(readFileSync(overridePath, "utf8")) as {
      base?: string
      current?: string
      outDir?: string
    })
  : {}

const base = process.env.DOCS_BASE || override.base || "/docs/"
const docCurrent =
  process.env.DOCS_CURRENT || override.current || versionsFile.latest
const outDir = process.env.DOCS_OUT_DIR || override.outDir || ".vitepress/dist"


// Staff guides that have Spanish and Arabic versions. Every other page is
// English only, and the translated sidebars link to it in English.
const TRANSLATED = new Set([
  "", "why-kamra", "how-it-works", "features", "user-guide", "faq",
  "settings", "reports", "rooms", "front-desk", "reservations", "operations",
  "billing", "night-audit", "revenue", "housekeeping", "fnb", "banquets",
  "booking-engine",
])

type Lang = "en" | "es" | "ar"
// [English, Spanish, Arabic]
const L = (en: string, es: string, ar: string) => ({ en, es, ar })

const SIDEBAR: { text: ReturnType<typeof L>; collapsed?: boolean; items: [ReturnType<typeof L>, string][] }[] = [
  {
    text: L("Getting started", "Primeros pasos", "البداية"),
    items: [
      [L("Introduction", "Introducción", "مقدمة"), ""],
      [L("Why Kamra", "Por qué Kamra", "لماذا Kamra"), "why-kamra"],
      [L("How Kamra works", "Cómo funciona Kamra", "كيف يعمل Kamra"), "how-it-works"],
      [L("Features at a glance", "Funciones de un vistazo", "الميزات بنظرة سريعة"), "features"],
      [L("What's new", "Novedades", "الجديد"), "releases"],
      [L("Video course", "Curso en video", "دورة الفيديو"), "video-course"],
      [L("Try the live demo", "Pruebe la demo", "جرّب العرض الحي"), "demo"],
      [L("Quickstart (Docker)", "Inicio rápido (Docker)", "البدء السريع (Docker)"), "quickstart"],
      [L("Go-live checklist", "Lista para la puesta en marcha", "قائمة بدء التشغيل"), "go-live"],
      [L("Go-live runbook (one night)", "Guía de puesta en marcha (una noche)", "دليل بدء التشغيل (ليلة واحدة)"), "go-live-runbook"],
    ],
  },
  {
    text: L("Run your hotel", "Gestione su hotel", "أدِر فندقك"),
    items: [
      [L("Guides by role", "Guías por rol", "أدلة حسب الدور"), "user-guide"],
      [L("Front desk", "Recepción", "مكتب الاستقبال"), "front-desk"],
      [L("Reservations", "Reservas", "الحجوزات"), "reservations"],
      [L("Billing & cashier", "Facturación y caja", "الفوترة والصندوق"), "billing"],
      [L("Night audit", "Auditoría nocturna", "التدقيق الليلي"), "night-audit"],
      [L("Reports & dashboards", "Informes y paneles", "التقارير ولوحات المعلومات"), "reports"],
      [L("Rooms", "Habitaciones", "الغرف"), "rooms"],
      [L("Housekeeping", "Limpieza", "التدبير المنزلي"), "housekeeping"],
      [L("Guest requests", "Solicitudes de huéspedes", "طلبات النزلاء"), "operations"],
      [L("F&B: POS & kitchen", "Alimentos y bebidas: POS y cocina", "الأغذية والمشروبات: نقطة البيع والمطبخ"), "fnb"],
      [L("Banquets & groups", "Banquetes y grupos", "الحفلات والمجموعات"), "banquets"],
      [L("Revenue & rates", "Ingresos y tarifas", "الإيرادات والأسعار"), "revenue"],
      [L("Booking engine", "Motor de reservas", "محرك الحجز"), "booking-engine"],
      [L("Settings & staff", "Configuración y personal", "الإعدادات والموظفون"), "settings"],
      [L("Roles and access", "Roles y acceso", "الأدوار والوصول"), "roles-and-access"],
    ],
  },
  {
    text: L("Connect", "Conectar", "الربط"),
    items: [
      [L("All integrations", "Todas las integraciones", "كل التكاملات"), "integrations"],
      [L("Country setup & e-invoicing", "Configuración por país y factura electrónica", "إعداد الدولة والفوترة الإلكترونية"), "country-setup"],
      [L("Write a country pack", "Escribir un country pack", "كتابة حزمة دولة"), "write-a-country-pack"],
      [L("WhatsApp on your number", "WhatsApp en su número", "WhatsApp على رقمك"), "whatsapp"],
      [L("Channel manager (OTA sync)", "Channel manager (sincronización OTA)", "مدير القنوات (مزامنة OTA)"), "channel-manager"],
      [L("Connect your AI (MCP)", "Conecte su IA (MCP)", "اربط الذكاء الاصطناعي (MCP)"), "ai-and-mcp"],
    ],
  },
  {
    text: L("Self-hosting", "Alojamiento propio", "الاستضافة الذاتية"),
    collapsed: true,
    items: [
      [L("Overview & requirements", "Resumen y requisitos", "نظرة عامة والمتطلبات"), "self-hosting/"],
      [L("Hostinger", "Hostinger", "Hostinger"), "self-hosting/hostinger"],
      [L("DigitalOcean", "DigitalOcean", "DigitalOcean"), "self-hosting/digitalocean"],
      [L("Linode (Akamai)", "Linode (Akamai)", "Linode (Akamai)"), "self-hosting/linode"],
      [L("AWS", "AWS", "AWS"), "self-hosting/aws"],
      [L("AWS / Azure / GCP marketplaces", "Marketplaces de AWS / Azure / GCP", "أسواق AWS / Azure / GCP"), "self-hosting/marketplace/hyperscalers"],
      [L("Install with bench", "Instalar con bench", "التثبيت باستخدام bench"), "self-hosting/bench"],
      [L("Frappe Cloud marketplace", "Marketplace de Frappe Cloud", "سوق Frappe Cloud"), "self-hosting/frappe-cloud"],
      [L("ERPNext & Frappe HR", "ERPNext y Frappe HR", "ERPNext و Frappe HR"), "self-hosting/erpnext-hr"],
      [L("Email (SMTP) setup", "Configurar el correo (SMTP)", "إعداد البريد (SMTP)"), "self-hosting/email"],
    ],
  },
  {
    text: L("MCP & API", "MCP y API", "MCP و API"),
    items: [
      [L("Connect your AI (MCP)", "Conecte su IA (MCP)", "اربط الذكاء الاصطناعي (MCP)"), "ai-and-mcp"],
      [L("MCP tool reference", "Referencia de herramientas MCP", "مرجع أدوات MCP"), "mcp-tools"],
      [L("Shortcuts hub", "Accesos directos", "مركز الاختصارات"), "developers"],
      [L("REST API basics", "Conceptos básicos de la API REST", "أساسيات REST API"), "api"],
      [L("REST API reference", "Referencia de la API REST", "مرجع REST API"), "api-reference"],
    ],
  },
  {
    text: L("Reference", "Referencia", "مرجع"),
    collapsed: true,
    items: [
      [L("FAQ", "Preguntas frecuentes", "الأسئلة الشائعة"), "faq"],
      [L("Contributors", "Colaboradores", "المساهمون"), "contributors"],
    ],
  },
]

const link = (lang: Lang, page: string) =>
  lang !== "en" && TRANSLATED.has(page) ? `/${lang}/${page}` : `/${page}`

const sidebarFor = (lang: Lang) => [
  ...SIDEBAR.map((g) => ({
    text: g.text[lang],
    ...(g.collapsed ? { collapsed: true } : {}),
    items: g.items.map(([t, page]) => ({ text: t[lang], link: link(lang, page) })),
  })),
]

const navFor = (lang: Lang) => [
  {
    text: L("MCP & API", "MCP y API", "MCP و API")[lang],
    items: [
      { text: L("Connect your AI (MCP)", "Conecte su IA (MCP)", "اربط الذكاء الاصطناعي (MCP)")[lang], link: "/ai-and-mcp" },
      { text: L("MCP tool reference", "Referencia de herramientas MCP", "مرجع أدوات MCP")[lang], link: "/mcp-tools" },
      { text: L("Developer shortcuts", "Accesos para desarrolladores", "اختصارات المطورين")[lang], link: "/developers" },
      { text: L("REST API basics", "Conceptos básicos de la API REST", "أساسيات REST API")[lang], link: "/api" },
      { text: L("REST API reference", "Referencia de la API REST", "مرجع REST API")[lang], link: "/api-reference" },
      {
        text: "Postman collection ↓",
        link: "https://kamrapms.com/docs/kamra.postman_collection.json",
        target: "_blank",
      },
    ],
  },
  { text: L("Website", "Sitio web", "الموقع")[lang], link: "https://kamrapms.com" },
  { text: L("Live demo", "Demo", "العرض الحي")[lang], link: "https://demo.kamrapms.com" },
  { text: "GitHub", link: "https://github.com/Kamra-PMS/kamra-pms" },
]

// what VitePress's own theme says, per language
const themeWords = (lang: Exclude<Lang, "en">) => {
  const es = lang === "es"
  return {
    nav: navFor(lang),
    sidebar: sidebarFor(lang),
    outline: { level: [2, 3] as [number, number], label: es ? "En esta página" : "في هذه الصفحة" },
    editLink: {
      pattern: "https://github.com/Kamra-PMS/kamra-pms/edit/develop/docs-site/:path",
      text: es ? "Sugerir un cambio en esta página" : "اقترح تعديلاً على هذه الصفحة",
    },
    docFooter: es ? { prev: "Anterior", next: "Siguiente" } : { prev: "السابق", next: "التالي" },
    lastUpdatedText: es ? "Actualizado" : "آخر تحديث",
    returnToTopLabel: es ? "Volver arriba" : "العودة إلى الأعلى",
    sidebarMenuLabel: es ? "Menú" : "القائمة",
    darkModeSwitchLabel: es ? "Apariencia" : "المظهر",
    langMenuLabel: es ? "Idioma" : "اللغة",
    footer: {
      message: es
        ? `Código abierto (AGPL-3.0) · documentación de Kamra v${docCurrent} · todas las funciones incluidas, siempre.`
        : `مفتوح المصدر (AGPL-3.0) · توثيق Kamra الإصدار ${docCurrent} · كل الميزات مشمولة دائماً.`,
      copyright: "Kamra PMS · hello@kamrapms.com",
    },
  }
}

export default defineConfig({
  title: "Kamra Docs",
  description:
    "Kamra docs - the open-source hotel PMS agents can run. Governed MCP tools, deterministic pricing, REST and Postman. Install, self-host, connect Claude.",
  base,
  outDir,
  cleanUrls: true,
  // the writing guide for contributors is not a published page
  srcExclude: ["STYLE.md", "README.md", "archives/**"],
  // local bench URLs in install guides are examples, not site pages
  ignoreDeadLinks: [
    /^https?:\/\/localhost/,
    /^https?:\/\/127\.0\.0\.1/,
    /^https?:\/\/kamra\.localhost/,
  ],
  locales: {
    root: { label: "English", lang: "en" },
    es: { label: "Español", lang: "es", link: "/es/", themeConfig: themeWords("es") },
    ar: { label: "العربية", lang: "ar", dir: "rtl", link: "/ar/", themeConfig: themeWords("ar") },
  },
  head: [["link", { rel: "icon", type: "image/svg+xml", href: `${base}kamra-mark.svg` }]],
  themeConfig: {
    logo: {
      light: "/kamra-horizontal.svg",
      dark: "/kamra-horizontal-white.svg",
      alt: "Kamra PMS",
      height: 28,
    },
    siteTitle: false,
    nav: navFor("en"),
    sidebar: sidebarFor("en"),
    search: {
      provider: "local",
      options: {
        locales: {
          es: { translations: { button: { buttonText: "Buscar", buttonAriaLabel: "Buscar" },
            modal: { noResultsText: "Sin resultados para", resetButtonTitle: "Borrar",
              footer: { selectText: "elegir", navigateText: "moverse", closeText: "cerrar" } } } },
          ar: { translations: { button: { buttonText: "بحث", buttonAriaLabel: "بحث" },
            modal: { noResultsText: "لا نتائج لـ", resetButtonTitle: "مسح",
              footer: { selectText: "اختيار", navigateText: "تنقّل", closeText: "إغلاق" } } } },
        },
      },
    },
    outline: { level: [2, 3], label: "On this page" },
    editLink: {
      pattern: "https://github.com/Kamra-PMS/kamra-pms/edit/develop/docs-site/:path",
      text: "Suggest a change to this page",
    },
    socialLinks: [
      { icon: "github", link: "https://github.com/Kamra-PMS/kamra-pms" },
    ],
    footer: {
      message: `Open source (AGPL-3.0) · docs for Kamra v${docCurrent} · every feature included, always.`,
      copyright: "Kamra PMS · hello@kamrapms.com",
    },
    // consumed by the version switcher / outdated banner (custom theme fields)
    ...({
      docVersions: versionsFile.versions,
      docLatest: versionsFile.latest,
      docCurrent,
    } as Record<string, unknown>),
  },
})
