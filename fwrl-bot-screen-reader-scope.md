# FWRL Discord Bot — Screen-Reading Race Data Scope

## Problem

There's no live timing API for Rocket Racing, so race data (position, lap, pit status) has to be pulled from the game's HUD in real time by watching the screen on the racer's/host's PC and extracting text and icons. This scope covers a companion capture agent that runs alongside the game and feeds parsed data to the Discord bot.

## Architecture (PC-only, local capture agent)

1. **Capture agent** — a small Python process running on the host machine during races. Grabs the game window at a fixed interval (1–2 fps is plenty; HUD doesn't need video-rate updates).
2. **Region extraction** — crop fixed screen regions for each HUD element (position number, lap counter, pit indicator). Rocket Racing's HUD layout is fixed, so regions can be calibrated once per resolution/aspect ratio and reused.
3. **Reading each region**:
   - **Position (P1–P12) and lap counter**: OCR on the cropped region.
   - **Pit status**: more reliable as icon/template matching than OCR (detect the pit indicator graphic appearing/disappearing) rather than reading text.
4. **Smoothing/confidence**: single-frame OCR misreads are common. Require the same reading to repeat across 2–3 consecutive frames before accepting it, and discard low-confidence reads rather than pushing bad data.
5. **Delivery to the bot**: capture agent posts parsed updates (position, lap, pit in/out) to the bot over localhost — either a local HTTP call to a small Flask/FastAPI endpoint the bot exposes, or a shared queue/file if bot and agent run in the same process.
6. **Bot output**: bot edits a single "live standings" embed in the Discord channel on an interval (every 3–5s), not on every update — Discord rate-limits message edits, and per-frame edits would get throttled instantly.
7. **Manual override**: a race admin command (e.g. `/correct position @driver 3`) to fix bad reads live, since OCR will occasionally get it wrong mid-race.

## Suggested stack

- `mss` — fast screen capture
- `opencv-python` — region cropping, template matching for icons
- `pytesseract` or `easyocr` — text OCR on the position/lap regions (easyocr tends to be more robust on stylized game fonts, at the cost of being slower — worth testing both against real footage)
- `discord.py` (or `discord.js` if the bot's already in Node) for the Discord side
- Local FastAPI/Flask endpoint or a simple queue to connect the two if they run as separate processes

## Risks / things that will bite you

- **HUD changes with game updates** — Epic can shift the HUD layout in a patch and break your calibrated regions without warning. Plan to recalibrate periodically, not just once.
- **Motion blur / fast HUD animation** — numbers can be genuinely unreadable on some frames. The multi-frame confirmation step above is there specifically to absorb this.
- **Performance overhead** — running OCR every 0.5–1s alongside a racing game eats CPU/GPU. Keep regions small and consider only running OCR when something in the region actually changed (frame diff) rather than every capture.
- **Discord rate limits** — batch updates into periodic embed edits, not per-event messages.

## Suggested build order

1. Record sample race footage first, prototype capture + OCR against the recording (not live) to validate accuracy before touching a live race.
2. Calibrate exact HUD regions from a reference screenshot at your target resolution.
3. Build the capture → parse → local endpoint pipeline with a manual-review mode (log what it read, don't push to Discord yet).
4. Wire it into the bot's live embed, with the manual-correction command as a safety net from day one.
5. Run it in a real race with an admin watching for misreads before trusting it unsupervised.

## Open questions to nail down before building

- What resolution/aspect ratio will races be run at consistently? (regions are resolution-dependent)
- Is there one canonical host PC/capture setup, or will different racers host different rounds?
- Acceptable latency — is a 3–5s lag on standings updates fine, or does it need to feel closer to real-time?
