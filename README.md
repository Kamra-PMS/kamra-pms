<p align="center">
  <img src="branding/png/kamra-mark-512.png" width="96" alt="Kamra, free open-source hotel PMS" />
</p>

<h1 align="center">Kamra PMS: the free, open-source hotel PMS</h1>

<p align="center">
  <b>Stop renting your hotel software.</b><br/>
  A complete property management system for hotels, resorts, villas and short-term rentals.<br/>
  No licence fee, no per-room pricing, no renewal hikes. You own the software and the data, for good.<br/>
  And it is ready for AI: Claude or ChatGPT can work the front desk under the same rules as your staff.
</p>

<p align="center">
  <a href="https://demo.kamrapms.com"><img src="https://img.shields.io/badge/demo-live-1E7B4F?style=flat-square" alt="Live demo" /></a>
  <a href="https://github.com/Kamra-PMS/kamra-pms/releases/latest"><img src="https://img.shields.io/github/v/release/Kamra-PMS/kamra-pms?style=flat-square&label=release" alt="Latest release" /></a>
  <a href="license.txt"><img src="https://img.shields.io/badge/license-Apache--2.0-blue?style=flat-square" alt="Apache-2.0" /></a>
  <img src="https://img.shields.io/badge/licence%20fee-%240%20forever-1E7B4F?style=flat-square" alt="Licence fee: $0 forever" />
  <a href="https://cloud.frappe.io/marketplace/apps/kamra"><img src="https://img.shields.io/badge/Frappe%20Cloud-Marketplace-ed8936?style=flat-square" alt="Frappe Cloud Marketplace" /></a>
  <a href="https://github.com/Kamra-PMS/kamra-pms/stargazers"><img src="https://img.shields.io/github/stars/Kamra-PMS/kamra-pms?style=flat-square" alt="GitHub stars" /></a>
</p>

<p align="center">
  <a href="https://demo.kamrapms.com"><b>Try the live demo</b></a> ·
  <a href="#install"><b>Install free</b></a> ·
  <a href="https://kamrapms.com/compare/"><b>Compare PMS</b></a> ·
  <a href="https://kamrapms.com/docs/"><b>Docs</b></a> ·
  <a href="https://www.youtube.com/@KamraPMS"><b>Videos</b></a>
</p>

