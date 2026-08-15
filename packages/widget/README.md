# Shiplog widget

A zero-dependency, single-file embeddable **“What’s new”** widget. Drop one script
tag into your product and users get an in-app changelog popover with an unread
badge, backed by your project’s public feed.

## Embed

```html
<script
  src="https://your-shiplog-host/widget.js"
  data-key="YOUR_PROJECT_PUBLIC_KEY"
  async
></script>
```

That’s it. It renders a floating launcher, fetches the feed, and shows unread
counts. Find your **public key** in the dashboard (it’s the `/c/<public-key>`
changelog URL, and it is not a secret).

## Options

| Attribute | Required | Default | What it does |
|---|---|---|---|
| `data-key` | ✅ | — | Project public key |
| `data-api` | — | script’s origin | API origin, if the script is served elsewhere |
| `data-accent` | — | `#6366f1` | Brand color for the launcher and links |
| `data-position` | — | `bottom-right` | `bottom-right` or `bottom-left` |
| `data-trigger` | — | — | CSS selector of **your own** element to open the panel from. When set, the floating launcher is not rendered. |

### Use your own button

```html
<button id="changelog">What’s new</button>
<script src="https://your-shiplog-host/widget.js"
        data-key="YOUR_PUBLIC_KEY" data-trigger="#changelog" async></script>
```

## How it works

- Fetches `GET {api}/api/v1/widget/{key}/feed` (Redis-cached, CORS-open).
- **Unread badge**: compares each release’s `publishedAt` to the newest one you’ve
  opened, stored in `localStorage` under `shiplog:{key}:seen`.
- **View tracking**: on open, fires `POST .../view/{releaseId}` for the newest
  release (fire-and-forget).
- Everything lives in a **Shadow DOM**, so the host page’s CSS can’t affect the
  widget and the widget can’t affect the host. Dark mode follows the OS setting.
- `bodyHtml` is sanitized server-side (nh3 allowlist) at write time, so it’s
  injected verbatim.

## Local demo

With the API running on `:8000` and a published release in the demo project:

```bash
# serve this folder over http (file:// works too but http is cleaner)
cd packages/widget && python3 -m http.server 8080
# open http://localhost:8080/demo.html
```

The `src` and `data-key` in [`demo.html`](./demo.html) already point at the local
API and the demo project.
