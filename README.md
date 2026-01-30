<p align="center">
  <strong>travelrecap.my</strong>
</p>
<p align="center">
  Your travel recap from Google Maps Timeline — 100% client-side, private, and open source.
</p>

<p align="center">
  <a href="https://github.com/imarinzone/travelrecap.my/blob/main/LICENSE"><img src="https://img.shields.io/github/license/imarinzone/travelrecap.my?color=blue" alt="License: MIT"></a>
  <a href="https://github.com/imarinzone/travelrecap.my"><img src="https://img.shields.io/github/package-json/v/imarinzone/travelrecap.my?label=version" alt="Version"></a>
  <a href="https://github.com/imarinzone/travelrecap.my"><img src="https://img.shields.io/github/languages/count/imarinzone/travelrecap.my" alt="Languages"></a>
  <a href="https://github.com/imarinzone/travelrecap.my"><img src="https://img.shields.io/github/repo-size/imarinzone/travelrecap.my" alt="Repo size"></a>
  <a href="https://github.com/imarinzone/travelrecap.my/issues"><img src="https://img.shields.io/github/issues/imarinzone/travelrecap.my" alt="Issues"></a>
</p>

---

A single-page static site that turns your **Google Takeout timeline** into a typography-first story: scroll-fade animations, vector infographics, and an interactive map — all running in your browser. No data is sent to any server.

## Table of contents

- [Features](#-features)
- [Quick start](#-quick-start)
- [Usage](#-usage)
- [Project structure](#-project-structure)
- [Development](#-development)
- [Deployment](#-deployment)
- [Privacy & design](#-privacy--design)
- [Tech stack](#-tech-stack)
- [Contributing](#-contributing)
- [License](#-license)

---

## Features

| | |
|---|---|
| **Typography-first layout** | Large, bold stats that tell your travel story as you scroll |
| **Scroll animations** | Content fades in from background to foreground with `IntersectionObserver` |
| **Vector infographics** | Subtle globe and journey-line illustrations |
| **Travel stats** | Total distance, unique places, countries visited, check-ins |
| **Time & records** | Moving vs stationary time, personal records |
| **Environmental impact** | Estimated carbon footprint and tree offset |
| **Interactive map** | Visualize timeline visits by uploading your JSON |
| **Privacy-first** | 100% client-side; no server uploads |

---

## Quick start

```bash
git clone https://github.com/imarinzone/travelrecap.my.git
cd travelrecap.my
npm install
npm run build          # optional: generates tailwind.css (or use CDN fallback)
npx serve
```

Open **http://localhost:3000** (or the port shown). No build step is required for styles — the app falls back to the Tailwind CDN if `tailwind.css` is missing.

---

## Usage

### Visualizing your data

1. Export your timeline from [Google Takeout](https://takeout.google.com/) (JSON).
2. Open the app in your browser.
3. Click **Choose File** in “Upload Your Timeline Data” and select your `GoogleTimeline.json`.
4. The map and stats will update with your locations and metrics.

### Offline country lookup

Country names are resolved offline using `data/countries.geojson` (point-in-polygon, no APIs). The file is committed; to update it, replace it with a [world countries GeoJSON](https://github.com/datasets/geo-countries) and save as `data/countries.geojson`.

---

## Project structure

```
travelrecap.my/
├── index.html           # Single-page app
├── script.js            # UI, map, and DOM logic
├── timeline-utils.js    # Parsing, stats, geo helpers
├── tailwind.css         # Built CSS (npm run build; gitignored)
├── src/tailwind.css     # Tailwind source + custom animations
├── vercel.json          # Build command + headers
├── data/
│   └── countries.geojson
├── components/
├── tests/
└── README.md
```

---

## Development

```bash
npm install
npm test                 # Jest tests for timeline-utils
npm run build            # Build Tailwind once
npm run watch:css        # Watch Tailwind while developing
```

- **Tests**: Core logic lives in `timeline-utils.js`; tests are in `tests/`.
- **Tailwind**: Use `npm run build` or `npm run watch:css` for the built styles, or rely on the CDN fallback when `tailwind.css` is missing.
- **Localhost**: Vercel Speed Insights is disabled on localhost to keep the console clean.

---

## Deployment

Optimized for [Vercel](https://vercel.com):

- **Build**: `npm run build` (Tailwind → `tailwind.css`).
- **Headers**: Custom `Permissions-Policy` in `vercel.json` (no `browsing-topics`).
- **Output**: Static files from repo root.

Push to your connected repo; no extra config needed.

---

## Privacy & design

- **Client-only**: Your `GoogleTimeline.json` is parsed in the browser. Nothing is uploaded.
- **Storytelling UI**: Large type, vertical scroll, fade-in sections, SVG backgrounds, and dark mode support.

---

## Tech stack

| Category | Tools |
|----------|--------|
| Markup & styling | HTML5, Tailwind CSS (built in prod, CDN fallback locally) |
| Logic | Vanilla JavaScript |
| Maps | Leaflet.js, CartoDB tiles |
| Animations | IntersectionObserver, CSS keyframes |
| Testing | Jest |

---

## Contributing

Contributions are welcome.

1. Open an [issue](https://github.com/imarinzone/travelrecap.my/issues) for bugs or ideas.
2. Fork the repo, create a branch, and open a [pull request](https://github.com/imarinzone/travelrecap.my/pulls).
3. Run `npm test` before submitting.

---

## License

This project is licensed under the **MIT License** — see the [LICENSE](LICENSE) file for details.
