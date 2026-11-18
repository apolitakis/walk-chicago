# Walk Chicago — recording the narration

This folder turns the narration tracks (22 overviews, 144 stops, and each stop's "Go deeper" chapters) into audio files the app plays instead of the phone voice. Recorded audio keeps playing with the screen locked, and the transcript still highlights sentence by sentence.

## Contents

| File | What it is |
|---|---|
| `tracks.json` | All narration text, one entry per track (made by `build.py`; chapter tracks are named like `loop-01-d2`) |
| `sample.txt` | A short bakeoff passage: the Board of Trade and Ceres |
| `render_kokoro.py` | Open-weights neural voice (Kokoro-82M). Linux/GPU; also runs on CPU, more slowly |
| `render_mac.py` | macOS built-in voices, including downloaded Premium ones. Nothing to install |
| `common.py` | Shared code: sentence splitting, pauses, encoding, timing manifest |

## Step 1 — bakeoff samples

**A40 (Kokoro):**
```
cd walk-chicago-voices
python3 -m venv .venv && . .venv/bin/activate
pip install "kokoro>=0.9" soundfile      # sudo apt install espeak-ng ffmpeg  if missing
python3 render_kokoro.py --sample
```
This writes `samples/kokoro-<voice>.mp3` for 8 voices: af_heart, af_bella, af_nicole (American female); am_michael, am_fenrir, am_puck (American male); bf_emma, bm_george (British). The first run downloads the model (~330 MB) from Hugging Face. On CUDA it checks that `gpu-fan` is active first and refuses to run otherwise. The sample is a few seconds of GPU time; submit it through the shared GPU queue if you prefer.

**Mac (Apple voices):**
First download voices in System Settings → Accessibility → Spoken Content → System voice → Manage Voices… → English. Tick a few Premium/Enhanced ones (Ava, Zoe, Evan, Nathan…). Then:
```
cd walk-chicago-voices
python3 render_mac.py --sample
```
This writes `samples/mac-<voice>.m4a` for every Premium/Enhanced English voice installed.

## Step 2 — record everything with the winner

```
python3 render_kokoro.py --all --voice af_heart        # or whichever voice won
python3 render_mac.py --all --voice "Zoe (Premium)"    # if a Mac voice won
```
- Add `--limit 3` first if you want a quick test.
- Runs are resumable: rerun the same command after an interruption and finished tracks are skipped.
- Output goes to `out/audio/`: one file per track, plus `manifest.json` with each sentence's start time. Expect roughly 170 MB for the ~6 hours of tours and stops, and about twice that again for the Go deeper chapters.
- When new chapters are added, the same command records just the new tracks.
- Rough timing (not measured): Kokoro on the A40 should take minutes. `say` on a Mac may take an hour or so.

## Step 3 — publish

On the A40, `bash publish_audio.sh` pushes `out/audio/` to the `audio` branch, and a GitHub Action uploads it to the R2 bucket `walk-chicago-audio` (or, with the Cloudflare token in the environment, `bash upload_r2.sh` uploads directly); see SHIPPING.md in the repo root. The live site and the iOS app read audio from there, so no site redeploy is needed.

