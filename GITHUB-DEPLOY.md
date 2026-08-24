# Deploying FWRL to GitHub Pages

This deploys the **website** (root files) live via GitHub Pages — free hosting straight from your repo. The **bot** (`/bot` folder) is *not* deployed by this process; GitHub Pages only serves static files and can't run Python. See `bot/BOT-README.md` and the "What about the bot?" section at the bottom for that part.

You don't need to be a developer for this — there's a no-terminal option (Method A) and a git/command-line option (Method B).

---

## Method A — No terminal, just the GitHub website (easiest)

1. Go to https://github.com and sign in (create a free account if you don't have one).
2. Click the **+** in the top-right → **New repository**.
   - Name it something like `fwrl-website`.
   - Set it to **Public** (required for free GitHub Pages).
   - Don't initialize with a README (we already have one) — leave "Add a README file" unchecked.
   - Click **Create repository**.
3. On the new (empty) repo page, click **uploading an existing file**.
4. Unzip the package I gave you on your computer, then drag *all* the files and folders from inside it (index.html, style.css, the `bot` folder, etc.) into the upload area. Do not upload the outer zip file itself, and do not upload a folder that wraps everything — the files need to land at the repo root.
5. Scroll down, add a commit message like "Initial site", click **Commit changes**.
6. Go to the repo's **Settings** tab → **Pages** (left sidebar, under "Code and automation").
7. Under "Build and deployment" → Source: choose **Deploy from a branch**. Branch: **main**, folder: **/ (root)**. Click **Save**.
8. Wait about a minute, then refresh the Pages settings page — it'll show a green box with your live URL, something like:
   ```
   https://<your-username>.github.io/fwrl-website/
   ```
9. Open that URL — your site is live.

## Method B — Using git (command line)

If you're comfortable with a terminal and have `git` installed:

```bash
# 1. Create the repo on GitHub first (same as Method A steps 1-2), then:
git clone https://github.com/<your-username>/fwrl-website.git
cd fwrl-website

# 2. Copy in all the files from the unzipped package (index.html, style.css,
#    the bot/ folder, README.md, .gitignore, everything) so they land at the
#    root of this cloned folder.

git add .
git commit -m "Initial site"
git push origin main
```

Then do steps 6-9 from Method A to turn on Pages.

---

## Updating the live site later

**Method A (web UI):** go to your repo, click into the file you want to change (e.g. `data.js`), click the pencil/edit icon, make your change, commit directly to `main`. Pages redeploys automatically within a minute or two.

**Method B (git):** edit the files locally, then:
```bash
git add .
git commit -m "Update standings"
git push origin main
```

Either way — after using the admin dashboard's **Export data.js** button, replace `data.js` in the repo with the downloaded one and commit/push (or upload it through the web UI) to publish the changes.

---

## Custom domain (optional)

If you own a domain and want e.g. `fwrl.gg` instead of the `github.io` address:
1. In repo Settings → Pages, enter your domain under "Custom domain" and save (this creates a `CNAME` file in your repo automatically).
2. At your domain registrar, add a `CNAME` DNS record pointing your subdomain (e.g. `www`) to `<your-username>.github.io`, or `A` records pointing the apex domain to GitHub's Pages IPs (GitHub's docs list the current IPs — search "GitHub Pages custom domain A records").
3. Wait for DNS to propagate (can take a few minutes to a few hours), then check "Enforce HTTPS" once GitHub shows the certificate is ready.

---

## What about the bot?

GitHub Pages can only serve static files — it cannot run `bot.py`. The `/bot` folder is included in this repo just so the code is version-controlled alongside the site, but you still need to run it somewhere that supports a live Python process: your own PC during races, or an always-on host like Railway/Render/a VPS for 24/7 admin login and live standings. Full options are in `bot/BOT-README.md`.

Once the bot is running somewhere, open your live GitHub Pages site's `status.html` or `fwrl-admin.html` and set the **FWRL bot address** field to wherever the bot is reachable.

## Before you push a public repo

Since this repo will be public: **never commit `bot/.env`** (it holds your real Discord bot token and OAuth secret). The included `.gitignore` already excludes it — just make sure you copy `.env.example` to `.env` locally/on your bot host and fill in real values there, not in the repo.
