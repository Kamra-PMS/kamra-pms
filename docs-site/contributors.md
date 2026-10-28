# Contributors

Kamra is open source and shaped by the people who run hotels on it. Thank
you to everyone who has written code, reported an issue from the front
desk, or disclosed a security problem responsibly.

## Code

| Contributor | What they built |
| --- | --- |
| [@Kruthikagowda12](https://github.com/Kruthikagowda12) | AioSell channel-manager adapter and fixes (#40, #46, #52), housekeeping proof media and room swap / upgrade (#74), phone validation (#69), season scoping (#80), property / booking flow (#22), per-head small-group rates and weekend / weekday guardrails (#162) |
| [@Mohammed-Muneef](https://github.com/Mohammed-Muneef) | Laundry, kitchen display v2, inventory & recipes, menu import, ID-document hardening |
| [@faresalslahi-collab](https://github.com/faresalslahi-collab) | Booking guest and room summary (#83) |
| [@ShaikhAmerPasha](https://github.com/ShaikhAmerPasha) | Saved bookings keep their voucher after it expires or hits its limit (reported in #142, fixed in #143); folio charges refuse zero or minus amounts and tax rates outside the country's list (reported in #146, fixed in #147); the bill screen's Void button asks for the reason the ledger needs (reported in #160, fixed in #161) |
| [@ernestoruiz89](https://github.com/ernestoruiz89) | Spanish localization and menu navigation fixes (#320, #324), international guest phone prefixes (#345, #360), the chat assistant using the property's currency (#368) |
| [@SandroG1977](https://github.com/SandroG1977) | Brazil country pack (ISS, BRL, CNPJ/CPF, NFS-e) (#378); Portuguese (pt-BR) staff UI (#377, landed via #383) |
| [@caseylee-TC](https://github.com/caseylee-TC) | Step-by-step tutorial for writing a country pack ([#362](https://github.com/Kamra-PMS/kamra-pms/pull/362), fixes [#258](https://github.com/Kamra-PMS/kamra-pms/issues/258)) |

## Issues from the front desk

| Reporter | What it led to |
| --- | --- |
| [@lhertig](https://github.com/lhertig) | Property-currency folio payments (#341), `max_total_occupants` on mixed adult/child bookings (#342), pre-arrival advance refunds releasing Deposit and reducing `advance_paid` (#343), concurrent booking `tabSeries` deadlock retries (#344) |
| [@faresalslahi-collab](https://github.com/faresalslahi-collab) (Sarawat Park Hotel & Resort) | One-screen walk-in (#97), the Saudi Arabia pack and ZATCA e-invoicing; Arab-world dial codes (#98); ERPNext Purchase Invoices working alongside Kamra's kitchen ledger (#131) |
| [@atomic-glitch](https://github.com/atomic-glitch) | Housekeeping Room Board and role checks (#99), room change from the reservation and GRC (#113), deposits before arrival (#114) |
| [@ali-qa-sudo](https://github.com/ali-qa-sudo) | Role-aware Walk-in / New booking buttons (#120) |
| [@omar99elnemr](https://github.com/omar99elnemr) | Checkout refused until the bill is settled (#132) |
| [@Syzygy2048](https://github.com/Syzygy2048) | Current OpenAI models in the assistant (#23) |

## Security

| Reporter | Advisory |
| --- | --- |
| **[@archnexus707](https://github.com/archnexus707)** (first reporter) | [GHSA-6cr2](https://github.com/Kamra-PMS/kamra-pms/security/advisories/GHSA-6cr2-jm8f-6jrx): cross-property access, fixed in 2.6.5 |
| [@kta1kri](https://github.com/kta1kri) | [GHSA-5hcx](https://github.com/Kamra-PMS/kamra-pms/security/advisories/GHSA-5hcx-h257-qr5j): unauthenticated webhooks; independent report of GHSA-6cr2. Both fixed in 2.6.5 |

## Join in

Open an issue from your front desk, pick up a `good first issue`, or send a
PR - see [CONTRIBUTING.md](https://github.com/Kamra-PMS/kamra-pms/blob/develop/CONTRIBUTING.md).
Security issues go through [private advisories](https://github.com/Kamra-PMS/kamra-pms/security/advisories/new).
