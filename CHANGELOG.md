# Changelog

All notable changes to Kamra PMS are documented here. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions follow
[Semantic Versioning](https://semver.org/) with a **patch-first** cadence:
PATCH (`2.6.1`, `2.6.2`) is the default for fixes and small features; MINOR
(`2.7.0`) only when a maintainer deliberately cuts a larger train; MAJOR for
upgrade-breaking changes (removed doctypes / API contracts).

## Unreleased

### Features

* **admin:** System Health screen — GitHub version check, site diagnostics,
  and upgrade guidance for self-host / bench / Docker (no auto-upgrade)
* **settings:** Time zone on Admin → Settings → Property (syncs site System
  Settings clock for single-property sites)
* **mcp:** expand agent surface to 85 tools — stay find/amend/move, payments,
  void/allowance/close folio, tickets advance, housekeeping, POS, and laundry;
  tools filtered by user roles **and** the property's enabled modules
* **ai:** Settings presets for OpenAI, Gemini, Groq, OpenRouter, and Ollama
  (OpenAI-compatible base URL + Test connection)
* **deploy:** WordPress-easy self-host via `deploy/install.sh` + first_boot;
  fresh installs land on `/kamra` instead of Desk
* **banquet:** Phase 1 enterprise ops (issue #67) — email/WhatsApp send
  quotation, desk-led guest response, department checklists + notify on
  Confirm (Sales/Finance/HK/F&B), and quote no-response chase reminders

## [2.6.2](https://github.com/Kamra-PMS/kamra-pms/compare/v2.6.2...v2.6.2) (2026-09-12)


### Features

* activity log rows expand to the full story on click ([c91fb09](https://github.com/Kamra-PMS/kamra-pms/commit/c91fb0977be9153a6f78a6088b6bc12f82f7dfa3))
* **admin:** System Health screen and Property time zone setting ([5e17a5e](https://github.com/Kamra-PMS/kamra-pms/commit/5e17a5ed229e39bf5ad2ce63e689383b8c26505f))
* Arabic RTL / LTR direction setting ([cb4f923](https://github.com/Kamra-PMS/kamra-pms/commit/cb4f923c2606dea50f38bcd8884d9dfaaf04c37e))
* **banquet:** floor plans, hall deals, pre-costing and a stepped flow ([94b2a11](https://github.com/Kamra-PMS/kamra-pms/commit/94b2a1122d46f9b359d8756c7d31a4e08dfa6e35))
* **banquet:** function management from enquiry to close-out ([21a8642](https://github.com/Kamra-PMS/kamra-pms/commit/21a8642aeccadbe212d1745c084a790ac09246ac))
* **banquet:** Phase 1 enterprise ops — send quote, guest response, dept checklists ([7e966d8](https://github.com/Kamra-PMS/kamra-pms/commit/7e966d8ead027cbb7081f9bfa0c2fa753b13c1c5))
* **banquet:** proper document templates - logo, numbers, GST compliance ([385e8c8](https://github.com/Kamra-PMS/kamra-pms/commit/385e8c866fe4d22edf31788de883cbe44acad429))
* Booking Engine app - hotel profile, photos, policies, FAQ, SEO ([74cdb00](https://github.com/Kamra-PMS/kamra-pms/commit/74cdb00e2c4bb93cd80397837c4dd325034ace83))
* booking-engine payment config (advance/deposit) + promo codes on /book ([1b90e12](https://github.com/Kamra-PMS/kamra-pms/commit/1b90e12746bb9b4bebb3eb4ce6d0941156f3624f))
* booking-page accent is now a hex colour picker, not fixed palettes ([e056791](https://github.com/Kamra-PMS/kamra-pms/commit/e05679121dd331c4e848920d06bdba2c62bc6109))
* **booking:** Airbnb-style property catalog, villa page, and listing detail ([2f79a2b](https://github.com/Kamra-PMS/kamra-pms/commit/2f79a2bc17f7ce559241daa1120024973e3c4b08))
* **booking:** Instant path with holds, locks, and idempotency ([0c55aa2](https://github.com/Kamra-PMS/kamra-pms/commit/0c55aa28d7638a0ddc067b44e5ec22201a2a7fd7))
* **booking:** per-villa location on Room Type for multi-site portfolios ([18f57fa](https://github.com/Kamra-PMS/kamra-pms/commit/18f57fa75179abfe4fe94df40138397b57b6c046))
* **booking:** public /stay listing and site slugs for STR catalogs ([f99c5b8](https://github.com/Kamra-PMS/kamra-pms/commit/f99c5b8d8abe0af9085b29bd443da1b262ea860c))
* capture arrival, transport and routed instructions at booking ([fc6849e](https://github.com/Kamra-PMS/kamra-pms/commit/fc6849e67a23a38bb2a4dd395033e6e17ce1c509))
* central reservation system - search & book across the chain, with access guard ([153830a](https://github.com/Kamra-PMS/kamra-pms/commit/153830ab8a8680e356146cb03ab0e4d49a9ea50b))
* channel manager seam - Channex live, STAAH and AioSell adapters ready ([a768e3c](https://github.com/Kamra-PMS/kamra-pms/commit/a768e3c40c094d3c3abe324ff51c45c49e8373be))
* **channel-manager:** Implement AioSell adapter with updated API int… ([c6d259b](https://github.com/Kamra-PMS/kamra-pms/commit/c6d259bfcc1412b86e2273759c344f14e8f6f362))
* **channel-manager:** Implement AioSell adapter with updated API integration ([8b0dbee](https://github.com/Kamra-PMS/kamra-pms/commit/8b0dbeebc6846e26806676ab62e44380d5468fc1))
* check-in becomes a flow - registration readiness, then a room ([b1a9608](https://github.com/Kamra-PMS/kamra-pms/commit/b1a960861abed795504dd57d1b6fa73d7072239b))
* **cloud:** per-property modules and one-command tenant provisioning ([ce6f8a2](https://github.com/Kamra-PMS/kamra-pms/commit/ce6f8a225257c57746285270d2b91cf8148ca6a2))
* command palette reaches every allowed page, searches invoices, keyboard-driven ([538488c](https://github.com/Kamra-PMS/kamra-pms/commit/538488cc929dedc11a47d5a7d35ea028e91836c5))
* connect Claude to the hotel over hosted MCP ([235a0b4](https://github.com/Kamra-PMS/kamra-pms/commit/235a0b4cc4ea621841cc0acfbc61d650ddbd0832))
* currency and number locale follow the property's country pack ([72cb83c](https://github.com/Kamra-PMS/kamra-pms/commit/72cb83c4c65baef06b454bb33730fbf796a258e9))
* **demo:** add guarded nightly reset for public playground ([47acca7](https://github.com/Kamra-PMS/kamra-pms/commit/47acca7156b7193574526995a3d766a24cc741e0))
* enhance phone input handling and validation in BookingDialog; a… ([57bd074](https://github.com/Kamra-PMS/kamra-pms/commit/57bd0743b40b0f0eb51b2037440d1ffdf8f57028))
* enhance phone input handling and validation in BookingDialog; add country support for phone numbers ([90e6bb4](https://github.com/Kamra-PMS/kamra-pms/commit/90e6bb49f8ee91497765fa633e934c2fd8cbc972))
* enhance property management and booking flow ([6f877e7](https://github.com/Kamra-PMS/kamra-pms/commit/6f877e780fad3bdf16a7dfbd70712c7a53350c40))
* Enhance property management and booking flow ([7138cb3](https://github.com/Kamra-PMS/kamra-pms/commit/7138cb37783f5061ca073595707c6c4fc44d2f18))
* **eval_harness:** add missing demo users for role-gate checks in setup ([25d7fca](https://github.com/Kamra-PMS/kamra-pms/commit/25d7fca9eca70384491843e119643db00aedb715))
* expand MCP tools with module gates and WordPress-easy self-host ([d586740](https://github.com/Kamra-PMS/kamra-pms/commit/d586740240ceca1cd1e476bf2271e3aff258c6b2))
* **finance:** add Opera-style cashier till and guest ledger ([da4bf6c](https://github.com/Kamra-PMS/kamra-pms/commit/da4bf6ce945660c54b6b57c3b4b62ad81ac34a84))
* folio audit integrity - mandatory void reason, allowance logging, report ([4e8477d](https://github.com/Kamra-PMS/kamra-pms/commit/4e8477d83dd7a66cb139a9ab81793b0c52905fea))
* front-desk persona journey suite; fix untaxed F&B posting it caught ([bfedb23](https://github.com/Kamra-PMS/kamra-pms/commit/bfedb2353ae4454ec94289b49e6113d9c812d7e4))
* **front-desk:** editable guest nationality on folio, GRC, and profile ([#60](https://github.com/Kamra-PMS/kamra-pms/issues/60)) ([4013778](https://github.com/Kamra-PMS/kamra-pms/commit/401377811554572cb6a5edd72db1273bee2908f6)), closes [#59](https://github.com/Kamra-PMS/kamra-pms/issues/59)
* generated REST API reference + Postman collection; website moves to its own repo ([26790e2](https://github.com/Kamra-PMS/kamra-pms/commit/26790e24796d3b2aa5d28e3f8784246c985afeb6))
* generic pack resolves the currency symbol from the Currency master ([abad702](https://github.com/Kamra-PMS/kamra-pms/commit/abad702871c604b7dc830c180d8240e1529a1cdc))
* **grc:** document uploads, actual stay times, and a real stay ledger ([8f6483b](https://github.com/Kamra-PMS/kamra-pms/commit/8f6483b02325df0131418a2f5275ae124342f5de))
* guests add experiences (safari, spa, dinner) as booking add-ons; seed showcase data ([d4da0ee](https://github.com/Kamra-PMS/kamra-pms/commit/d4da0ee2549eea2481a94d8e11b57673b98e3e5e))
* HK proof media, room swap/upgrade, video upload, POS/Kitchen me… ([6d4d319](https://github.com/Kamra-PMS/kamra-pms/commit/6d4d31975f9c5e73835df6169d7ca02a3e3f9d77))
* HK proof media, room swap/upgrade, video upload, POS/Kitchen menu, agent actions ([ff6df42](https://github.com/Kamra-PMS/kamra-pms/commit/ff6df42bcda706949d1aa71367d4a155d86d7f8c))
* **hk:** housekeeping posts minibar/laundry from the floor ([c0dbd50](https://github.com/Kamra-PMS/kamra-pms/commit/c0dbd50da18a532285ac89ac165f67a8dfa6a907))
* **hk:** Lost & Found gets Found/Missing/Damaged kinds + floor-staff logging ([9a8ca02](https://github.com/Kamra-PMS/kamra-pms/commit/9a8ca02f01858ac0c6efb7c9a6e34aaab2e2df44))
* **hk:** task assignment + self-claim + accept/reject; guest context on floor app ([0f520bc](https://github.com/Kamra-PMS/kamra-pms/commit/0f520bcd28b84bcc751670b982e6a01926aa64dd))
* **hk:** task SLA, multi-level escalation and completion alerts ([0d37ca9](https://github.com/Kamra-PMS/kamra-pms/commit/0d37ca976f845bcd2ea89f06a6cbec68814f2b76))
* **i18n:** finish staff Arabic coverage for POS, laundry, kitchen and folios ([a15f11a](https://github.com/Kamra-PMS/kamra-pms/commit/a15f11a4007277dd5b283e724445e4a4945e1b4b))
* **i18n:** translate Banquet and Tape Chart chrome ([3f98c2d](https://github.com/Kamra-PMS/kamra-pms/commit/3f98c2d3176e29a018f52ff59f26ff6960dff150))
* **i18n:** translate ResourceScreen and add extract/import scripts ([5d9c2b2](https://github.com/Kamra-PMS/kamra-pms/commit/5d9c2b29a3f671d5a1f8f687c1ebb96657e02a16))
* **i18n:** wire staff chrome and key screens through language switcher ([4c156ee](https://github.com/Kamra-PMS/kamra-pms/commit/4c156eeacb824ab332cfc9a71cd191250fae0ee3))
* image uploads with size guidance; booking-page accent themes ([b3cfc7c](https://github.com/Kamra-PMS/kamra-pms/commit/b3cfc7c42f45dc95d2a82037c4d2b11ed9235838))
* inventory & recipes, menu bulk import, KDS v2, hardened ID documents ([#6](https://github.com/Kamra-PMS/kamra-pms/issues/6)) ([20affc0](https://github.com/Kamra-PMS/kamra-pms/commit/20affc061698b0204c771bb0a9bf2b62bebe3bff))
* **inventory:** kitchen stock — optional recipes deduct from the outlet when a KOT fires ([2171b5b](https://github.com/Kamra-PMS/kamra-pms/commit/2171b5b806bd056dc6c2e34d115692fc146b98d0))
* kamrapms.com website, hosting enquiries, and full docs site ([24a735a](https://github.com/Kamra-PMS/kamra-pms/commit/24a735adfc08cff3a1c79054d92023a26ed624e3))
* laundry pickup ([10fcb48](https://github.com/Kamra-PMS/kamra-pms/commit/10fcb486c4982b54289304a35580c17e8d312d42))
* **laundry:** export the rate card as CSV, bulk import/update it back ([c82ebdd](https://github.com/Kamra-PMS/kamra-pms/commit/c82ebdda148c7db02fc05d06b00f7f2ded0dfeba))
* **laundry:** guest laundry end to end — rate card, pickup to return, folio billing ([1d9f61b](https://github.com/Kamra-PMS/kamra-pms/commit/1d9f61bc963c2d31091a1327568cf0f1a35e43fb))
* **laundry:** guest self-service pickup, desk console, house & complimentary orders ([#3](https://github.com/Kamra-PMS/kamra-pms/issues/3)) ([b275383](https://github.com/Kamra-PMS/kamra-pms/commit/b2753831be13910c437daee4328627d8edb03658))
* **localization:** Indonesia country pack — PBJT hotel tax, NPWP, Rupiah ([#4](https://github.com/Kamra-PMS/kamra-pms/issues/4)) ([b753579](https://github.com/Kamra-PMS/kamra-pms/commit/b7535793acf77eab8bca090d3bc5bf6188b860ba))
* **migrate:** vendor-aware CSV importers with dry-run preview (eZee / Cloudbeds / generic) ([dbfc459](https://github.com/Kamra-PMS/kamra-pms/commit/dbfc459099f2df8ce0a09dec3b770afbf609feb7))
* occupant ID capture on the GRC; WhatsApp conversations inbox; setup guide ([4db3387](https://github.com/Kamra-PMS/kamra-pms/commit/4db3387ee1cd05381cfe80c2cb35fd0765e45f60))
* one Move panel for folio routing/splitting; party auto-split into rooms ([6317f40](https://github.com/Kamra-PMS/kamra-pms/commit/6317f4090ef44090a4492b2258c524c21ecfd4de))
* Operations SLA report - breach rate, resolve time, overdue queue ([ea87cc1](https://github.com/Kamra-PMS/kamra-pms/commit/ea87cc1ef964c1d7faa48524e385a30a75a80b9f))
* playground reset and hosted Claude MCP ([4be5b92](https://github.com/Kamra-PMS/kamra-pms/commit/4be5b929d930217f45fc2bdf43dfedeb88bf7c40))
* **pos:** area-wise table map, live temp tables, NC (complimentary) bills ([594129a](https://github.com/Kamra-PMS/kamra-pms/commit/594129a75bc7d7212a6b0b43ae113329b60f2703))
* **pos:** concurrent orders (running tabs), menu search, full-screen, per-outlet kitchen ([1a06086](https://github.com/Kamra-PMS/kamra-pms/commit/1a060866828051c72752e8a6b34439342271b3bd))
* **pos:** kitchen display + guest QR ordering ([5501f49](https://github.com/Kamra-PMS/kamra-pms/commit/5501f49b44eb4ff42b530391b00a398c348aab5d))
* **pos:** menu item photos upload directly (or paste a URL) ([07700ce](https://github.com/Kamra-PMS/kamra-pms/commit/07700cecf2868d53de742ab129914ae604d7b97a))
* **pos:** move POS into its own F&B app; add Menu & Outlets management screens ([2f47a5e](https://github.com/Kamra-PMS/kamra-pms/commit/2f47a5ed222ad55737682d2d130944a5509bb225))
* **pos:** restaurant POS - digital menu, captain ordering, KOT, room posting ([a17ad83](https://github.com/Kamra-PMS/kamra-pms/commit/a17ad83da17fc5db36c24dd36e4967f73f0fad82))
* **pos:** shared tables, split bills, temp tables, clearer new-order flow ([211e69e](https://github.com/Kamra-PMS/kamra-pms/commit/211e69e7461d4520dc155138fa46c1089771bc19))
* **pos:** table map, thermal KOT & bill printing, outlet settle, order types, voids ([435855a](https://github.com/Kamra-PMS/kamra-pms/commit/435855a19f46b75eeca68f40de2cb14ebf4ae3ec))
* **pos:** table reservations, cleaning state, self-healing deploys ([b55b33d](https://github.com/Kamra-PMS/kamra-pms/commit/b55b33d78c881c6dac334bafdb7c22438c4749c5))
* **pos:** three-column POS — delivery orders, table seats, recent bills, F-key shortcuts ([15c9dda](https://github.com/Kamra-PMS/kamra-pms/commit/15c9dda0db27ef218847cf5e41f79f6aabc935c1))
* **pos:** traverse running orders - prev/next arrows + scrollable tab strip ([bbb6bfc](https://github.com/Kamra-PMS/kamra-pms/commit/bbb6bfc415eca498163bebc56d4ef7513893869b))
* property + central (portfolio) dashboards by department ([f524d62](https://github.com/Kamra-PMS/kamra-pms/commit/f524d62bafa4a5b322bc001a6854e7b1bd97f946))
* **realtime:** live async updates on tickets, dashboard, activity, groups ([03e1dda](https://github.com/Kamra-PMS/kamra-pms/commit/03e1ddac54ff41e3b6eb06bf7cb7a9e3d5c31311))
* **realtime:** live kitchen display, POS tabs and housekeeping over the socket ([5761336](https://github.com/Kamra-PMS/kamra-pms/commit/576133691bd5dfebe38af9fe98e810ded38d56f2))
* **revenue:** tape-chart position with ETA/ETD, overbooking allowance, hurdle rates, GM briefing ([e81a928](https://github.com/Kamra-PMS/kamra-pms/commit/e81a9280fada5297533392fb9ebc4491a4b94691))
* room blocks - hold rooms out of sale for house use, VIP, maintenance ([e952940](https://github.com/Kamra-PMS/kamra-pms/commit/e952940b693322ef53652415b7e91f7d6bfe39f3))
* **seed:** operations demo data — tickets, shift handovers, live laundry ([7ccc730](https://github.com/Kamra-PMS/kamra-pms/commit/7ccc730e3d604604ad5df1a9cf3919f8b61754a6))
* **seed:** sample content across the demo - profile, today story, revenue tiers ([51059fd](https://github.com/Kamra-PMS/kamra-pms/commit/51059fd8f3319a4918e009312f8870e38ee063ea))
* **setup:** property_kind preset and STR wizard branch ([132e34c](https://github.com/Kamra-PMS/kamra-pms/commit/132e34cbf8e796a402f9b01c4096872f16c7657f))
* shadcn-green console redesign + booking details + folio audit + code-split ([3c8a55a](https://github.com/Kamra-PMS/kamra-pms/commit/3c8a55aa2f29a32ff7b6e266882913e63d05a1b6))
* **siu:** sellable units and availability SSOT for STR ([31e9403](https://github.com/Kamra-PMS/kamra-pms/commit/31e940323104a5cbfb16d63f412e01d3247f7dfd))
* sortable columns on manager flash trend table ([103a422](https://github.com/Kamra-PMS/kamra-pms/commit/103a42280e86ce40ef261883145c31fb7008cda8))
* **str:** quote ledger, deposits, turnover, and access gates ([265e2ae](https://github.com/Kamra-PMS/kamra-pms/commit/265e2ae73acc2bd4cbd8aa1913018a203948eeb0))
* Thailand, Malaysia and UAE country packs; enquiry routing fields ([7a5ce2b](https://github.com/Kamra-PMS/kamra-pms/commit/7a5ce2b3288cbca34ed07429802160463750febb))
* **ui:** capture requests & arrival in the booking dialog ([3084757](https://github.com/Kamra-PMS/kamra-pms/commit/308475776a3645ac8cb0dccf3a4563bb0096a753))
* **ui:** Dashboard on the shared shadcn-green StatCard ([0df81f5](https://github.com/Kamra-PMS/kamra-pms/commit/0df81f513760c3572e2287aead53ba49d4df20ac))
* **ui:** in-house guests as a data table with avatar chips ([e2c6577](https://github.com/Kamra-PMS/kamra-pms/commit/e2c6577b7a32886f36dc9b6b172902df5c21119d))
* **ui:** room board floor tabs, HK/insights panels, centered search ([a5d6ffe](https://github.com/Kamra-PMS/kamra-pms/commit/a5d6ffe13172e136cc0dfad16e31b147795e67a2))
* **ui:** shadcn-green front-desk overview - KPI strip with sparklines ([b79f1f1](https://github.com/Kamra-PMS/kamra-pms/commit/b79f1f1090ae01cadcb0c455d29d20fdcf4c16fd))
* venue calendar is now interactive - add, edit and search from the grid ([5281bbd](https://github.com/Kamra-PMS/kamra-pms/commit/5281bbd9db56c96b65fd09725f377ed500feecaa))
* WhatsApp on your own number - Meta Cloud API, open source ([eaabab2](https://github.com/Kamra-PMS/kamra-pms/commit/eaabab23542ef645482e89222efd0eb0fe97a812))


### Bug Fixes

* **assistant:** GPT-5.6 luna/terra/sol tool calling on chat completions ([84c8bf9](https://github.com/Kamra-PMS/kamra-pms/commit/84c8bf972be3d9128b6789319a925693a0bf7fae)), closes [#23](https://github.com/Kamra-PMS/kamra-pms/issues/23)
* **banquet:** one door to create a function, and a real dish editor ([e3ca25b](https://github.com/Kamra-PMS/kamra-pms/commit/e3ca25b9d6744709f75643e3bf3fc6425e3b2502))
* **booking:** always show country code on public phone numbers ([0016525](https://github.com/Kamra-PMS/kamra-pms/commit/001652536d2ee4c1054d788e4294f9f11ee504d0))
* **booking:** fill /book hero with showcase photo or brand accent ([abb7e3d](https://github.com/Kamra-PMS/kamra-pms/commit/abb7e3d4c7367500b4d35b414951c55ebdfb662b))
* **booking:** null-safe cancellation/no-show fee labels ([781d638](https://github.com/Kamra-PMS/kamra-pms/commit/781d6386d8ef687a9f0845c0fd4856459a70679c))
* **booking:** null-safe cancellation/no-show fee labels ([03c0963](https://github.com/Kamra-PMS/kamra-pms/commit/03c0963dde4455990fe76bfb67673e5324dfb38e))
* **booking:** null-safe fee labels ([9b30810](https://github.com/Kamra-PMS/kamra-pms/commit/9b30810f67cf87fa859cdb50ef2f9e6b067edc62))
* **booking:** null-safe fee labels and widen booking sheet ([e815491](https://github.com/Kamra-PMS/kamra-pms/commit/e81549197f7be15c141996b5bf503623f07be5a7))
* **booking:** persist uploaded images automatically ([737b4c5](https://github.com/Kamra-PMS/kamra-pms/commit/737b4c5d9ea8da6d0a50c5db7b01cdb9187148b9))
* **booking:** real check-in/out date range + explicit search CTA ([ea7e6e0](https://github.com/Kamra-PMS/kamra-pms/commit/ea7e6e0e12e5497f93f1066594bdbf609907054b))
* **booking:** resolve tenant property for public booking engine ([2acc59c](https://github.com/Kamra-PMS/kamra-pms/commit/2acc59c491b72452d4126aaae82a40568a84e70f))
* **channel-manager:** add _do_cancel helper for OTA cancels ([cd9f332](https://github.com/Kamra-PMS/kamra-pms/commit/cd9f3321d2211892c15164fa5dc947d70a2abc9d))
* **channel-manager:** exact nosemgrep:frappe-setuser marker for marketplace check ([baa94c2](https://github.com/Kamra-PMS/kamra-pms/commit/baa94c225cb9e7b075c9d9aaeaac85bedc0601c4))
* **channel-manager:** OTA cancel under Guest + agent_name logging ([0b50fdf](https://github.com/Kamra-PMS/kamra-pms/commit/0b50fdf80f629601e0270478714a494de6f7aef3))
* **channel-manager:** OTA cancel under Guest + agent_name logging ([0c771be](https://github.com/Kamra-PMS/kamra-pms/commit/0c771bec8429ad2730d5ca53063f71490b13b4cb))
* **channel-manager:** preserve AioSell Basic-auth so Frappe doesn't r… ([d671b7a](https://github.com/Kamra-PMS/kamra-pms/commit/d671b7a2fab24dd9d449799a0f5990bd8cec4ad3))
* **channel-manager:** preserve AioSell Basic-auth so Frappe doesn't reject the webhook ([b0937bd](https://github.com/Kamra-PMS/kamra-pms/commit/b0937bd6409023200bd431d9dc25d3c800e149a9))
* clear AUD-00003 Semgrep Security warning ([fedbd98](https://github.com/Kamra-PMS/kamra-pms/commit/fedbd98726f770d806a4228c44a6881c235e6e9a))
* clear Frappe Cloud audit frappe-manual-commit ([e6be2bf](https://github.com/Kamra-PMS/kamra-pms/commit/e6be2bf8dbb2defc9ea517310d40ed68f02e8776))
* clear leftover agent-era copy from the UI ([ebaf62a](https://github.com/Kamra-PMS/kamra-pms/commit/ebaf62a0c97893940edc66317d763da6b3bc9367))
* close Dependabot CVEs and Code Quality findings ([7d51e08](https://github.com/Kamra-PMS/kamra-pms/commit/7d51e08b640808f9c92e92ce7a387d541d4ee243))
* close Dependabot CVEs and GitHub Code Quality findings ([c0d6cdc](https://github.com/Kamra-PMS/kamra-pms/commit/c0d6cdcf512255fe81abb47eed18a4dfe3fc82d8))
* **cloud:** admin cannot be switched off, and module-gate tests ([41734be](https://github.com/Kamra-PMS/kamra-pms/commit/41734be30e5ff2b2b3ce84227d3973fa1399ab03))
* de-duplicate Booking Engine section nav; link journey events to the reservation ([8d31eaf](https://github.com/Kamra-PMS/kamra-pms/commit/8d31eaf255fb4de57d053bdb6ee44d15c877fb76))
* declare Frappe v16 for the marketplace + listing copy ([#14](https://github.com/Kamra-PMS/kamra-pms/issues/14)) ([9e128ea](https://github.com/Kamra-PMS/kamra-pms/commit/9e128eae0beb2f54d55edf95aad0c9740e6b3a5b))
* drop scheduler manual commit that failed FC Submission Gate ([339971f](https://github.com/Kamra-PMS/kamra-pms/commit/339971f3d0311a86c0b85d3a493bea2ce57c5c0f))
* drop superseded local id-image state after pipeline unification ([9c4b9ff](https://github.com/Kamra-PMS/kamra-pms/commit/9c4b9ff4e349084b71b4b15d3fd88daa5e2c2ebc))
* **eval:** guest merge + SIU room pick for booking harness ([9101ce5](https://github.com/Kamra-PMS/kamra-pms/commit/9101ce509628ddd5f95a96b6b9ffd7308dcc6df5))
* **eval:** Venue Booking merge uses customer field ([bbd310d](https://github.com/Kamra-PMS/kamra-pms/commit/bbd310d9a17631d25567f20161f96c4cda6136ef))
* **eval:** Venue Booking merge uses customer field ([5028d10](https://github.com/Kamra-PMS/kamra-pms/commit/5028d10e68a5c1edd2c890f9c6578a8c549f1fc5))
* **folio:** return guest_id from folio_invoice for nationality edit ([#63](https://github.com/Kamra-PMS/kamra-pms/issues/63)) ([d3ea808](https://github.com/Kamra-PMS/kamra-pms/commit/d3ea808ead19c615f63986296874428dc9bb912b))
* GRC, self check-in submit and public booking were silently un-whitelisted ([0616b1f](https://github.com/Kamra-PMS/kamra-pms/commit/0616b1fb5d8ad219231ab800f94f5e98fe3b14ae))
* **grc:** make actual check-in/out datetime edit reliable ([b029b26](https://github.com/Kamra-PMS/kamra-pms/commit/b029b263b363ee951c86184b0798e9a22400d5c7))
* **harness:** create the agent user without seed_rbac_v2's custom perm grants ([467c816](https://github.com/Kamra-PMS/kamra-pms/commit/467c8166ea9f5ee4bd29e0ab049b409f7db82413))
* **install:** don't seed partial agent perms at install - custom DocPerms replace standard ones ([77faf87](https://github.com/Kamra-PMS/kamra-pms/commit/77faf8761c4f9758935d1cdf1ad3662aad4950f8))
* issue-template config.yml was invalid YAML ([b83a391](https://github.com/Kamra-PMS/kamra-pms/commit/b83a391c5a1c83800c0ba0f08cdd8e3de5dd7280))
* Kamra favicon on Frappe-served pages; Revenue icon is no longer a pig ([21b0bd2](https://github.com/Kamra-PMS/kamra-pms/commit/21b0bd2611bd200a7e213d3a447d2a2cb0349249))
* **marketplace:** annotate MCP and HK set_user for FC gate ([04f4b7b](https://github.com/Kamra-PMS/kamra-pms/commit/04f4b7bfabf44c87ea35c71822d4a2311ce8bf61))
* move language (English/Arabic) into Settings &gt; Appearance, off the header ([6b6791a](https://github.com/Kamra-PMS/kamra-pms/commit/6b6791a4f9d9555eb05ec1d86b62c2ccb3dc750c))
* **nav:** GRC & cancellation links 404'd in production; feat: ID photo capture at pre-check-in ([d3064ea](https://github.com/Kamra-PMS/kamra-pms/commit/d3064ea31a08fef7fd75b12bf19cb059fafdecae))
* pin release-please to main - default branch is develop now ([764be73](https://github.com/Kamra-PMS/kamra-pms/commit/764be73d73f72eb61bfc98fa1f03a542bbba3975))
* **pos:** clear stale kitchen drawer and keep Esc layered ([f59bc93](https://github.com/Kamra-PMS/kamra-pms/commit/f59bc93aa1c31b6c8fc75055f0f0f9c86d6c7367))
* **pos:** KOT daily sequence uses site-local today ([8e58c3b](https://github.com/Kamra-PMS/kamra-pms/commit/8e58c3b299b38db4778abef36e0f907fc2580f9b))
* **pos:** restore Esc and Maximize on floor fullscreen ([125d00b](https://github.com/Kamra-PMS/kamra-pms/commit/125d00beca471543101b436328273ed8de35259c))
* **pos:** restore Esc and Maximize on floor fullscreen ([cdcee0e](https://github.com/Kamra-PMS/kamra-pms/commit/cdcee0ecf7696ee4350c6d0c205c758dbcd91c8c))
* **pos:** table tile layout — elapsed time no longer overlaps the name ([16567ab](https://github.com/Kamra-PMS/kamra-pms/commit/16567ab12da36a805545f45410230ef2991ac714))
* **provision:** support implicit SSL for SMTP on port 465 ([d8bfaa8](https://github.com/Kamra-PMS/kamra-pms/commit/d8bfaa8b284932a3b53faa46d33ead51fd108a11))
* public booking search was 403ing for every real guest ([cbd964b](https://github.com/Kamra-PMS/kamra-pms/commit/cbd964b42d97db5c7d5fc014bb86c86a922c4a65))
* **reservation:** block backdated check-in on create and amend ([#72](https://github.com/Kamra-PMS/kamra-pms/issues/72)) ([3dbedef](https://github.com/Kamra-PMS/kamra-pms/commit/3dbedefb93451bc8fb414c5ded90403ab627d39f)), closes [#71](https://github.com/Kamra-PMS/kamra-pms/issues/71)
* resolve Frappe Cloud marketplace Semgrep findings ([#16](https://github.com/Kamra-PMS/kamra-pms/issues/16)) ([378c44d](https://github.com/Kamra-PMS/kamra-pms/commit/378c44d063223bc1a150825c450c924e5a812ef9))
* rooms can no longer sleep more guests than the room type allows ([b65bffc](https://github.com/Kamra-PMS/kamra-pms/commit/b65bffc8b70501891aee72e3d321cde1098acc16))
* Settings booking-page logo and hero become upload fields ([4edc370](https://github.com/Kamra-PMS/kamra-pms/commit/4edc37075d4c57e21141f3542f7c6908a426437c))
* silence FC Semgrep Security set_user warnings ([67d26b1](https://github.com/Kamra-PMS/kamra-pms/commit/67d26b18c72153f29fef862ae33163ef53abb7b2))
* **ui:** tighten Service Tickets header layout ([f999a1e](https://github.com/Kamra-PMS/kamra-pms/commit/f999a1e3d729e32ba97b91dca9d4652ae0a89466))
* **ux:** human error messages, offline resilience, graceful session handling ([3e867b2](https://github.com/Kamra-PMS/kamra-pms/commit/3e867b2cab22b3e2272cd59eb5ad81b496be2e76))


### Performance Improvements

* **ui:** code-split routes with React.lazy ([3f5e28f](https://github.com/Kamra-PMS/kamra-pms/commit/3f5e28f60aa207cc4a48d622df85ed9d7da3405e))


### Miscellaneous Chores

* pin next release version ([19fbe5f](https://github.com/Kamra-PMS/kamra-pms/commit/19fbe5f88397452e8c381ea08a6979c7da9c4520))

## [2.6.2](https://github.com/Kamra-PMS/kamra-pms/compare/v2.6.0...v2.6.2) (2026-09-07)

### Features

* **finance:** Opera-style cashier module — till open/close with float and variance, unified FO+POS cash, petty cash, shift report, and currency desk under Finance → Cashier
* **finance:** append-only folio ledger (Guest / Deposit / AR / Package), transaction codes, reason codes, city ledger aging, advance bill, proforma folio, and credit notes
* **finance:** cashier PIN pad with admin reset, lockout, and a 15-minute unlock window on folio and POS money actions
* **ops:** property business date advanced by night audit; postings and cash summary use business date
* **pos:** full-screen till and kitchen pass, F&B dashboard, clearer settle sheet and complimentary actions

### Bug Fixes

* MCP stdio sidecar now registers group and banquet tools (`mcp.run()` had been sitting mid-file). Duplicate `banquet_receipt` split into `banquet_record_receipt` and `banquet_receipt_document`. Tool list is a shared registry of 52 tools.

## [2.6.0](https://github.com/Kamra-PMS/kamra-pms/compare/v2.5.0...v2.6.0) (2026-08-27)


### Features

* **channel-manager:** Implement AioSell adapter with updated API int… ([c6d259b](https://github.com/Kamra-PMS/kamra-pms/commit/c6d259bfcc1412b86e2273759c344f14e8f6f362))
* **channel-manager:** Implement AioSell adapter with updated API integration ([8b0dbee](https://github.com/Kamra-PMS/kamra-pms/commit/8b0dbeebc6846e26806676ab62e44380d5468fc1))
* connect Claude to the hotel over hosted MCP ([235a0b4](https://github.com/Kamra-PMS/kamra-pms/commit/235a0b4cc4ea621841cc0acfbc61d650ddbd0832))
* **demo:** add guarded nightly reset for public playground ([47acca7](https://github.com/Kamra-PMS/kamra-pms/commit/47acca7156b7193574526995a3d766a24cc741e0))
* playground reset and hosted Claude MCP ([4be5b92](https://github.com/Kamra-PMS/kamra-pms/commit/4be5b929d930217f45fc2bdf43dfedeb88bf7c40))


### Bug Fixes

* **booking:** null-safe cancellation/no-show fee labels ([781d638](https://github.com/Kamra-PMS/kamra-pms/commit/781d6386d8ef687a9f0845c0fd4856459a70679c))
* **booking:** null-safe cancellation/no-show fee labels ([03c0963](https://github.com/Kamra-PMS/kamra-pms/commit/03c0963dde4455990fe76bfb67673e5324dfb38e))
* **booking:** null-safe fee labels ([9b30810](https://github.com/Kamra-PMS/kamra-pms/commit/9b30810f67cf87fa859cdb50ef2f9e6b067edc62))
* **booking:** null-safe fee labels and widen booking sheet ([e815491](https://github.com/Kamra-PMS/kamra-pms/commit/e81549197f7be15c141996b5bf503623f07be5a7))
* **channel-manager:** add _do_cancel helper for OTA cancels ([cd9f332](https://github.com/Kamra-PMS/kamra-pms/commit/cd9f3321d2211892c15164fa5dc947d70a2abc9d))
* **channel-manager:** exact nosemgrep:frappe-setuser marker for marketplace check ([baa94c2](https://github.com/Kamra-PMS/kamra-pms/commit/baa94c225cb9e7b075c9d9aaeaac85bedc0601c4))
* **channel-manager:** preserve AioSell Basic-auth so Frappe doesn't r… ([d671b7a](https://github.com/Kamra-PMS/kamra-pms/commit/d671b7a2fab24dd9d449799a0f5990bd8cec4ad3))
* **channel-manager:** preserve AioSell Basic-auth so Frappe doesn't reject the webhook ([b0937bd](https://github.com/Kamra-PMS/kamra-pms/commit/b0937bd6409023200bd431d9dc25d3c800e149a9))
* clear AUD-00003 Semgrep Security warning ([fedbd98](https://github.com/Kamra-PMS/kamra-pms/commit/fedbd98726f770d806a4228c44a6881c235e6e9a))
* clear Frappe Cloud audit frappe-manual-commit ([e6be2bf](https://github.com/Kamra-PMS/kamra-pms/commit/e6be2bf8dbb2defc9ea517310d40ed68f02e8776))
* drop scheduler manual commit that failed FC Submission Gate ([339971f](https://github.com/Kamra-PMS/kamra-pms/commit/339971f3d0311a86c0b85d3a493bea2ce57c5c0f))
* **marketplace:** annotate MCP and HK set_user for FC gate ([04f4b7b](https://github.com/Kamra-PMS/kamra-pms/commit/04f4b7bfabf44c87ea35c71822d4a2311ce8bf61))
* silence FC Semgrep Security set_user warnings ([67d26b1](https://github.com/Kamra-PMS/kamra-pms/commit/67d26b18c72153f29fef862ae33163ef53abb7b2))

## [2.5.0](https://github.com/Kamra-PMS/kamra-pms/compare/v2.4.0...v2.5.0) (2026-08-13)

**Short-term rentals.** Kamra is no longer hotel-only. A property can be a
hotel *or* a short-term rental portfolio: several villas at different
addresses, sold room-wise or as the whole house, with deposits, cleaning fees,
and a guest catalog that looks like a listing site.

Hotel installs are unchanged. Set **Property kind** to Short Term Rental (on
create, or later in Settings) to get the STR catalog, per-villa maps, and
sellable-unit inventory.

### Features

* **STR property kind** — setup wizard and Settings branch for villas vs hotels (`property_kind`)
* **Sellable inventory units** — room, whole-place, or package, with competition groups so booking the villa blocks its rooms
* **Multi-villa booking engine** — `/book` catalog of sites, `/stay/:slug` villa and listing pages, per-room-type location (name, address, map, lat/long)
* **Guest search that looks like a booking site** — check-in and check-out dates (not a nights spinner), adults/children, and a **Check availability** button on both the catalog and the villa page
* Instant book with holds/locks, or request-to-book; cleaning fee and refundable security deposit on the quote
* **Banquet** — enquiry-to-close-out functions, floor plans, hall deals, GST-ready documents
* **Cloud** — per-property modules and one-command tenant provisioning

### Bug Fixes

* Copilot works with current OpenAI models (`gpt-5.6-luna`, `gpt-5.6-terra`, `gpt-5.6-sol`) — Chat Completions + tools no longer 400 ([#23](https://github.com/Kamra-PMS/kamra-pms/issues/23))
* Public phone numbers: a 10-digit Indian mobile starting with `91` is no longer stripped to eight digits
* Public booking engine resolves the tenant's property instead of a hardcoded demo name
* POS KOT daily sequence uses site-local today (no UTC reset after 18:30)
* Guest merge repoints Venue Booking via `customer`; eval harness isolates failed checks
* Provision SMTP supports implicit SSL on port 465
* Dependabot CVEs and Code Quality findings closed

## [2.4.0](https://github.com/Kamra-PMS/kamra-pms/compare/v2.3.0...v2.4.0) (2026-07-28)


### Features

* capture arrival, transport and routed instructions at booking ([fc6849e](https://github.com/Kamra-PMS/kamra-pms/commit/fc6849e67a23a38bb2a4dd395033e6e17ce1c509))
* folio audit integrity - mandatory void reason, allowance logging, report ([4e8477d](https://github.com/Kamra-PMS/kamra-pms/commit/4e8477d83dd7a66cb139a9ab81793b0c52905fea))
* shadcn-green console redesign + booking details + folio audit + code-split ([3c8a55a](https://github.com/Kamra-PMS/kamra-pms/commit/3c8a55aa2f29a32ff7b6e266882913e63d05a1b6))
* **ui:** capture requests & arrival in the booking dialog ([3084757](https://github.com/Kamra-PMS/kamra-pms/commit/308475776a3645ac8cb0dccf3a4563bb0096a753))
* **ui:** Dashboard on the shared shadcn-green StatCard ([0df81f5](https://github.com/Kamra-PMS/kamra-pms/commit/0df81f513760c3572e2287aead53ba49d4df20ac))
* **ui:** in-house guests as a data table with avatar chips ([e2c6577](https://github.com/Kamra-PMS/kamra-pms/commit/e2c6577b7a32886f36dc9b6b172902df5c21119d))
* **ui:** room board floor tabs, HK/insights panels, centered search ([a5d6ffe](https://github.com/Kamra-PMS/kamra-pms/commit/a5d6ffe13172e136cc0dfad16e31b147795e67a2))
* **ui:** shadcn-green front-desk overview - KPI strip with sparklines ([b79f1f1](https://github.com/Kamra-PMS/kamra-pms/commit/b79f1f1090ae01cadcb0c455d29d20fdcf4c16fd))


### Performance Improvements

* **ui:** code-split routes with React.lazy ([3f5e28f](https://github.com/Kamra-PMS/kamra-pms/commit/3f5e28f60aa207cc4a48d622df85ed9d7da3405e))

## [2.3.0](https://github.com/Kamra-PMS/kamra-pms/compare/v2.2.1...v2.3.0) (2026-07-27)


### Features

* channel manager seam - Channex live, STAAH and AioSell adapters ready ([a768e3c](https://github.com/Kamra-PMS/kamra-pms/commit/a768e3c40c094d3c3abe324ff51c45c49e8373be))
* check-in becomes a flow - registration readiness, then a room ([b1a9608](https://github.com/Kamra-PMS/kamra-pms/commit/b1a960861abed795504dd57d1b6fa73d7072239b))
* currency and number locale follow the property's country pack ([72cb83c](https://github.com/Kamra-PMS/kamra-pms/commit/72cb83c4c65baef06b454bb33730fbf796a258e9))
* generic pack resolves the currency symbol from the Currency master ([abad702](https://github.com/Kamra-PMS/kamra-pms/commit/abad702871c604b7dc830c180d8240e1529a1cdc))
* **localization:** Indonesia country pack — PBJT hotel tax, NPWP, Rupiah ([#4](https://github.com/Kamra-PMS/kamra-pms/issues/4)) ([b753579](https://github.com/Kamra-PMS/kamra-pms/commit/b7535793acf77eab8bca090d3bc5bf6188b860ba))
* occupant ID capture on the GRC; WhatsApp conversations inbox; setup guide ([4db3387](https://github.com/Kamra-PMS/kamra-pms/commit/4db3387ee1cd05381cfe80c2cb35fd0765e45f60))
* Thailand, Malaysia and UAE country packs; enquiry routing fields ([7a5ce2b](https://github.com/Kamra-PMS/kamra-pms/commit/7a5ce2b3288cbca34ed07429802160463750febb))
* WhatsApp on your own number - Meta Cloud API, open source ([eaabab2](https://github.com/Kamra-PMS/kamra-pms/commit/eaabab23542ef645482e89222efd0eb0fe97a812))


### Bug Fixes

* declare Frappe v16 for the marketplace + listing copy ([#14](https://github.com/Kamra-PMS/kamra-pms/issues/14)) ([9e128ea](https://github.com/Kamra-PMS/kamra-pms/commit/9e128eae0beb2f54d55edf95aad0c9740e6b3a5b))
* GRC, self check-in submit and public booking were silently un-whitelisted ([0616b1f](https://github.com/Kamra-PMS/kamra-pms/commit/0616b1fb5d8ad219231ab800f94f5e98fe3b14ae))
* resolve Frappe Cloud marketplace Semgrep findings ([#16](https://github.com/Kamra-PMS/kamra-pms/issues/16)) ([378c44d](https://github.com/Kamra-PMS/kamra-pms/commit/378c44d063223bc1a150825c450c924e5a812ef9))
* Settings booking-page logo and hero become upload fields ([4edc370](https://github.com/Kamra-PMS/kamra-pms/commit/4edc37075d4c57e21141f3542f7c6908a426437c))

## [2.2.1](https://github.com/Kamra-PMS/kamra-pms/compare/v2.2.0...v2.2.1) (2026-07-22)


### Features

* **grc:** document uploads, actual stay times, and a real stay ledger ([8f6483b](https://github.com/Kamra-PMS/kamra-pms/commit/8f6483b02325df0131418a2f5275ae124342f5de))
* inventory & recipes, menu bulk import, KDS v2, hardened ID documents ([#6](https://github.com/Kamra-PMS/kamra-pms/issues/6)) ([20affc0](https://github.com/Kamra-PMS/kamra-pms/commit/20affc061698b0204c771bb0a9bf2b62bebe3bff))
* **laundry:** export the rate card as CSV, bulk import/update it back ([c82ebdd](https://github.com/Kamra-PMS/kamra-pms/commit/c82ebdda148c7db02fc05d06b00f7f2ded0dfeba))


### Bug Fixes

* drop superseded local id-image state after pipeline unification ([9c4b9ff](https://github.com/Kamra-PMS/kamra-pms/commit/9c4b9ff4e349084b71b4b15d3fd88daa5e2c2ebc))


### Miscellaneous Chores

* pin next release version ([19fbe5f](https://github.com/Kamra-PMS/kamra-pms/commit/19fbe5f88397452e8c381ea08a6979c7da9c4520))

## [2.2.0](https://github.com/Kamra-PMS/kamra-pms/compare/v2.1.0...v2.2.0) (2026-07-22)


### Features

* **laundry:** guest self-service pickup, desk console, house & complimentary orders ([#3](https://github.com/Kamra-PMS/kamra-pms/issues/3)) ([b275383](https://github.com/Kamra-PMS/kamra-pms/commit/b2753831be13910c437daee4328627d8edb03658))


### Bug Fixes

* **nav:** GRC & cancellation links 404'd in production; feat: ID photo capture at pre-check-in ([d3064ea](https://github.com/Kamra-PMS/kamra-pms/commit/d3064ea31a08fef7fd75b12bf19cb059fafdecae))

## [2.1.0](https://github.com/Kamra-PMS/kamra-pms/compare/v2.0.0...v2.1.0) (2026-07-14)


### Features

* activity log rows expand to the full story on click ([c91fb09](https://github.com/Kamra-PMS/kamra-pms/commit/c91fb0977be9153a6f78a6088b6bc12f82f7dfa3))
* Arabic RTL / LTR direction setting ([cb4f923](https://github.com/Kamra-PMS/kamra-pms/commit/cb4f923c2606dea50f38bcd8884d9dfaaf04c37e))
* booking-engine payment config (advance/deposit) + promo codes on /book ([1b90e12](https://github.com/Kamra-PMS/kamra-pms/commit/1b90e12746bb9b4bebb3eb4ce6d0941156f3624f))
* booking-page accent is now a hex colour picker, not fixed palettes ([e056791](https://github.com/Kamra-PMS/kamra-pms/commit/e05679121dd331c4e848920d06bdba2c62bc6109))
* central reservation system - search & book across the chain, with access guard ([153830a](https://github.com/Kamra-PMS/kamra-pms/commit/153830ab8a8680e356146cb03ab0e4d49a9ea50b))
* command palette reaches every allowed page, searches invoices, keyboard-driven ([538488c](https://github.com/Kamra-PMS/kamra-pms/commit/538488cc929dedc11a47d5a7d35ea028e91836c5))
* front-desk persona journey suite; fix untaxed F&B posting it caught ([bfedb23](https://github.com/Kamra-PMS/kamra-pms/commit/bfedb2353ae4454ec94289b49e6113d9c812d7e4))
* generated REST API reference + Postman collection; website moves to its own repo ([26790e2](https://github.com/Kamra-PMS/kamra-pms/commit/26790e24796d3b2aa5d28e3f8784246c985afeb6))
* guests add experiences (safari, spa, dinner) as booking add-ons; seed showcase data ([d4da0ee](https://github.com/Kamra-PMS/kamra-pms/commit/d4da0ee2549eea2481a94d8e11b57673b98e3e5e))
* **hk:** housekeeping posts minibar/laundry from the floor ([c0dbd50](https://github.com/Kamra-PMS/kamra-pms/commit/c0dbd50da18a532285ac89ac165f67a8dfa6a907))
* **hk:** Lost & Found gets Found/Missing/Damaged kinds + floor-staff logging ([9a8ca02](https://github.com/Kamra-PMS/kamra-pms/commit/9a8ca02f01858ac0c6efb7c9a6e34aaab2e2df44))
* **hk:** task assignment + self-claim + accept/reject; guest context on floor app ([0f520bc](https://github.com/Kamra-PMS/kamra-pms/commit/0f520bcd28b84bcc751670b982e6a01926aa64dd))
* **hk:** task SLA, multi-level escalation and completion alerts ([0d37ca9](https://github.com/Kamra-PMS/kamra-pms/commit/0d37ca976f845bcd2ea89f06a6cbec68814f2b76))
* image uploads with size guidance; booking-page accent themes ([b3cfc7c](https://github.com/Kamra-PMS/kamra-pms/commit/b3cfc7c42f45dc95d2a82037c4d2b11ed9235838))
* kamrapms.com website, hosting enquiries, and full docs site ([24a735a](https://github.com/Kamra-PMS/kamra-pms/commit/24a735adfc08cff3a1c79054d92023a26ed624e3))
* **laundry:** guest laundry end to end — rate card, pickup to return, folio billing ([1d9f61b](https://github.com/Kamra-PMS/kamra-pms/commit/1d9f61bc963c2d31091a1327568cf0f1a35e43fb))
* **migrate:** vendor-aware CSV importers with dry-run preview (eZee / Cloudbeds / generic) ([dbfc459](https://github.com/Kamra-PMS/kamra-pms/commit/dbfc459099f2df8ce0a09dec3b770afbf609feb7))
* one Move panel for folio routing/splitting; party auto-split into rooms ([6317f40](https://github.com/Kamra-PMS/kamra-pms/commit/6317f4090ef44090a4492b2258c524c21ecfd4de))
* Operations SLA report - breach rate, resolve time, overdue queue ([ea87cc1](https://github.com/Kamra-PMS/kamra-pms/commit/ea87cc1ef964c1d7faa48524e385a30a75a80b9f))
* **pos:** area-wise table map, live temp tables, NC (complimentary) bills ([594129a](https://github.com/Kamra-PMS/kamra-pms/commit/594129a75bc7d7212a6b0b43ae113329b60f2703))
* **pos:** concurrent orders (running tabs), menu search, full-screen, per-outlet kitchen ([1a06086](https://github.com/Kamra-PMS/kamra-pms/commit/1a060866828051c72752e8a6b34439342271b3bd))
* **pos:** kitchen display + guest QR ordering ([5501f49](https://github.com/Kamra-PMS/kamra-pms/commit/5501f49b44eb4ff42b530391b00a398c348aab5d))
* **pos:** menu item photos upload directly (or paste a URL) ([07700ce](https://github.com/Kamra-PMS/kamra-pms/commit/07700cecf2868d53de742ab129914ae604d7b97a))
* **pos:** move POS into its own F&B app; add Menu & Outlets management screens ([2f47a5e](https://github.com/Kamra-PMS/kamra-pms/commit/2f47a5ed222ad55737682d2d130944a5509bb225))
* **pos:** restaurant POS - digital menu, captain ordering, KOT, room posting ([a17ad83](https://github.com/Kamra-PMS/kamra-pms/commit/a17ad83da17fc5db36c24dd36e4967f73f0fad82))
* **pos:** shared tables, split bills, temp tables, clearer new-order flow ([211e69e](https://github.com/Kamra-PMS/kamra-pms/commit/211e69e7461d4520dc155138fa46c1089771bc19))
* **pos:** table map, thermal KOT & bill printing, outlet settle, order types, voids ([435855a](https://github.com/Kamra-PMS/kamra-pms/commit/435855a19f46b75eeca68f40de2cb14ebf4ae3ec))
* **pos:** table reservations, cleaning state, self-healing deploys ([b55b33d](https://github.com/Kamra-PMS/kamra-pms/commit/b55b33d78c881c6dac334bafdb7c22438c4749c5))
* **pos:** three-column POS — delivery orders, table seats, recent bills, F-key shortcuts ([15c9dda](https://github.com/Kamra-PMS/kamra-pms/commit/15c9dda0db27ef218847cf5e41f79f6aabc935c1))
* **pos:** traverse running orders - prev/next arrows + scrollable tab strip ([bbb6bfc](https://github.com/Kamra-PMS/kamra-pms/commit/bbb6bfc415eca498163bebc56d4ef7513893869b))
* property + central (portfolio) dashboards by department ([f524d62](https://github.com/Kamra-PMS/kamra-pms/commit/f524d62bafa4a5b322bc001a6854e7b1bd97f946))
* **realtime:** live async updates on tickets, dashboard, activity, groups ([03e1dda](https://github.com/Kamra-PMS/kamra-pms/commit/03e1ddac54ff41e3b6eb06bf7cb7a9e3d5c31311))
* **realtime:** live kitchen display, POS tabs and housekeeping over the socket ([5761336](https://github.com/Kamra-PMS/kamra-pms/commit/576133691bd5dfebe38af9fe98e810ded38d56f2))
* **revenue:** tape-chart position with ETA/ETD, overbooking allowance, hurdle rates, GM briefing ([e81a928](https://github.com/Kamra-PMS/kamra-pms/commit/e81a9280fada5297533392fb9ebc4491a4b94691))
* room blocks - hold rooms out of sale for house use, VIP, maintenance ([e952940](https://github.com/Kamra-PMS/kamra-pms/commit/e952940b693322ef53652415b7e91f7d6bfe39f3))
* **seed:** operations demo data — tickets, shift handovers, live laundry ([7ccc730](https://github.com/Kamra-PMS/kamra-pms/commit/7ccc730e3d604604ad5df1a9cf3919f8b61754a6))
* **seed:** sample content across the demo - profile, today story, revenue tiers ([51059fd](https://github.com/Kamra-PMS/kamra-pms/commit/51059fd8f3319a4918e009312f8870e38ee063ea))
* venue calendar is now interactive - add, edit and search from the grid ([5281bbd](https://github.com/Kamra-PMS/kamra-pms/commit/5281bbd9db56c96b65fd09725f377ed500feecaa))


### Bug Fixes

* clear leftover agent-era copy from the UI ([ebaf62a](https://github.com/Kamra-PMS/kamra-pms/commit/ebaf62a0c97893940edc66317d763da6b3bc9367))
* de-duplicate Booking Engine section nav; link journey events to the reservation ([8d31eaf](https://github.com/Kamra-PMS/kamra-pms/commit/8d31eaf255fb4de57d053bdb6ee44d15c877fb76))
* **harness:** create the agent user without seed_rbac_v2's custom perm grants ([467c816](https://github.com/Kamra-PMS/kamra-pms/commit/467c8166ea9f5ee4bd29e0ab049b409f7db82413))
* **install:** don't seed partial agent perms at install - custom DocPerms replace standard ones ([77faf87](https://github.com/Kamra-PMS/kamra-pms/commit/77faf8761c4f9758935d1cdf1ad3662aad4950f8))
* issue-template config.yml was invalid YAML ([b83a391](https://github.com/Kamra-PMS/kamra-pms/commit/b83a391c5a1c83800c0ba0f08cdd8e3de5dd7280))
* Kamra favicon on Frappe-served pages; Revenue icon is no longer a pig ([21b0bd2](https://github.com/Kamra-PMS/kamra-pms/commit/21b0bd2611bd200a7e213d3a447d2a2cb0349249))
* move language (English/Arabic) into Settings &gt; Appearance, off the header ([6b6791a](https://github.com/Kamra-PMS/kamra-pms/commit/6b6791a4f9d9555eb05ec1d86b62c2ccb3dc750c))
* pin release-please to main - default branch is develop now ([764be73](https://github.com/Kamra-PMS/kamra-pms/commit/764be73d73f72eb61bfc98fa1f03a542bbba3975))
* **pos:** table tile layout — elapsed time no longer overlaps the name ([16567ab](https://github.com/Kamra-PMS/kamra-pms/commit/16567ab12da36a805545f45410230ef2991ac714))
* rooms can no longer sleep more guests than the room type allows ([b65bffc](https://github.com/Kamra-PMS/kamra-pms/commit/b65bffc8b70501891aee72e3d321cde1098acc16))
* **ux:** human error messages, offline resilience, graceful session handling ([3e867b2](https://github.com/Kamra-PMS/kamra-pms/commit/3e867b2cab22b3e2272cd59eb5ad81b496be2e76))

## [2.0.0] - 2026-07-08

### Added
- Booking Engine: a management app for the direct-booking page — hotel
  profile with driving directions and an embedded map, a photo gallery,
  house/pets/children/extra-bed policies, an FAQ list, and SEO fields (meta
  title/description, OG image, page slug). The public booking page now
  renders a gallery, a Policies & Rules card, a Location & Directions card,
  and an FAQ accordion, and its `<title>`/meta description/OG image come from
  the SEO fields when set.
- Revenue Reports: budget vs. actual with attainment %, and a contribution
  analysis by source / company / travel agent.
- Accounting export: download closed invoices as Tally, Zoho Books or ERPNext
  import files, with tax columns driven by the property's localization pack.
- Tape chart: room-type grouping and filter, guest-type badges (VIP,
  Corporate, Group, OTA), and an Hourly view for day-use bookings with
  planned check-in/out times.
- Preference-aware room allocation suggestions ("Auto-assign arrivals") on
  the tape chart, matching guest requests to room attributes.
- Self check-in now captures consent and an e-signature, producing a signed,
  paperless Guest Registration Card.
- A Void action on open folio charges — correct a mis-posted bill without
  split/transfer/allowance gymnastics.
- Localization seam: country packs decide tax rates and invoice fields;
  India ships as the reference pack.
- Kamra as an app suite (Front Desk, Housekeeping, Operations, Events &
  Groups, Revenue, Finance, Admin) with an app switcher and launcher.
- Marketplace: connect HeyKoala (voice/WhatsApp), bring your own AI
  (Claude over MCP, or an OpenAI key for the in-app Copilot chat).
- Realtime updates: Tape Chart, Today and the room board update live.
- Centralized cross-navigation: every reservation, company and group links
  to its billing, folios and guests.
- List screens: search, filter, pagination, date range, CSV export and a
  column picker across every resource list.
- Cashier PIN on money actions (per-user, property-togglable).
- Folio finance: allowances, part-settlement for long stays, and an invoice
  cancellation register.
- MICE: room blocks, pickup-aware inventory holds, Group Rooms Control.
- Copilot: streaming responses, markdown rendering, and a Connect tab for
  bringing your own Claude via MCP.
- Centralized auth (`/login` route, consistent 401/403 handling).

### Changed
- **Kamra is fully open** — removed all "Premium" tier labeling from the
  app switcher, launcher and marketplace. Every app ships included.
- The Copilot is a plain chat over governed tools, not a bundle of named
  personas.
- Marketplace AI section reframed as "Bring your own AI" (Claude/MCP, OpenAI
  key) and "AI on your phone lines" (HeyKoala).
- Food & beverage tax on posted charges is now computed server-side from the
  localization pack, rather than trusting the caller's supplied rate.

### Removed (⚠️ breaking)
- **Native seeded agents** (NOVA, IRA, TARA, ORION, MAYA) and the underlying
  `Agent`, `Agent Autonomy Rule`, `Agent Tool` and `Pending Agent Action`
  doctypes, the autonomy/approval gate, and the Approvals inbox.
  Kamra ships the governed tools, MCP access, RBAC and an audit log; the AI
  itself is brought in — your own Claude over MCP, or HeyKoala for
  voice/WhatsApp.
  **If you installed `v1.0.0` and configured agents, upgrading deletes that
  configuration and any pending-approval history on `bench migrate` — export
  anything you need first.**

### Fixed
- The public booking page's live availability/price search was silently
  failing for every real guest (403) because it depended on a staff-only,
  role-gated internal function. It now computes availability the same way
  without the role check, so `/book` shows real per-date quotes again.
- Copilot could mis-tax a food & beverage charge, double-post a charge, and
  claim it had notified housekeeping when no such tool existed. Tax now comes
  from the tax engine, the system prompt forbids claiming un-actioned work,
  and a real ticket-raising tool reaches housekeeping/maintenance.
- Assorted Copilot UX: page jumped on click, markdown headings didn't render,
  "who checked out / arrived" lookups failed to resolve reservations.

## [1.0.0] - 2026-07-05
Initial public release.
