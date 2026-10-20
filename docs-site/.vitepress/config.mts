import { defineConfig } from "vitepress"

export default defineConfig({
  title: "Kamra Docs",
  description:
    "Documentation for Kamra, the open-source AI-native hotel PMS - install, self-host, connect your AI over MCP, and run your property.",
  base: "/docs/",
  cleanUrls: true,
  // the writing guide for contributors is not a published page
  srcExclude: ["STYLE.md", "README.md"],
  head: [["link", { rel: "icon", type: "image/svg+xml", href: "/docs/kamra-mark.svg" }]],
  themeConfig: {
    logo: { src: "/kamra-horizontal.svg", height: 28 },
    siteTitle: false,
    nav: [
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
      message: "Open source (AGPL-3.0) · every feature included, always.",
      copyright: "Kamra PMS · hello@kamrapms.com",
    },
    sidebar: [
      {
        text: "Getting started",
        items: [
          { text: "Introduction", link: "/" },
          { text: "Features at a glance", link: "/features" },
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
          { text: "Housekeeping", link: "/housekeeping" },
          { text: "Guest requests", link: "/operations" },
          { text: "F&B — POS & kitchen", link: "/fnb" },
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
        text: "Reference",
        collapsed: true,
        items: [
          { text: "MCP tool reference", link: "/mcp-tools" },
          { text: "REST API basics", link: "/api" },
          { text: "REST API reference", link: "/api-reference" },
          { text: "FAQ", link: "/faq" },
          { text: "Contributors", link: "/contributors" },
        ],
      },
    ],
  },
})
