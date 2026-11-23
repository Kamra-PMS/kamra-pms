# Usage reporting

Kamra sends one small, anonymous heartbeat a day to kamrapms.com, so we
can count how many hotels run Kamra. It is on by default, and you can
turn it off with one click. Registering your property is a separate
choice, and it is off until you opt in.

## What the heartbeat sends

This is the whole payload. **Settings → Usage reporting → See exactly
what we send** shows the values for your install.

```json
{
  "install_id": "3f2b9c1e-7a4d-4e0b-9c55-1d2e3f4a5b6c",
  "kamra_version": "2.8.0",
  "frappe_version": "16.0.0",
  "rooms": "11-50",
  "country": "India",
  "deployment": "docker",
  "checkins_last_7_days": true
}
```

| Field | What it is |
|---|---|
| `install_id` | A random ID, made once for this install. It does not come from your site name or domain. |
| `kamra_version`, `frappe_version` | The versions you run. |
| `rooms` | A size bucket for all rooms on the install: `0`, `1-10`, `11-50`, `51-200` or `200+`. |
| `country` | The country most of your properties are set to. |
| `deployment` | `docker` or `bench`. |
| `checkins_last_7_days` | `true` if any guest checked in during the last 7 days. |

It never sends guest data, your hotel's name, your domain, revenue or
email addresses. kamrapms.com does not store IP addresses. An install
counts as **live** when it has had check-ins in the last 30 days.

The heartbeat runs at 05:35 server time. It waits at most 5 seconds and
fails silently, so it never slows down or blocks Kamra. Kamra uses no
third-party analytics SDK.

## Turn it off

Do any one of these:

- **Settings → Usage reporting**: switch off **Anonymous usage heartbeat**.
- In the environment (good for Docker and CI): `KAMRA_TELEMETRY=0`, or
  `DO_NOT_TRACK=1`.
- In site config: `bench --site your-site set-config kamra_telemetry 0`.

The environment and site config settings win over the Settings switch.

## Register your property (optional)

You can tell us who you are in the setup wizard or in **Settings → Usage
reporting**. You enter the property name, city, country, room count and
a contact email. We name your hotel on kamrapms.com only if you tick
**List us on kamrapms.com as a Kamra property**.

You can change the registration or remove it at any time. **Remove
registration** asks kamrapms.com to delete it. If kamrapms.com can't be
reached, Kamra keeps the registration and you can try again.
