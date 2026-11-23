# Run Kamra on a box at the hotel

For hotels where the internet drops often. Kamra runs on a small computer
on the hotel's own network, so the front desk, housekeeping and billing
keep working when the line to the outside is down. Only the parts that
need the internet wait: OTA bookings, online payments, email and WhatsApp.

## What to buy

| Hotel | Box | Notes |
| --- | --- | --- |
| Up to 30 rooms | Mini PC, 4 cores, 8 GB RAM, 256 GB SSD | An Intel N100-class mini PC is enough |
| 30 to 100 rooms, POS | 4 to 8 cores, 16 GB RAM, 512 GB SSD | |
| More than one property | Use a cloud server instead | See [Self-hosting](/self-hosting/) |

Also buy:

- A **UPS** for the box and the network switch. A power cut that corrupts
  the database is worse than a slow line.
- A **wired** connection from the box to the router. Desks and phones can
  use Wi-Fi.
- An **external disk** or a cloud bucket for backups (see below).

Run Ubuntu 24.04 LTS. Set the box's IP address to a fixed one in the
router (a DHCP reservation), for example `192.168.1.20`.

## Install

Install with the [Docker quickstart](/quickstart) on the box:

```bash
curl -fsSL https://raw.githubusercontent.com/Kamra-PMS/kamra-pms/main/deploy/install.sh | KAMRA_PULL=1 bash
```

`KAMRA_PULL=1` downloads the ready-made image instead of building it,
which matters on a slow line. For the site name, use a name staff can
reach on the hotel network, for example `pms.hotel.local`, and add it to
the router's DNS (or each computer's hosts file) pointing at the box.

Staff then open `http://pms.hotel.local/kamra` from any desk computer or
phone on the hotel Wi-Fi.

## When the internet is down

Nothing changes for the desk: check-in, check-out, room status, folios,
POS and night audit all run on the box.

What waits for the line to come back:

- **Channel manager.** Changes to availability and rates are queued and
  sent when the connection returns (Revenue → Channel Manager shows
  **Changes waiting**). The nightly sweep at 06:20 sends anything a
  trigger missed. OTA bookings made during the outage reach Kamra when
  the channel manager can deliver them again; check the channel
  manager's extranet for anything urgent.
- **Online payments, email, WhatsApp and the AI agent.** They need the
  internet. Take card or cash at the desk meanwhile.

If the **box itself** goes down (power, a restart), staff screens keep
the last copy of **Today**, arrivals and the **room board** for viewing,
marked with the time it was synced. A housekeeping status change made
then is kept and sent when the box answers again; if someone changed
that room in the meantime, the change is not applied and the screen
says so. Money actions never run offline.

## Reach the box from outside (optional)

OTA booking webhooks, the guest booking engine and online payments need
the box to be reachable from the internet:

- A **static IP** from your internet provider with port 443 forwarded
  to the box, and a public name (for example `pms.yourhotel.com`) with a
  certificate, or
- A **tunnel** (for example Cloudflare Tunnel) from the box, which needs
  no open ports.

Without either, run Kamra for staff only and keep online bookings in the
channel manager's own tools.

## Backups

The box is a single computer, so back it up off the box every night:

```bash
# on the box, as a nightly root cron job
docker compose -p kamra exec -T backend bench --site all backup --with-files
```

The backups land in `sites/<site>/private/backups` inside the backend
container (`docker compose -p kamra exec backend ls sites/*/private/backups`
lists them). Copy them to the external disk and, when the line is up, to
a cloud bucket. Test a restore on another computer once a
quarter: a backup you have never restored is a guess.

## Updates

Update outside busy hours: `sudo /opt/kamra/install.sh update` takes a
backup first and stops if it fails. See
[Updating](/self-hosting/#updating-docker-install).
