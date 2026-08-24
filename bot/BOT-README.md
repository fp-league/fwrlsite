# FWRL Bot — Screen-Reading Prototype

Prototype for reading live race data (position, lap, pit status) off the Rocket Racing HUD and pushing it into a live Discord standings embed, since there's no official timing API to pull from.

## How it fits together

```
race game (PC) ──screen──▶ capture_agent.py ──HTTP POST──▶ bot.py ──▶ Discord embed
                              (OCR + template match)      (localhost:8765)
```

`capture_agent.py` and `bot.py` are separate processes that talk over localhost. They can run on the same machine or two machines on the same network (change `bot_endpoint` in `config.json` accordingly).

## Setup

1. Install Python 3.10+ and [Tesseract OCR](https://github.com/tesseract-ocr/tesseract) (the binary — `pytesseract` just calls out to it. On Windows, install it and make sure `tesseract.exe` is on your PATH).
2. `pip install -r requirements.txt`
3. Copy `.env.example` to `.env`, fill in your bot token (from the Discord Developer Portal) and the channel ID where standings should post.
4. Calibrate the HUD regions once for your resolution:
   ```
   python calibrate.py
   ```
   This opens your screen (make sure the race HUD is visible) and lets you drag boxes around the position number, lap counter, and pit indicator. Saves coordinates into `config.json` and a `pit_icon_template.png` reference image.
5. Start the bot:
   ```
   python bot.py
   ```
6. Start the capture agent for each driver you're tracking (one process per driver's screen, since it's reading one HUD at a time):
   ```
   python capture_agent.py --driver "K. Reyes"
   ```
   Use `--dry-run` first to confirm it's reading sensible values before letting it post to the bot.

## In-race controls

- `/correct driver:<name> position:<n> lap:<x/y> pit:<true|false>` — fix a bad OCR read without restarting anything.
- `/reset_standings` — clear the board at the start of a new race.

## Known limitations of this prototype

- **One capture agent per driver's screen.** If races are hosted from a single PC/stream, you'd need one calibrated region set per visible HUD, or run one agent per racer's own machine.
- **OCR needs Tesseract installed as a system binary**, not just the Python package — this is the most common setup snag.
- **Regions are resolution-specific.** Re-run `calibrate.py` if the race resolution or window size changes.
- **This has not been tested against real Rocket Racing footage yet.** Per the scope doc, the recommended next step is to record sample race footage and validate OCR accuracy against it before running this live.

## Files

| File | Purpose |
|---|---|
| `config.json` | HUD region coordinates, OCR whitelists, timing settings |
| `calibrate.py` | One-time visual tool to set region coordinates |
| `capture_agent.py` | Reads the screen, OCRs/template-matches, posts confirmed updates |
| `bot.py` | Discord bot — live embed + `/correct` and `/reset_standings` commands |
| `requirements.txt` | Python dependencies |
| `.env.example` | Copy to `.env` and fill in bot token + channel ID |

See `fwrl-bot-screen-reader-scope.md` for the architecture rationale and risks.
