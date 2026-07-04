# Listing Kamra on the Frappe Cloud Marketplace

The [Marketplace](https://cloud.frappe.io/marketplace) is where Frappe
Cloud users one-click-install apps — our biggest distribution channel,
plus revenue share for free open-source apps.

## Prerequisites

- Public GitHub repo (this one, once flipped public) with README + LICENSE
- App installs cleanly on a supported Frappe version (ours: v16) — CI
  already proves this
- A Frappe Cloud account (team) at https://frappecloud.com

## Steps

1. **Become a developer**: Frappe Cloud dashboard → enable Developer mode
   (Settings → Developer).
2. **Add the app**: Dashboard → **Apps → Add App** → connect the GitHub
   repo (`Kamra-PMS/kamra-pms`), pick the `main` branch and Frappe
   version compatibility (v16).
3. **Create the listing**: title, one-line pitch, description (reuse the
   README manifesto), category (Hospitality), logo
   (`branding/png/kamra-mark-512.png`), screenshots, support/website
   links.
4. **Publish for review** — the Frappe team validates that the app
   installs and the listing meets guidelines
   ([docs](https://docs.frappe.io/cloud/marketplace)). Fix feedback,
   resubmit.
5. **After approval**: users install Kamra on any Frappe Cloud site in
   one click. Keep `main` releasable — Marketplace installs track your
   branch releases.

## Monetization options

- Keep the app **free** (our model) and opt into the
  [revenue-sharing program](https://frappe.io/blog/announcements/revenue-sharing-with-3rd-party-apps-on-frappe-cloud-marketplace)
  — Frappe shares 25% of hosting top-line with app developers, paid
  quarterly.
- Paid plans per app are also supported (up to 3 monthly tiers) — not our
  strategy for the core, but available for future add-ons.

## Checklist before submitting

- [ ] Repo public, AGPL LICENSE present
- [ ] README with screenshots
- [ ] `required_apps` declared (payments) — Marketplace resolves them
- [ ] Fresh-install test green in CI
- [ ] Support email / issue tracker linked
