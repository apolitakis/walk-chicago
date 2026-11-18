# Walk Chicago — notes for Claude

GPS-triggered audio walking tours of Chicago (plus Oak Park) for Alex's phone: 22 tours, 144 stops, ~59.6k words (~6 h), plus optional "Go deeper" chapters per stop (about twice the base narration; being written in Nov 2026). It is the sister app of Walk NYC (`apolitakis/walk-nyc`) and started from its code on 2026-11-18, so the two repos share almost all of their code: a fix to `index.html`, the Pages Functions, `voices/` or `ios/` usually belongs in both.

## Where things live

| What | Where | Updated when |
|---|---|---|
| Source of truth | this repo, `apolitakis/walk-chicago` | every change |
| Public site (and what the iOS app loads) | Cloudflare Pages project `walk-chicago` → `https://walk-chicago.pages.dev` (from `hosting/cloudflare/`) | **only when Alex says "ship"** |
| Recorded narration | Cloudflare R2 bucket `walk-chicago-audio`, served at `/audio/*` by `functions/audio/[[path]].js` | after re-rendering audio (see SHIPPING.md) |
| Feedback notes | Cloudflare KV namespace `walk-chicago-feedback` (id `b27b2c91d739401da8d7f750f06c5aa2`), bound as `FEEDBACK`, written by `functions/api/feedback.js`; read with `scripts/read_feedback.py` | live, from the app |
| Audio rendering | Alex's A40 workstation (`alex@192.168.1.196`), `~/lab/walk-chicago-voices` (same setup as `~/lab/walk-nyc-voices`) | when narration text changes |
| iPhone app | `ios/`: Capacitor wrapper, bundle id `com.apolitakis.walkchicago`, TestFlight steps in `ios/TESTFLIGHT.md` | native changes only; web changes arrive with each ship |

## Layout

- `content/NN-<tour>.txt` — narration source, one file per tour (format below). **Edit text here, never in tours.json.** Files are numbered in a walking order: Downtown, North Side, West and Northwest Sides, South Side, then Oak Park.
- `content/deeper/NN-<tour>.txt` — "Go deeper" chapters for that tour's stops, same file name as the tour (format below).
- `build.py` — `python3 build.py` regenerates `hosting/cloudflare/public/tours.json` and `voices/tracks.json`, checks the deeper files against the tours, and prints word counts.
- `hosting/cloudflare/public/` — the app: one `index.html` (vanilla JS, no build step), `sw.js` (offline shell; skips /audio and /api), icons, manifest, `privacy.html`.
- `hosting/cloudflare/functions/` — Pages Functions: `api/feedback.js`, `audio/[[path]].js` (R2 with HTTP Range support, which Safari needs).
- `hosting/cloudflare/wrangler.toml` — bindings `FEEDBACK` (KV) and `AUDIO` (R2). Secret `FEEDBACK_KEY` gates reading notes over HTTP.
- `voices/` — audio render kit (Kokoro on the A40; macOS `say` as an alternative). Outputs `out/audio/*.mp3` + `manifest.json` with sentence start times. `publish_audio.sh` sends them to R2 through the `audio` branch.
- `ios/` — the Capacitor iOS wrapper; `TESTFLIGHT.md` (getting it to testers), `BUILD-iOS.md` (the original plan), `NOTES.md` (build log).
- `SHIPPING.md` — Cloudflare setup, ship, audio upload, reading feedback.

## Narration format

```
=== TOUR
id: loop
title: The Loop: Birthplace of the Skyscraper
area: Downtown
blurb: One line.
=== OVERVIEW
Paragraphs separated by blank lines.
=== STOP Stop Title @ 41.8787,-87.6357
Paragraphs.
```
`area` groups tours on the home screen, in file order: Downtown, North Side, West & Northwest Sides, South Side, West suburbs. Write for the ear: spell out abbreviations ("Street", not "St."), avoid symbols, and keep the second-person "look up at…" voice. Pronunciation fixes live in two places that must match: `SPEAK_FIX` in `index.html` and `voices/common.py` (Chicago names such as Mies, DuSable, Cermak, Juárez, Goethe Street). Flag legends as legends; keep claims you aren't sure of out. Stop titles are display-only (only the text is spoken), so they may use "&".

Stop coordinates were checked against OpenStreetMap (Nominatim) in November 2026. Keep consecutive stops at least about 120 m apart, because iOS geofences are at least 100 m across. When a note says a stop triggered late or early, fix its `@ lat,lng`.

"Go deeper" chapters (`content/deeper/NN-<tour>.txt`):
```
=== STOP Stop Title
=== DEEPER Chapter Title | history
Paragraphs.
=== DEEPER Another Chapter | look
Paragraphs.
```
- `STOP` names the stop exactly as in the tour file, without coordinates. Each `DEEPER` line is one chapter with one topic: `history`, `people`, `companies`, `architecture`, `nature`, `look` (look closer), `underfoot` (under your feet), `names`, `food`, `politics`, `culture`, `legends`. The ids live in `build.py` `LENSES` and the labels and descriptions in `index.html` `LENSES`; add a topic in both.
- Aim for about twice the stop's own narration, in three or four chapters of 250 to 350 words, each one able to stand alone. Don't repeat what the stop already says; build on it. Same voice and rules as the stops. Anything in a `legends` chapter is told as a story, with what's documented and what isn't.
- Audio: chapter n of stop i (both as shown in the app, from 1) is track key `<tour>:<i-1>:<n>`, file `<tour>-<ii>-d<n>.mp3`. Chapters are numbered by position, so inserting or reordering a chapter makes the later chapters' recordings at that stop stale.

## Rules

- Don't deploy to Cloudflare unless Alex says "ship". Bump `APP_VERSION` in index.html and add a line to CHANGELOG.md when you ship.
- After changing any stop or chapter text, its recorded audio is stale. List which tracks need re-rendering. `render_kokoro.py --all` skips existing files, so delete those mp3s and their manifest entries before rerendering.
- GPU work on the A40 goes through Alex's shared queue conventions, and the render script refuses CUDA if the `gpu-fan` service isn't active.
- App facts worth knowing: iOS web pages only get basic built-in voices (WebKit fingerprinting protection), hence recorded audio; iPhone Silent mode mutes web speech; browser GPS stops when the screen locks, hence the iOS wrapper.
