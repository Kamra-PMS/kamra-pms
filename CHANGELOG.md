# Changelog

All notable changes to Kamra PMS are documented here. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions follow
[Semantic Versioning](https://semver.org/) — MAJOR for anything that breaks an
existing install on upgrade (removed doctypes, removed API endpoints),
MINOR for new features, PATCH for fixes.

## [2.5.0](https://github.com/Kamra-PMS/kamra-pms/compare/v2.4.0...v2.5.0) (2026-08-13)


### Features

* **banquet:** floor plans, hall deals, pre-costing and a stepped flow ([94b2a11](https://github.com/Kamra-PMS/kamra-pms/commit/94b2a1122d46f9b359d8756c7d31a4e08dfa6e35))
* **banquet:** function management from enquiry to close-out ([21a8642](https://github.com/Kamra-PMS/kamra-pms/commit/21a8642aeccadbe212d1745c084a790ac09246ac))
* **banquet:** proper document templates - logo, numbers, GST compliance ([385e8c8](https://github.com/Kamra-PMS/kamra-pms/commit/385e8c866fe4d22edf31788de883cbe44acad429))
* **booking:** Airbnb-style property catalog, villa page, and listing detail ([2f79a2b](https://github.com/Kamra-PMS/kamra-pms/commit/2f79a2bc17f7ce559241daa1120024973e3c4b08))
* **booking:** Instant path with holds, locks, and idempotency ([0c55aa2](https://github.com/Kamra-PMS/kamra-pms/commit/0c55aa28d7638a0ddc067b44e5ec22201a2a7fd7))
* **booking:** per-villa location on Room Type for multi-site portfolios ([18f57fa](https://github.com/Kamra-PMS/kamra-pms/commit/18f57fa75179abfe4fe94df40138397b57b6c046))
* **booking:** public /stay listing and site slugs for STR catalogs ([f99c5b8](https://github.com/Kamra-PMS/kamra-pms/commit/f99c5b8d8abe0af9085b29bd443da1b262ea860c))
* **cloud:** per-property modules and one-command tenant provisioning ([ce6f8a2](https://github.com/Kamra-PMS/kamra-pms/commit/ce6f8a225257c57746285270d2b91cf8148ca6a2))
* enhance property management and booking flow ([6f877e7](https://github.com/Kamra-PMS/kamra-pms/commit/6f877e780fad3bdf16a7dfbd70712c7a53350c40))
* Enhance property management and booking flow ([7138cb3](https://github.com/Kamra-PMS/kamra-pms/commit/7138cb37783f5061ca073595707c6c4fc44d2f18))
* **setup:** property_kind preset and STR wizard branch ([132e34c](https://github.com/Kamra-PMS/kamra-pms/commit/132e34cbf8e796a402f9b01c4096872f16c7657f))
* **siu:** sellable units and availability SSOT for STR ([31e9403](https://github.com/Kamra-PMS/kamra-pms/commit/31e940323104a5cbfb16d63f412e01d3247f7dfd))
* sortable columns on manager flash trend table ([103a422](https://github.com/Kamra-PMS/kamra-pms/commit/103a42280e86ce40ef261883145c31fb7008cda8))
* **str:** quote ledger, deposits, turnover, and access gates ([265e2ae](https://github.com/Kamra-PMS/kamra-pms/commit/265e2ae73acc2bd4cbd8aa1913018a203948eeb0))


### Bug Fixes

* **assistant:** GPT-5.6 luna/terra/sol tool calling on chat completions ([84c8bf9](https://github.com/Kamra-PMS/kamra-pms/commit/84c8bf972be3d9128b6789319a925693a0bf7fae)), closes [#23](https://github.com/Kamra-PMS/kamra-pms/issues/23)
* **banquet:** one door to create a function, and a real dish editor ([e3ca25b](https://github.com/Kamra-PMS/kamra-pms/commit/e3ca25b9d6744709f75643e3bf3fc6425e3b2502))
* **booking:** always show country code on public phone numbers ([0016525](https://github.com/Kamra-PMS/kamra-pms/commit/001652536d2ee4c1054d788e4294f9f11ee504d0))
* **booking:** fill /book hero with showcase photo or brand accent ([abb7e3d](https://github.com/Kamra-PMS/kamra-pms/commit/abb7e3d4c7367500b4d35b414951c55ebdfb662b))
* **booking:** persist uploaded images automatically ([737b4c5](https://github.com/Kamra-PMS/kamra-pms/commit/737b4c5d9ea8da6d0a50c5db7b01cdb9187148b9))
* **booking:** real check-in/out date range + explicit search CTA ([ea7e6e0](https://github.com/Kamra-PMS/kamra-pms/commit/ea7e6e0e12e5497f93f1066594bdbf609907054b))
* **booking:** resolve tenant property for public booking engine ([2acc59c](https://github.com/Kamra-PMS/kamra-pms/commit/2acc59c491b72452d4126aaae82a40568a84e70f))
* close Dependabot CVEs and Code Quality findings ([7d51e08](https://github.com/Kamra-PMS/kamra-pms/commit/7d51e08b640808f9c92e92ce7a387d541d4ee243))
* close Dependabot CVEs and GitHub Code Quality findings ([c0d6cdc](https://github.com/Kamra-PMS/kamra-pms/commit/c0d6cdcf512255fe81abb47eed18a4dfe3fc82d8))
* **cloud:** admin cannot be switched off, and module-gate tests ([41734be](https://github.com/Kamra-PMS/kamra-pms/commit/41734be30e5ff2b2b3ce84227d3973fa1399ab03))
* **eval:** guest merge + SIU room pick for booking harness ([9101ce5](https://github.com/Kamra-PMS/kamra-pms/commit/9101ce509628ddd5f95a96b6b9ffd7308dcc6df5))
* **eval:** Venue Booking merge uses customer field ([bbd310d](https://github.com/Kamra-PMS/kamra-pms/commit/bbd310d9a17631d25567f20161f96c4cda6136ef))
* **eval:** Venue Booking merge uses customer field ([5028d10](https://github.com/Kamra-PMS/kamra-pms/commit/5028d10e68a5c1edd2c890f9c6578a8c549f1fc5))
* **pos:** KOT daily sequence uses site-local today ([8e58c3b](https://github.com/Kamra-PMS/kamra-pms/commit/8e58c3b299b38db4778abef36e0f907fc2580f9b))
* **provision:** support implicit SSL for SMTP on port 465 ([d8bfaa8](https://github.com/Kamra-PMS/kamra-pms/commit/d8bfaa8b284932a3b53faa46d33ead51fd108a11))

## [Unreleased]

**2.5 — Short-term rentals.** Kamra is no longer hotel-only. A property can be
a hotel *or* a short-term rental portfolio: several villas at different
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

### Bug Fixes

* Copilot works with current OpenAI models (`gpt-5.6-luna`, `gpt-5.6-terra`, `gpt-5.6-sol`) — Chat Completions + tools no longer 400 ([#23](https://github.com/Kamra-PMS/kamra-pms/issues/23))
* Public phone numbers: a 10-digit Indian mobile starting with `91` is no longer stripped to eight digits
* Public booking engine resolves the tenant's property instead of a hardcoded demo name

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
