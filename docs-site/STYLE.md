# Writing Kamra docs

How pages on kamrapms.com/docs are written. Read this before adding or
changing a page. (This file is not published; VitePress skips it via
`srcExclude`.)

## Who reads what

- **Module guides** (Front desk, Reservations, Billing, Housekeeping, F&B,
  Banquets, Revenue, Night audit, Reports, Booking engine, Settings) are for
  hotel staff and owners. No code, no jargon. They say how to do a job.
- **Self-hosting, AI & MCP, API** pages are for whoever installs and
  integrates. Commands and code are fine there.

## Rules

1. **True to the code.** Every button name, menu path, default and rule must
   match the app as it is. Check the screen (`frontend/src/screens/...`)
   and the endpoint (`kamra/*.py`) before you write it. Don't describe a
   feature that isn't merged. If something is a limit, say so.
2. **Tasks, not tours.** Headings are things people do: "Check a guest in",
   "Move a guest to another room". Not "Powerful check-in".
3. **Plain words.** Short sentences, second person, present tense. No
   marketing words: powerful, seamless, effortless, robust, cutting-edge,
   world-class, leverage, unlock, streamline, revolutionise.
4. **Name things the way the screen does.** Bold the exact label:
   **Send to kitchen**, **Settings → F&B**. Use → for menu paths.
5. **Show, then tell.** Each page has a screenshot near the top, one image
   per screen a task uses, and a GIF for the one or two flows that are
   easier to watch than read. Don't add an image that shows nothing new.
6. **Numbers and money** are examples from the sample hotel. Don't promise
   a tax rate or currency; those come from the country pack
   ([Country setup](/country-setup)).
7. **Short.** If a section needs more than one screen of text, it's two
   tasks.

## Page shape (module guides)

```md
# F&B — POS and kitchen

One or two sentences: what this part of Kamra is for and who uses it
(the roles that see it).

![The restaurant POS with the table map and a running bill](/img/fnb/pos.png)

## Before you start
What has to be set up once, with where to do it. Numbered steps.

## <A task> (one H2 per everyday task)
1. Numbered steps, each one action.
2. ...

![Alt text that says what the picture shows](/img/fnb/<name>.png)

## Settings
| Setting | Where | Default | What it does |

## Good to know
- Rules Kamra enforces (and why), limits, edge cases.

## Troubleshooting
**The KOT didn't print.** What to check, in order.

## For developers
One paragraph: the MCP tools and API endpoints behind this module, linked
to [MCP tools](/mcp-tools) and the [API reference](/api-reference).
```

## Images

- Captured from a real Kamra with the sample hotel by the scripts in
  `frontend/scripts/docs-shots/` (Playwright + ffmpeg). Re-run the script
  for a page when its screens change; don't edit images by hand.
- Files live in `docs-site/public/img/<page>/`. Reference them as
  `/img/<page>/<name>.png` (VitePress adds the `/docs/` base).
- 1440×900 viewport. Crop to the part that matters (a card, a dialog) with
  `shot(page, name, { locator })` rather than showing the whole app.
- GIFs: 5–15 s, 960 px wide, 8 fps, under ~2 MB. One flow per GIF.
- Alt text describes what the image shows, in a sentence.
- No real guest data, no API keys, no passwords in any image.
