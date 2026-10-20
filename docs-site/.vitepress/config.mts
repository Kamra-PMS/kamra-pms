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
  head: [["link", { rel: "icon", type: "image/svg+xml", href: `${base}kamra-mark.svg` }]],
  themeConfig: {
    logo: {
      light: "/kamra-horizontal.svg",
      dark: "/kamra-horizontal-white.svg",
      alt: "Kamra PMS",
      height: 28,
    },
    siteTitle: false,
    nav: [
      {
        text: "MCP & API",
        items: [
          { text: "Connect your AI (MCP)", link: "/ai-and-mcp" },
          { text: "MCP tool reference", link: "/mcp-tools" },
          { text: "Developer shortcuts", link: "/developers" },
          { text: "REST API basics", link: "/api" },
          { text: "REST API reference", link: "/api-reference" },
          {
            text: "Postman collection ↓",
            link: "https://kamrapms.com/docs/kamra.postman_collection.json",
            target: "_blank",
          },
        ],
      },
      { text: "Website", link: "https://kamrapms.com" },
      { text: "Live demo", link: "https://demo.kamrapms.com" },
      { text: "GitHub", link: "https://github.com/Kamra-PMS/kamra-pms" },
    ],
    search: { provider: "local" },
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
    sidebar: [
      {
        text: "Getting started",
        items: [
          { text: "Introduction", link: "/" },
          { text: "Why Kamra", link: "/why-kamra" },
          { text: "How Kamra works", link: "/how-it-works" },
          { text: "Features at a glance", link: "/features" },
          { text: "What's new", link: "/releases" },
          { text: "Try the live demo", link: "/demo" },
          { text: "Quickstart (Docker)", link: "/quickstart" },
          { text: "Go-live checklist", link: "/go-live" },
          { text: "Go-live runbook (one night)", link: "/go-live-runbook" },
        ],
      },
      {
        text: "Run your hotel",
        items: [
          { text: "Guides by role", link: "/user-guide" },
          { text: "Front desk", link: "/front-desk" },
          { text: "Reservations", link: "/reservations" },
          { text: "Billing & cashier", link: "/billing" },
          { text: "Night audit", link: "/night-audit" },
          { text: "Reports & dashboards", link: "/reports" },
          { text: "Rooms", link: "/rooms" },
          { text: "Housekeeping", link: "/housekeeping" },
          { text: "Guest requests", link: "/operations" },
          { text: "F&B: POS & kitchen", link: "/fnb" },
          { text: "Banquets & groups", link: "/banquets" },
          { text: "Revenue & rates", link: "/revenue" },
          { text: "Booking engine", link: "/booking-engine" },
          { text: "Settings & staff", link: "/settings" },
        ],
      },
      {
        text: "Connect",
        items: [
          { text: "All integrations", link: "/integrations" },
          { text: "Country setup & e-invoicing", link: "/country-setup" },
          { text: "WhatsApp on your number", link: "/whatsapp" },
          { text: "Channel manager (OTA sync)", link: "/channel-manager" },
          { text: "Connect your AI (MCP)", link: "/ai-and-mcp" },
        ],
      },
      {
        text: "Self-hosting",
        collapsed: true,
        items: [
          { text: "Overview & requirements", link: "/self-hosting/" },
          { text: "Hostinger", link: "/self-hosting/hostinger" },
          { text: "DigitalOcean", link: "/self-hosting/digitalocean" },
          { text: "Linode (Akamai)", link: "/self-hosting/linode" },
          { text: "AWS", link: "/self-hosting/aws" },
          { text: "AWS / Azure / GCP marketplaces", link: "/self-hosting/marketplace/hyperscalers" },
          { text: "Install with bench", link: "/self-hosting/bench" },
          { text: "Frappe Cloud marketplace", link: "/self-hosting/frappe-cloud" },
          { text: "ERPNext & Frappe HR", link: "/self-hosting/erpnext-hr" },
          { text: "Email (SMTP) setup", link: "/self-hosting/email" },
        ],
      },
      {
        text: "MCP & API",
        items: [
          { text: "Connect your AI (MCP)", link: "/ai-and-mcp" },
          { text: "MCP tool reference", link: "/mcp-tools" },
          { text: "Shortcuts hub", link: "/developers" },
          { text: "REST API basics", link: "/api" },
          { text: "REST API reference", link: "/api-reference" },
          {
            text: "Postman collection ↓",
            link: "https://kamrapms.com/docs/kamra.postman_collection.json",
          },
        ],
      },
      {
        text: "Reference",
        collapsed: true,
        items: [
          { text: "FAQ", link: "/faq" },
          { text: "Contributors", link: "/contributors" },
        ],
      },
    ],
    // consumed by the version switcher / outdated banner (custom theme fields)
    ...({
      docVersions: versionsFile.versions,
      docLatest: versionsFile.latest,
      docCurrent,
    } as Record<string, unknown>),
  },
})
