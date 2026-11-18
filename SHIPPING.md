# Shipping, audio, and feedback

All commands run from the repo root unless noted, with `CLOUDFLARE_API_TOKEN` and `CLOUDFLARE_ACCOUNT_ID` set (they are in the cloud environment the Walk NYC and Walk Chicago threads use). The token needs Pages: Edit, Workers KV Storage: Edit, and Workers R2 Storage: Edit.

## One-time setup (done 2026-11-18)

```
cd hosting/cloudflare
npx wrangler pages project create walk-chicago --production-branch main
npx wrangler kv namespace create walk-chicago-feedback      # id b27b2c91d739401da8d7f750f06c5aa2, in wrangler.toml
npx wrangler r2 bucket create walk-chicago-audio
openssl rand -hex 32 | npx wrangler pages secret put FEEDBACK_KEY --project-name walk-chicago
```
The `FEEDBACK_KEY` value wasn't stored anywhere, because threads read notes straight from KV with the token (below). To use the `GET /api/feedback` route instead, set a new value the same way and keep it; it takes effect on the next ship.

## Ship (only when Alex says "ship")

```
python3 build.py
cd hosting/cloudflare && npx wrangler pages deploy public --project-name walk-chicago --branch main --commit-dirty=true
```
Then check `https://walk-chicago.pages.dev/` loads, `/audio/manifest.json` returns JSON (once audio is uploaded), and `POST /api/feedback` with `{"note":"ship test"}` returns `{"ok":true}`. (The cloud environment may need `walk-chicago.pages.dev` added to its allowed hosts for these checks.)

## Recorded audio

1. Render on the A40 (see `voices/README.md`) in `~/lab/walk-chicago-voices`: `python render_kokoro.py --all --voice af_heart`. Alex's chosen voice for Walk NYC is **af_heart**; Walk Chicago uses the same one.
2. Publish from the A40:
   ```
   cd ~/lab/walk-chicago-voices && bash publish_audio.sh
   ```
   This checks that every file in `manifest.json` exists, then force-pushes `out/audio/` as a single commit to the `audio` branch, over the A40's walk-chicago deploy key (SSH host alias `github-walkchicago`; GitHub doesn't let one deploy key serve two repos, so it is separate from Walk NYC's). Pushing to that branch runs the **Upload narration to R2** Action, which uploads each mp3 to the R2 bucket `walk-chicago-audio` under `audio/`, then `manifest.json` last, so the app never sees a manifest pointing at missing files. The Action then checks the live manifest and one mp3. Watch it at https://github.com/apolitakis/walk-chicago/actions.
   - The Action needs the repo secrets `CLOUDFLARE_API_TOKEN` (R2 object writes on `walk-chicago-audio` are enough) and `CLOUDFLARE_ACCOUNT_ID`.
   - The Action's definition is in `voices/publish_audio.sh`, which writes it into the `audio` branch. Edit it there, not on the branch.
   - To re-run an upload without re-pushing: Actions -> Upload narration to R2 -> Run workflow, on branch `audio`.
   - Fallback, with the token in the environment: `bash voices/upload_r2.sh` uploads directly.
   - No branch may be named `audio/...` (it would clash with `audio`).
3. No redeploy needed: the Pages Function reads R2 directly. The app picks up the new manifest on its next launch.

## Reading feedback notes

```
python3 scripts/read_feedback.py          # newest first; --json for the raw notes
```
It reads the `walk-chicago-feedback` KV namespace through the Cloudflare API with the token, so no feedback key is needed. Each note has the text, tour, stop index and title, the Go deeper chapter if one was playing, the sentence playing when it was written, lat/lng/accuracy, app version, and time. Typical workflow: read the notes, group them (facts, pronunciation, GPS placement, UX), propose fixes to Alex, make the agreed changes, ship when told.
