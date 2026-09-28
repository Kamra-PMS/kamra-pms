# Country setup & Saudi e-invoicing (ZATCA)

Kamra is one product for every country. The **country** you pick when you
create the property selects its *localization pack*, and the pack decides:

| | What it sets |
| --- | --- |
| Money | currency, number format, tax name (GST, VAT, SST, PB1…) and the tax-ID label on invoices |
| Front desk | the **ID documents** the desk and guest self check-in accept, the **ways to pay** offered at the counter, POS and till |
| Levies | the name of the per-night room levy (e.g. *Municipality fee*) |
| Guests | the default nationality, and the data-protection authority named in the privacy notice |
| Invoices | the invoice title and, where the law requires it, e-invoicing (Saudi Arabia: ZATCA) |

Packs today: **India, Indonesia, Malaysia, Saudi Arabia, Thailand, United
Arab Emirates**. Any other country runs on a simple flat-tax pack with the
currency you enter.

## Choosing the country

- **New property**: the setup wizard (`/kamra/setup`) asks for the country
  first and fills in the currency and time zone. It pre-selects the country
  from your computer's clock; check it before you continue.
- **Existing property**: *Settings → Property → Country* and *Currency*.
  Changing the country changes tax labels, ID types and payment methods
  immediately; bills already issued are not rewritten.

| Country | ID types | Payment methods |
| --- | --- | --- |
| India | Aadhaar, Passport, Driving License, Voter ID, PAN | Cash, Card, UPI, Bank Transfer |
| Saudi Arabia | National ID, Iqama, Passport, GCC ID | Cash, Card (incl. mada), Bank Transfer |
| UAE | Emirates ID, Passport, GCC ID, Driving License | Cash, Card, Bank Transfer |
| Indonesia | KTP, Passport, KITAS, Driving License | Cash, Card (incl. QRIS), Bank Transfer |
| Thailand | Thai ID Card, Passport, Driving License | Cash, Card, Bank Transfer |
| Malaysia | MyKad, Passport, Driving License | Cash, Card, Bank Transfer |
| Other | Passport, National ID, Driving License | Cash, Card, Bank Transfer |

## Room levy (municipality fee, city tax)

*Settings → Stay, tax & privacy*: **Room levy name**, **Room levy %** and
whether tax applies to it. When the % is above zero the levy is included in
every quote and posted as its own line with each room night, so the invoice
shows it and the ledger books it apart from room revenue. Saudi Arabia and
the UAE pre-fill the name *Municipality fee*; set the rate your
municipality charges.

## Saudi Arabia: ZATCA e-invoicing

### What Kamra does (Phase 1 — generation)

For every **invoice** (a settled folio), **credit note** (a cancelled
invoice — ZATCA does not allow deleting one) and **paid restaurant bill**,
Kamra creates a *ZATCA Invoice* record with:

- a UUID and the property's invoice counter (**ICV**), and the previous
  invoice's hash (**PIH**), so every document is chained to the one before;
- the **UBL 2.1 XML** — *simplified* for guests, *standard* (B2B) when the
  bill goes to a company with a VAT number;
- the **ZATCA invoice hash**;
- the **QR code** (seller name, VAT number, time, total, VAT), printed on
  the invoice and the thermal restaurant bill with the Arabic title
  (*فاتورة ضريبية مبسطة*).

Records are append-only. Finance can download any document's XML from the
API (`zatca_invoice_xml`).

### Setting it up

1. Set the property's country to **Saudi Arabia** and its **VAT No.**
   (15 digits, starting and ending with 3).
2. Open *Settings → ZATCA e-invoicing* (shown for Saudi properties). Kamra
   creates it from the property on first use. Fill in the details exactly
   as registered: seller name, Commercial Registration (CRN), building
   number (4 digits), street, district, city, postal code (5 digits).
3. The banner at the top turns green — *ZATCA Phase 1 ready* — when
   nothing is missing. It also shows how many documents have been issued
   and the last ICV.

Closing a bill never waits on ZATCA: if a record cannot be generated the
error is logged and the desk carries on.

### Phase 2 (integration) — what is still to come

The XML, hash chain and settings (environment, EGS serial, CSID, private
key) are in place. Still to build before a property in a Phase 2 wave can
go live: onboarding the EGS unit (CSR + the OTP from the FATOORA portal →
compliance and production CSIDs), XAdES signing, the QR's Phase 2 tags
(hash, signature, public key), and calling ZATCA's **reporting**
(simplified) and **clearance** (standard) APIs. Until then records stay
*Generated*.

## Guest self check-in in Arabic

The pre-arrival check-in page follows the guest's phone language and has
an **English / العربية** switch; the privacy notice names the country's
regulator (SDAIA in Saudi Arabia) and its guest-registration system
(Shomoos).