![Kamra's Today screen: arrivals, departures, KPIs, the room board and in-house guests](docs-site/public/img/front-desk/today.png)

---

## Why are you still paying for a PMS licence every year?

Most hotels pay their PMS vendor again every year, for the same software. The bill grows with every room you add and every module you switch on, it tends to go up at renewal, and at the end of it you still own nothing. Want your own data out, an API for a new tool, or AI on the front desk? That is often another fee, another quote, or "on the roadmap".

A PMS is the system your whole hotel runs on. It should belong to the hotel.

Kamra is that PMS. It is open source under Apache-2.0, so every feature is in the free app: no editions, no locked modules, no per-room or per-user fees. You can host it yourself, on Frappe Cloud, or let us host it for you. If you ever leave, the code and the data leave with you.

| | Typical licensed PMS | Kamra |
|---|---|---|
| **Licence** | Paid every year, again and again | **0**, forever |
| **Pricing grows with** | Rooms, users, properties, modules | Nothing. 10 rooms or 500, same licence: free |
| **Renewal** | The vendor sets the new price | Nothing to renew |
| **Your data** | On the vendor's servers; export may be limited | Your database, your server, export any table |
| **Integrations and API** | Often extra, or partner-only | 560+ REST endpoints, all included |
| **AI** | A chatbot add-on, or a roadmap slide | Built-in assistant and a governed MCP layer for Claude and ChatGPT today |
| **If the vendor changes course** | You migrate on their timeline | You keep running the code you have, and anyone can support it |

**What does cost money?** Being honest about it: a server to run on (your own, a small VPS, or Frappe Cloud), and, if you want them, setup, migration, training and support from us or a [partner](https://kamrapms.com/partners/). AI usage is billed by the AI provider you choose, with no markup from us. None of these is a licence, and you choose whether you need them. How we fund the project: [kamrapms.com/how-kamra-makes-money](https://kamrapms.com/how-kamra-makes-money/).

**Is open source safe for a hotel?** Your guest data sits on a server you control, not in a vendor's shared cloud. The code is public, so anyone can check it, and it is: every pull request runs Semgrep security rules and a large suite of hotel-flow checks (double booking, folio math, tax, property scope), and outside researchers have reported issues privately and had them fixed and credited (see [Security](#security)). Access is role-based per property, and every change by staff or AI is logged with who, what and why.

[![Star Kamra on GitHub](https://img.shields.io/badge/%E2%AD%90%20Star%20Kamra-help%20other%20hotels%20find%20it-1C3F38?style=for-the-badge)](https://github.com/Kamra-PMS/kamra-pms/stargazers)

---

## Switching from eZee, Cloudbeds, IDS, Opera or another PMS

- **Bring your bookings.** CSV import with ready presets for eZee and Cloudbeds exports, plus an auto mode for anything else. Preview first, then import.
- **Keep your channel manager.** Kamra connects to Channex.io, STAAH and AioSell, so Booking.com, Expedia, Airbnb and other OTAs keep flowing.
- **Go live with a checklist.** Opening balances, staff and roles, tax setup and a [go-live checklist](https://kamrapms.com/docs/go-live).
- **Get help if you want it.** Our [implementation service](https://kamrapms.com/implementation/) or a local [partner](https://kamrapms.com/partners/) can do migration, setup and training on a fixed quote.

Side-by-side with other systems: [Kamra vs Mews, Cloudbeds, Apaleo, OPERA, eZee](https://kamrapms.com/compare/).

---

## What Kamra does

Everything below is in the free, open-source app.

**Front desk**
- Today screen with arrivals, departures, in-house guests, balances due and a live room board.
- One-screen walk-ins, guided check-in with an ID card per guest, group check-in, and online self check-in by link.
- Tape chart and calendar: book from an empty cell, move rooms, extend or shorten a stay.
- Groups with a rooming list, group rate, deposit and quotation; central reservations across several properties.

**Housekeeping**
- Room Board for supervisors and a phone app (`/hk`) for floor staff: claim a room, start, finish with a photo.
- Tasks with deadlines and escalation, guest requests with an SLA report.
- Guest laundry from collection to folio, minibar posting, lost and found, shift handover.

**Billing and finance**
- Folios with a tax rate per line, split and routed billing (the company pays the room, the guest pays the bar), payment links and security deposits.
- Cashier tills, shift reports, petty cash and a currency desk; bills paid and shown in another currency.
- Night audit on one page: only what needs you, one Close button, and an audit pack with every table exportable to CSV; it also runs by itself at 03:00.
- Accounts receivable as a work queue: overdue and over-limit filters, aging, statements and month-end bills to many companies at once.
- Books check that says whether folios and ledgers agree, plus accounts payable, P&amp;L and balance sheet.

**Restaurant POS, F&amp;B and banquets**
- Restaurant POS with a table map, room charges to the folio, kitchen display and network kitchen printers.
- Kitchen stock and recipes that move when an order is sent.
- Banquets from enquiry to quotation, event order (BEO), receipts and close-out, with a venue diary.

**Revenue and reports**
- Room types, rate plans, seasons, meal plans, vouchers, negotiated company rates and rate guardrails.
- Manager flash, property and portfolio dashboards (occupancy, ADR, RevPAR), budget against actual.
- Custom report builder with save and email, and report packs per department.

**Booking engine and short-term rentals**
- Your own commission-free booking page at `/book` with live rates, add-ons, instant booking or request to book.
- Villas and holiday homes: a catalogue of units sold as rooms or the whole place, cleaning fees and refundable deposits.
- Channel manager adapters for Channex.io, STAAH and AioSell. Channex sends only the dates that changed.

**AI and MCP**
- Kamra Agent, the in-app assistant, with action cards to check in, collect or open a folio.
- 178 MCP tools for Claude, ChatGPT or any MCP client. See [Run your hotel with AI](#run-your-hotel-with-ai).

The staff UI is in English, German, Spanish, Arabic (right to left), Portuguese (Brazil), Indonesian, Filipino, Vietnamese, Swahili, Hindi, Tamil and Simplified Chinese. Module by module, with screenshots: [Features](https://kamrapms.com/docs/features).

---

## Run your hotel with AI

**Why "first":** [Kamra 1.0](https://github.com/Kamra-PMS/kamra-pms/releases/tag/v1.0.0) shipped on 5 July 2026 as open source, free, and MCP-driven. We know of no open-source PMS that shipped all three earlier. MCP (Model Context Protocol) is the open standard that lets an AI assistant use a system's tools, here with the same permissions as a member of staff.

![Kamra Agent: a reply with a stay card and Check out, Collect, Open folio and Waive deposit actions](docs-site/public/img/ai/agent-cards.png)

- **Kamra Agent** is built in and on by default. Bring your own key from OpenAI, Gemini, Groq, OpenRouter, Ollama, Azure or any OpenAI-compatible provider. No markup: requests go from your server to your provider.
- **MCP for Claude and ChatGPT.** Open **Kamra Agent → Connect your AI** and click **Connect Claude**, or add your site's `/mcp` URL as a connector in ChatGPT. Claude Code works too:

  ```bash
  claude mcp add --transport http kamra https://pms.yourhotel.com/mcp
  ```

- **One write path.** The desk, the REST API, Kamra Agent and MCP clients all call the same governed functions. Each call is checked against the person's roles and property, and every change lands in the Activity Log with who, what and why.
- **Prices always come from Kamra.** Quotes, tax, deposits and availability are computed by Kamra's pricing code. An AI can ask for a quote or post a charge; it never invents a number, and rate guardrails refuse anything outside the floor and ceiling.
- **You decide who uses it.** A hotel admin gives each person MCP Read or MCP Manage, can make a property read-only for AI, or block single tools.

Guide: [Connect your AI (MCP)](https://kamrapms.com/docs/ai-and-mcp) · [MCP tool reference](https://kamrapms.com/docs/mcp-tools) · [REST API reference](https://kamrapms.com/docs/api-reference)

Kamra is built and maintained by [HeyKoala](https://heykoala.ai) (Koala AI Solutions Pvt Ltd). HeyKoala also offers hosted AI services for hotels, such as guest calls and WhatsApp; they are separate and optional, and Kamra works fully without them.

---

## Country packs: tax and compliance built in

The property's country picks its pack. The pack decides tax, invoice wording, ID types, payment modes, the privacy notice and any country-only integrations, so one country's integrations never show up in another.

| Country | Highlights |
|---|---|
| India | GST by tariff slab, CGST + SGST or IGST, GSTR-1 export, Razorpay and Cashfree payment links, Form C |
| Saudi Arabia | VAT 15%, municipality fee, ZATCA Phase 1 e-invoices with QR, Shomoos register |
| United Arab Emirates | VAT 5%, municipality fee, TRN on the tax invoice |
| Germany | 7% MwSt on lodging, USt-IdNr. on invoices |
| Malaysia | SST on rooms and F&amp;B, tourism tax note |
| Thailand | VAT 7%, service charge as its own line |
| Indonesia | Regional hotel tax (PB1 / PBJT) |
| Philippines | VAT 12%, TIN, peso. Senior citizen and PWD discount is calculated in the pack and posted by hand |
| Brazil | ISS, BRL, CNPJ / CPF, NFS-e reference |
| Nicaragua | IVA 15%, NIO |
| Anywhere else | One flat rate from property settings |

Rates are defaults you can change per property or room type. A new country is one Python module: [Write a country pack](https://kamrapms.com/docs/write-a-country-pack).

---

## Install

| Method | Best for | Guide |
|---|---|---|
| **Frappe Cloud Marketplace** | Managed hosting, no server to run (needs a private bench) | [Install via Frappe Cloud](https://kamrapms.com/docs/self-hosting/frappe-cloud) |
| **Docker on a VPS** | Hostinger, DigitalOcean, Linode, AWS or your own box | [Quickstart](https://kamrapms.com/docs/quickstart) |
| **Bench** | Teams already running Frappe or ERPNext | [Bench install](https://kamrapms.com/docs/self-hosting/bench) |

**Docker** (2 vCPU / 4 GB minimum, three prompts: domain, admin email, admin password):

```bash
curl -fsSL https://raw.githubusercontent.com/Kamra-PMS/kamra-pms/main/deploy/install.sh | bash
```

Cheapest path in India and South-East Asia: a Hostinger KVM 2 through the [Kamra referral link](https://www.hostinger.com/in?REFERRALCODE=kamrapms) (20% off, or coupon `KAMRAPMS`; it helps keep Kamra going). [Hostinger guide](https://kamrapms.com/docs/self-hosting/hostinger).

**Bench:**

```bash
bench get-app payments
bench get-app kamra https://github.com/Kamra-PMS/kamra-pms --branch main
bench --site your-site install-app kamra
```

Then open `/kamra`, sign in as Administrator with the password you set (there is no default) and finish `/kamra/setup`. Production installs track `main`; `develop` is the nightly channel. Release notes: [CHANGELOG.md](CHANGELOG.md) and [what's new](https://kamrapms.com/docs/releases).

Rather not run a server or set it up yourself? Frappe Cloud hosts, backs up and updates it, and our [implementation service](https://kamrapms.com/implementation/) covers migration, setup and training. Implementers can list themselves on [kamrapms.com/partners](https://kamrapms.com/partners/).

---

## FAQ

**Is Kamra really free?**
Yes. The full PMS is open source under Apache-2.0, with no licence fee, no per-room or per-user charges and no paid edition of the open-source app. You pay only for what you choose on top: hosting, and optional setup or support.

**What does it cost to run?**
A small server is enough for most independent hotels (2 vCPU / 4 GB). Self-host on your own VPS, use Frappe Cloud, or ask us for a managed install. AI features use your own key from your chosen provider.

**Can I move from eZee, Cloudbeds or another PMS?**
Yes. Import bookings by CSV (eZee and Cloudbeds presets included), keep your channel manager, and follow the [go-live checklist](https://kamrapms.com/docs/go-live). We or a partner can do it for you.

**Does it connect to Booking.com, Expedia and Airbnb?**
Through your channel manager. Kamra has adapters for Channex.io, STAAH and AioSell, and its own commission-free booking engine at `/book`.

**Is it only for big hotels? Only for India?**
Neither. Kamra fits a 10-room guesthouse, a resort with a restaurant and banquet hall, a group of properties, or a portfolio of villas. Country packs cover India, the Gulf, South-East Asia, Germany, Brazil and more, with a flat-tax fallback anywhere else.

**What if HeyKoala stops working on it?**
The code is Apache-2.0 and on GitHub. You keep running what you have, any Frappe developer can support it, and the community can carry it on. That is the point of owning your PMS.

More answers: [FAQ](https://kamrapms.com/docs/faq).

---

## Docs and help

- **Manual:** [kamrapms.com/docs](https://kamrapms.com/docs/) (guides by role, every module, self-hosting, FAQ), also in [Spanish](https://kamrapms.com/docs/es/) and [Arabic](https://kamrapms.com/docs/ar/)
- **Videos:** [youtube.com/@KamraPMS](https://www.youtube.com/@KamraPMS)
- **Developers:** [REST API reference](https://kamrapms.com/docs/api-reference), [Postman collection](https://kamrapms.com/docs/kamra.postman_collection.json), [How Kamra works](https://kamrapms.com/docs/how-it-works)
- **Why Kamra, and how we fund it:** [kamrapms.com/why-kamra](https://kamrapms.com/why-kamra/) and [kamrapms.com/how-kamra-makes-money](https://kamrapms.com/how-kamra-makes-money/)
- **Bugs and ideas:** [GitHub issues](https://github.com/Kamra-PMS/kamra-pms/issues)
- **Email:** [hello@kamrapms.com](mailto:hello@kamrapms.com)

## Security

Please report vulnerabilities privately, not in a public issue. See [SECURITY.md](SECURITY.md).

## Contributing

Issues and PRs are welcome. Branch from `develop`, use [Conventional Commits](https://www.conventionalcommits.org/), and put anything country-specific in that country's pack, not the core. The full guide, including the eval checks a backend fix needs, is in [CONTRIBUTING.md](CONTRIBUTING.md).

### Quickstart (development)

```bash
bench init --frappe-branch v16.25.0 frappe-bench && cd frappe-bench
bench get-app payments
bench get-app kamra https://github.com/Kamra-PMS/kamra-pms
bench new-site kamra.localhost --admin-password admin
bench --site kamra.localhost install-app kamra
bench serve --port 8000
cd apps/kamra/frontend && npm install && npm run dev   # hot-reload UI on :5173
```

More in [docs-dev.md](docs-dev.md).

## License and trademark

The code is **Apache-2.0**: free to use, change, host and sell, including in proprietary products, with attribution and patent protections as the license requires. Releases published before this change remain AGPL-3.0. The Kamra name and mark are covered by [TRADEMARK.md](TRADEMARK.md): run and resell Kamra freely, show your own hotel or partner logo next to ours, and give a changed fork its own name. See [Kamra is Apache-2.0](https://kamrapms.com/docs/apache-2.0).

If Kamra saves your hotel a licence bill, [star the repo](https://github.com/Kamra-PMS/kamra-pms/stargazers) so the next hotelier searching for a PMS finds it too.

---

## Contributors

Every merged PR and every issue that shapes a feature is credited in the release notes and here. The full list also lives on the docs site: [Contributors](https://kamrapms.com/docs/contributors).

**Code**

- [@Kruthikagowda12](https://github.com/Kruthikagowda12): the AioSell channel-manager adapter and its fixes ([#40](https://github.com/Kamra-PMS/kamra-pms/pull/40), [#46](https://github.com/Kamra-PMS/kamra-pms/pull/46), [#52](https://github.com/Kamra-PMS/kamra-pms/pull/52)), housekeeping proof media and room swap / upgrade ([#74](https://github.com/Kamra-PMS/kamra-pms/pull/74)), phone validation ([#69](https://github.com/Kamra-PMS/kamra-pms/pull/69)), season scoping ([#80](https://github.com/Kamra-PMS/kamra-pms/pull/80)), property / booking flow work ([#22](https://github.com/Kamra-PMS/kamra-pms/pull/22)), and per-head small-group rates with weekend / weekday guardrails ([#162](https://github.com/Kamra-PMS/kamra-pms/pull/162)), and group rooming-list booking with group rate, deposit and quotation ([#422](https://github.com/Kamra-PMS/kamra-pms/pull/422))
- [@Mohammed-Muneef](https://github.com/Mohammed-Muneef): laundry, kitchen display v2, inventory & recipes, menu import, ID-document hardening
- [@faresalslahi-collab](https://github.com/faresalslahi-collab): booking guest and room summary ([#83](https://github.com/Kamra-PMS/kamra-pms/pull/83))
- [@ShaikhAmerPasha](https://github.com/ShaikhAmerPasha): saved bookings keep their voucher after it expires or hits its limit ([#142](https://github.com/Kamra-PMS/kamra-pms/issues/142), [#143](https://github.com/Kamra-PMS/kamra-pms/pull/143)), folio charges refuse zero or minus amounts and unknown tax rates ([#146](https://github.com/Kamra-PMS/kamra-pms/issues/146), [#147](https://github.com/Kamra-PMS/kamra-pms/pull/147)), and the bill screen's Void button, which now asks for a reason ([#160](https://github.com/Kamra-PMS/kamra-pms/issues/160), [#161](https://github.com/Kamra-PMS/kamra-pms/pull/161))
- [@ernestoruiz89](https://github.com/ernestoruiz89): Spanish localization and menu navigation fixes (fork [#320](https://github.com/Kamra-PMS/kamra-pms/pull/320), landed via [#324](https://github.com/Kamra-PMS/kamra-pms/pull/324), included in 2.6.21), international guest phone prefixes ([#345](https://github.com/Kamra-PMS/kamra-pms/pull/345), [#360](https://github.com/Kamra-PMS/kamra-pms/pull/360)), and the chat assistant using the property's currency ([#368](https://github.com/Kamra-PMS/kamra-pms/pull/368), 2.6.22), and the MCP OAuth discovery fix ([#387](https://github.com/Kamra-PMS/kamra-pms/pull/387), 2.7.0)
- [@SandroG1977](https://github.com/SandroG1977): Brazil country pack: ISS, BRL, CNPJ/CPF, NFS-e ([#378](https://github.com/Kamra-PMS/kamra-pms/pull/378)); Portuguese (pt-BR) staff UI ([#377](https://github.com/Kamra-PMS/kamra-pms/pull/377), landed via [#383](https://github.com/Kamra-PMS/kamra-pms/pull/383)); the Portuguese review and wording glossary ([#410](https://github.com/Kamra-PMS/kamra-pms/pull/410)); the assistant quoting with exact occupancy and tax-inclusive totals ([#432](https://github.com/Kamra-PMS/kamra-pms/pull/432)); room pricing fields and children on quote cards ([#444](https://github.com/Kamra-PMS/kamra-pms/pull/444))
- [@pmwanje2](https://github.com/pmwanje2): the hotel's own name and logo next to Kamra's ([#431](https://github.com/Kamra-PMS/kamra-pms/pull/431), landed via [#436](https://github.com/Kamra-PMS/kamra-pms/pull/436))
- [@diegolweb](https://github.com/diegolweb): Channex sends only the dates that changed ([#650](https://github.com/Kamra-PMS/kamra-pms/pull/650), 2.8.0); a country pack can supply the exchange-rate source ([#644](https://github.com/Kamra-PMS/kamra-pms/pull/644)); the missing Spanish front-desk and server strings ([#651](https://github.com/Kamra-PMS/kamra-pms/pull/651))
- [@madhukarah](https://github.com/madhukarah): the desk no longer closes an in-house guest's own bill ([#648](https://github.com/Kamra-PMS/kamra-pms/pull/648), 2.8.0)
- [@kentrick22](https://github.com/kentrick22): Bahasa Indonesia for Today, the reservation and the folio ([#625](https://github.com/Kamra-PMS/kamra-pms/pull/625), 2.8.0)
- [@baiyu0616a](https://github.com/baiyu0616a): Simplified Chinese staff UI ([#618](https://github.com/Kamra-PMS/kamra-pms/pull/618)) and the hotel-term refinements ([#647](https://github.com/Kamra-PMS/kamra-pms/pull/647), 2.8.0)
- [@ankitxxdevil](https://github.com/ankitxxdevil): Frappe payments dependency moved to v16 ([#641](https://github.com/Kamra-PMS/kamra-pms/pull/641), 2.8.0)

**Docs and guides**

- [@caseylee-TC](https://github.com/caseylee-TC): [Write a country pack](https://kamrapms.com/docs/write-a-country-pack) tutorial ([#362](https://github.com/Kamra-PMS/kamra-pms/pull/362), fixes [#258](https://github.com/Kamra-PMS/kamra-pms/issues/258))

**Hotels and users who shaped it through issues**

- [@lhertig](https://github.com/lhertig): folio payments in the property currency ([#341](https://github.com/Kamra-PMS/kamra-pms/issues/341)), `max_total_occupants` on mixed adult/child bookings ([#342](https://github.com/Kamra-PMS/kamra-pms/issues/342)), pre-arrival advance refunds releasing Deposit and reducing `advance_paid` ([#343](https://github.com/Kamra-PMS/kamra-pms/issues/343)), and concurrent booking `tabSeries` deadlock retries ([#344](https://github.com/Kamra-PMS/kamra-pms/issues/344))
- [@faresalslahi-collab](https://github.com/faresalslahi-collab) (Sarawat Park Hotel & Resort): the one-screen walk-in ([#97](https://github.com/Kamra-PMS/kamra-pms/issues/97)), which led to the Saudi Arabia pack and ZATCA, Arab-world dial codes ([#98](https://github.com/Kamra-PMS/kamra-pms/issues/98)), and Kamra's kitchen ledger clashing with ERPNext stock on a shared site ([#131](https://github.com/Kamra-PMS/kamra-pms/issues/131))
- [@atomic-glitch](https://github.com/atomic-glitch): the housekeeping Room Board and role checks ([#99](https://github.com/Kamra-PMS/kamra-pms/issues/99)), room change from the reservation and GRC ([#113](https://github.com/Kamra-PMS/kamra-pms/issues/113)), and deposits before arrival ([#114](https://github.com/Kamra-PMS/kamra-pms/issues/114))
- [@ali-qa-sudo](https://github.com/ali-qa-sudo): role-aware Walk-in / New booking buttons ([#120](https://github.com/Kamra-PMS/kamra-pms/issues/120))
- [@omar99elnemr](https://github.com/omar99elnemr): checkout refused until the bill is settled ([#132](https://github.com/Kamra-PMS/kamra-pms/issues/132))
- [@Syzygy2048](https://github.com/Syzygy2048): current OpenAI models in the assistant ([#23](https://github.com/Kamra-PMS/kamra-pms/issues/23))
- [@andreasnewuser](https://github.com/andreasnewuser): the Germany country pack, 7% MwSt on lodging ([#623](https://github.com/Kamra-PMS/kamra-pms/issues/623), 2.8.0)

**Security**

- **[@archnexus707](https://github.com/archnexus707)**: found and responsibly disclosed cross-property access ([GHSA-6cr2](https://github.com/Kamra-PMS/kamra-pms/security/advisories/GHSA-6cr2-jm8f-6jrx)), fixed in 2.6.5
- [@kta1kri](https://github.com/kta1kri): unauthenticated webhooks ([GHSA-5hcx](https://github.com/Kamra-PMS/kamra-pms/security/advisories/GHSA-5hcx-h257-qr5j)) and an independent report of GHSA-6cr2, both fixed in 2.6.5

---

*Kamra means "room". The door in our logo is open on purpose.*
