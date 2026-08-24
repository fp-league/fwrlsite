# Setting Up Discord Login for the Admin Dashboard

The admin dashboard (`fwrl-admin.html`) no longer uses a password. Instead, visitors click "Login with Discord," and `bot.py` checks whether they hold a specific admin role in your FWRL Discord server before letting them in. This requires a few one-time setup steps in the Discord Developer Portal.

## 1. Create/configure the Discord application

If you don't already have a Discord application for your bot:

1. Go to https://discord.com/developers/applications and create a new application (or open your existing FWRL bot's application).
2. Under **OAuth2 → General**, copy the **Client ID** and **Client Secret** — these go into `.env` as `DISCORD_CLIENT_ID` and `DISCORD_CLIENT_SECRET`.
3. Under **OAuth2 → General → Redirects**, add:
   ```
   http://127.0.0.1:8765/auth/callback
   ```
   (Change the port/host here if you changed `CAPTURE_HTTP_PORT`, or if you're hosting `bot.py` somewhere other than your own machine — see "Running this remotely" below.)
4. Under **Bot → Privileged Gateway Intents**, enable **Server Members Intent**. This is required for the bot to look up a logged-in user's roles.

## 2. Get your server (guild) ID and admin role ID

1. In Discord, enable Developer Mode: **User Settings → Advanced → Developer Mode**.
2. Right-click your FWRL server's icon → **Copy Server ID** → this is `DISCORD_GUILD_ID`.
3. Right-click the role that should have admin access (e.g. "League Admin") in **Server Settings → Roles** → **Copy Role ID** → this is `DISCORD_ADMIN_ROLE_ID`.
4. Make sure your bot is actually a member of this server with permission to see roles (it should already be, if it's posting standings there).

## 3. Generate a session secret

`SESSION_SECRET` signs the login tokens the admin dashboard uses — it should be a long random string that never gets committed anywhere public. Generate one with:
```
python -c "import secrets; print(secrets.token_hex(32))"
```

## 4. Fill in `.env`

```
DISCORD_CLIENT_ID=...
DISCORD_CLIENT_SECRET=...
DISCORD_GUILD_ID=...
DISCORD_ADMIN_ROLE_ID=...
OAUTH_REDIRECT_URI=http://127.0.0.1:8765/auth/callback
SESSION_SECRET=...
SESSION_TTL_SECONDS=28800
```

## 5. Run it

```
python bot.py
```
Then open `fwrl-admin.html` and click **Login with Discord**. If you're not a member of `DISCORD_GUILD_ID` with the `DISCORD_ADMIN_ROLE_ID` role, you'll be bounced back with "not authorized."

## Important limitation: admin login only works while bot.py is running

There's no separate backend — `bot.py` *is* the backend for admin login. If it's not running, "Login with Discord" will fail (the dashboard will tell you to check that bot.py is up). This is fine if you mainly need admin access during races when the bot is already running anyway; if you want the admin dashboard reachable any time, you'll need to host `bot.py` somewhere that stays up (a small always-on VPS, Railway, Fly.io, etc.) rather than only running it on a race host's PC.

## Running this remotely (bot.py not on the same machine as the admin page)

The admin page's login button sends the browser to `<bot address>/auth/login`. By default that's `http://127.0.0.1:8765`, which only resolves to *your own* machine — if `bot.py` runs on a different computer (e.g. the race host PC), that won't reach it.

To fix this:
1. On the admin page's login screen, change the **FWRL bot address** field to wherever `bot.py` is actually reachable — e.g. its LAN IP (`http://192.168.1.42:8765`) or a public URL if you've set up port forwarding / a tunnel (ngrok, Cloudflare Tunnel, etc.).
2. Update `OAUTH_REDIRECT_URI` in `bot.py`'s `.env` to match that same address (e.g. `http://192.168.1.42:8765/auth/callback`), and update the redirect URI registered in the Discord Developer Portal to match exactly — Discord rejects any mismatch.

## Security notes

- Session tokens are signed (HMAC-SHA256) and expire after `SESSION_TTL_SECONDS` (default 8 hours). They're stored in the browser's `sessionStorage`, so they clear when the tab closes.
- Anyone who loses the admin role in Discord will fail the next login attempt, but an already-issued session token stays valid until it expires — role changes don't immediately revoke existing sessions. Lower `SESSION_TTL_SECONDS` if you need faster revocation.
- This flow only requests the `identify` OAuth scope (username + user ID) — it doesn't ask for email, guild list, or anything else.
