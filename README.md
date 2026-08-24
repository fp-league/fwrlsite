# FWRL — Fortnite World Racing League

This repo has two parts:

- **/** (repo root) — the public website + admin dashboard. Static HTML/CSS/JS, deployed via GitHub Pages straight from this repo.
- **/bot** — the Discord bot and screen-reading capture agent. A Python app — GitHub Pages can't run this, it needs to be hosted separately (see `bot/BOT-README.md` and `bot/ADMIN-LOGIN-SETUP.md`).

See `GITHUB-DEPLOY.md` for exact step-by-step deployment instructions.

## Structure

```
index.html, standings.html, schedule.html,   ← public site pages
teams.html, discord.html, status.html
fwrl-admin.html                               ← admin dashboard (Discord login required)
style.css, script.js, data.js                 ← shared site assets + data
bot/
  bot.py                                      ← Discord bot + admin login + capture API
  capture_agent.py                            ← screen-reading race data capture
  calibrate.py                                ← one-time HUD region calibration tool
  requirements.txt
  .env.example                                ← copy to bot/.env and fill in (never commit .env)
  ADMIN-LOGIN-SETUP.md                        ← Discord OAuth setup steps
  BOT-README.md                               ← running the bot + capture agent
  fwrl-bot-screen-reader-scope.md             ← architecture notes for the capture pipeline
  test_parsing.py                             ← sanity tests for OCR parsing logic
```

## Updating standings/schedule/teams

Edit through the admin dashboard (`fwrl-admin.html`, requires Discord login) and use its **Export data.js** button, then replace `data.js` in this repo and push — or just edit `data.js` directly and push.
