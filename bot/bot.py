"""
FWRL Discord bot.

Runs three things in one process:
  1. A local FastAPI endpoint (POST /update) that capture_agent.py sends
     confirmed position/lap/pit readings to.
  2. A discord.py bot that keeps one "live standings" embed message
     up to date on an interval, and exposes admin-only override commands
     for when OCR gets something wrong mid-race.
  3. A Discord OAuth2 login flow (GET /auth/login, /auth/callback,
     /auth/verify) that fwrl-admin.html uses to gate access to the admin
     dashboard: a visitor logs in with Discord, and is only let in if
     they hold the configured admin role in the FWRL Discord server.

Setup:
  1. Copy .env.example to .env and fill in DISCORD_BOT_TOKEN and
     STANDINGS_CHANNEL_ID.
  2. For admin login, also fill in DISCORD_CLIENT_ID, DISCORD_CLIENT_SECRET,
     DISCORD_GUILD_ID, DISCORD_ADMIN_ROLE_ID, SESSION_SECRET, and
     OAUTH_REDIRECT_URI. See ADMIN-LOGIN-SETUP.md for exact steps.
  3. Run this file: python bot.py
  4. On another (or the same) machine, run capture_agent.py once the
     bot is up so it has somewhere to POST to.

IMPORTANT: this bot process is what fwrl-admin.html talks to for login.
Admin login only works while bot.py is running and reachable from wherever
the admin page is opened (127.0.0.1 only works if they're on the same
machine as this process — see ADMIN-LOGIN-SETUP.md for reaching it
remotely).

The embed only edits every EMBED_UPDATE_INTERVAL seconds, batching
whatever readings came in during that window, to stay well under
Discord's rate limits. Entries that haven't been updated in
STALE_AFTER_SECONDS are flagged, since that usually means the capture
agent for that driver crashed or lost sight of the HUD.
"""

import base64
import hashlib
import hmac
import json
import logging
import os
import secrets
import threading
import time
import urllib.parse
from datetime import datetime, timezone

import discord
import httpx
from discord import app_commands
from discord.ext import tasks
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
import uvicorn

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("fwrl.bot")

DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
STANDINGS_CHANNEL_ID = int(os.getenv("STANDINGS_CHANNEL_ID", "0"))
EMBED_UPDATE_INTERVAL = float(os.getenv("EMBED_UPDATE_INTERVAL_SECONDS", "4"))
HTTP_PORT = int(os.getenv("CAPTURE_HTTP_PORT", "8765"))
STALE_AFTER_SECONDS = float(os.getenv("STALE_AFTER_SECONDS", "20"))
MAX_EMBED_FIELDS = 24  # Discord's hard limit is 25; leave room for a summary field if needed

# --- Discord OAuth2 (admin dashboard login) ---------------------------------
DISCORD_CLIENT_ID = os.getenv("DISCORD_CLIENT_ID", "")
DISCORD_CLIENT_SECRET = os.getenv("DISCORD_CLIENT_SECRET", "")
DISCORD_GUILD_ID = int(os.getenv("DISCORD_GUILD_ID", "0") or "0")
DISCORD_ADMIN_ROLE_ID = os.getenv("DISCORD_ADMIN_ROLE_ID", "")
OAUTH_REDIRECT_URI = os.getenv("OAUTH_REDIRECT_URI", f"http://127.0.0.1:{HTTP_PORT}/auth/callback")
SESSION_SECRET = os.getenv("SESSION_SECRET", "")
SESSION_TTL_SECONDS = int(os.getenv("SESSION_TTL_SECONDS", str(8 * 3600)))

# In-memory race state: {driver_name: {"position": int, "lap": str, "pit": bool, "updated_at": datetime, "source": str}}
race_state = {}
state_lock = threading.Lock()
state_dirty = False

# Short-lived CSRF state for the OAuth handshake: {state: {"return_to": str, "created": float}}
pending_oauth_states = {}
OAUTH_STATE_TTL_SECONDS = 300

PROCESS_START_TIME = time.time()


# ---------------------------------------------------------------------------
# Session tokens (stdlib HMAC — no extra JWT dependency needed for this)
# ---------------------------------------------------------------------------
def make_session_token(payload):
    if not SESSION_SECRET:
        raise RuntimeError("SESSION_SECRET is not set — cannot issue session tokens.")
    data = dict(payload)
    data["exp"] = int(time.time()) + SESSION_TTL_SECONDS
    body = base64.urlsafe_b64encode(json.dumps(data).encode()).decode().rstrip("=")
    sig = hmac.new(SESSION_SECRET.encode(), body.encode(), hashlib.sha256).hexdigest()
    return f"{body}.{sig}"


def verify_session_token(token):
    if not token or not SESSION_SECRET or "." not in token:
        return None
    body, sig = token.rsplit(".", 1)
    expected_sig = hmac.new(SESSION_SECRET.encode(), body.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(sig, expected_sig):
        return None
    padded = body + "=" * (-len(body) % 4)
    try:
        data = json.loads(base64.urlsafe_b64decode(padded.encode()))
    except Exception:
        return None
    if data.get("exp", 0) < time.time():
        return None
    return data


def cleanup_pending_states():
    now = time.time()
    expired = [s for s, v in pending_oauth_states.items() if now - v["created"] > OAUTH_STATE_TTL_SECONDS]
    for s in expired:
        pending_oauth_states.pop(s, None)


async def check_admin_role(user_id):
    """True only if the logged-in Discord user is currently a member of the
    FWRL guild AND holds the configured admin role there."""
    if not DISCORD_ADMIN_ROLE_ID or not DISCORD_GUILD_ID:
        log.warning("DISCORD_GUILD_ID / DISCORD_ADMIN_ROLE_ID not configured — denying all admin logins.")
        return False
    guild = client.get_guild(DISCORD_GUILD_ID)
    if guild is None:
        log.warning("Bot is not in guild %s (or it hasn't finished caching). Denying login.", DISCORD_GUILD_ID)
        return False
    member = guild.get_member(int(user_id))
    if member is None:
        try:
            member = await guild.fetch_member(int(user_id))
        except discord.NotFound:
            return False
        except discord.HTTPException:
            log.exception("Error fetching guild member for role check.")
            return False
    return any(str(role.id) == str(DISCORD_ADMIN_ROLE_ID) for role in member.roles)


# ---------------------------------------------------------------------------
# Local HTTP API — capture agent updates + admin OAuth
# ---------------------------------------------------------------------------
api = FastAPI()

# Admin dashboard is a static file that may be opened via file:// or hosted
# elsewhere; CORS has to be wide open for this local tool to be reachable.
api.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@api.post("/update")
async def receive_update(request: Request):
    global state_dirty
    payload = await request.json()
    driver = payload.get("driver")
    if not driver:
        return {"ok": False, "error": "missing 'driver'"}

    with state_lock:
        entry = race_state.setdefault(driver, {"position": None, "lap": None, "pit": False})
        if "position" in payload:
            entry["position"] = payload["position"]
        if "lap" in payload:
            entry["lap"] = payload["lap"]
        if "pit" in payload:
            entry["pit"] = payload["pit"]
        entry["updated_at"] = datetime.now(timezone.utc)
        entry["source"] = payload.get("source", "ocr")
        state_dirty = True

    log.debug(f"Received update for {driver}: {payload}")
    return {"ok": True}


@api.get("/health")
async def health():
    """Public status endpoint — no auth required. Used by status.html so
    anyone can see whether the FWRL backend is alive without needing to
    log in. Deliberately avoids leaking anything sensitive (driver names,
    session data, etc) — just aggregate counts and connection state."""
    with state_lock:
        entries = list(race_state.values())
    stale_count = sum(1 for e in entries if is_stale(e))
    last_update = None
    if entries:
        timestamps = [e["updated_at"] for e in entries if e.get("updated_at")]
        if timestamps:
            last_update = max(timestamps).isoformat()

    bot_connected = client.is_ready() if client else False
    guild = client.get_guild(DISCORD_GUILD_ID) if (bot_connected and DISCORD_GUILD_ID) else None

    return {
        "ok": True,
        "uptime_seconds": round(time.time() - PROCESS_START_TIME),
        "bot_connected": bot_connected,
        "standings_channel_configured": bool(STANDINGS_CHANNEL_ID),
        "embed_loop_running": refresh_embed.is_running() if bot_connected else False,
        "admin_login_configured": bool(DISCORD_CLIENT_ID and SESSION_SECRET),
        "guild_configured": bool(DISCORD_GUILD_ID),
        "guild_reachable": guild is not None if DISCORD_GUILD_ID else None,
        "drivers_tracked": len(entries),
        "stale_drivers": stale_count,
        "last_update": last_update,
    }


@api.get("/auth/login")
async def auth_login(return_to: str):
    if not DISCORD_CLIENT_ID or not SESSION_SECRET:
        return JSONResponse(
            {"error": "Discord login isn't configured on this bot yet. See ADMIN-LOGIN-SETUP.md."},
            status_code=503,
        )
    cleanup_pending_states()
    state = secrets.token_urlsafe(24)
    pending_oauth_states[state] = {"return_to": return_to, "created": time.time()}
    params = {
        "client_id": DISCORD_CLIENT_ID,
        "redirect_uri": OAUTH_REDIRECT_URI,
        "response_type": "code",
        "scope": "identify",
        "state": state,
        "prompt": "consent",
    }
    url = "https://discord.com/api/oauth2/authorize?" + urllib.parse.urlencode(params)
    return RedirectResponse(url)


def _redirect_with_error(return_to, error_code):
    target = (return_to or "/") + "#auth_error=" + urllib.parse.quote(error_code)
    return RedirectResponse(target)


@api.get("/auth/callback")
async def auth_callback(code: str = None, state: str = None, error: str = None):
    pending = pending_oauth_states.pop(state, None) if state else None
    return_to = pending["return_to"] if pending else None

    if error:
        return _redirect_with_error(return_to, "denied")
    if not code or not pending:
        return _redirect_with_error(return_to or "/", "invalid_state")

    async with httpx.AsyncClient(timeout=10) as http_client:
        token_resp = await http_client.post(
            "https://discord.com/api/oauth2/token",
            data={
                "client_id": DISCORD_CLIENT_ID,
                "client_secret": DISCORD_CLIENT_SECRET,
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": OAUTH_REDIRECT_URI,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
    if token_resp.status_code != 200:
        log.warning("Discord token exchange failed: %s %s", token_resp.status_code, token_resp.text)
        return _redirect_with_error(return_to, "token_exchange_failed")
    access_token = token_resp.json().get("access_token")

    async with httpx.AsyncClient(timeout=10) as http_client:
        user_resp = await http_client.get(
            "https://discord.com/api/users/@me",
            headers={"Authorization": f"Bearer {access_token}"},
        )
    if user_resp.status_code != 200:
        return _redirect_with_error(return_to, "identity_fetch_failed")
    discord_user = user_resp.json()
    user_id = discord_user["id"]
    username = discord_user.get("username", "unknown")

    is_admin = await check_admin_role(user_id)
    if not is_admin:
        log.info("Login denied (no admin role): %s (%s)", username, user_id)
        return _redirect_with_error(return_to, "not_authorized")

    token = make_session_token({"uid": user_id, "username": username})
    log.info("Admin login granted: %s (%s)", username, user_id)
    return RedirectResponse(return_to + "#token=" + token)


@api.get("/auth/verify")
async def auth_verify(request: Request):
    auth_header = request.headers.get("Authorization", "")
    token = auth_header[7:] if auth_header.startswith("Bearer ") else request.query_params.get("token", "")
    payload = verify_session_token(token)
    if not payload:
        return JSONResponse({"valid": False}, status_code=401)
    return {"valid": True, "username": payload.get("username")}


def run_http_server():
    uvicorn.run(api, host="0.0.0.0", port=HTTP_PORT, log_level="warning")


# ---------------------------------------------------------------------------
# Discord bot
# ---------------------------------------------------------------------------
intents = discord.Intents.default()
intents.members = True  # required to look up a logged-in user's roles for admin login
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

standings_message = None  # the live embed message, created on first update


def is_stale(entry):
    updated_at = entry.get("updated_at")
    if updated_at is None:
        return True
    return (datetime.now(timezone.utc) - updated_at).total_seconds() > STALE_AFTER_SECONDS


def build_embed():
    with state_lock:
        entries = sorted(
            race_state.items(),
            key=lambda kv: (kv[1]["position"] is None, kv[1]["position"] or 99),
        )

    embed = discord.Embed(
        title="FWRL — Live Standings",
        description="Auto-updated from race screen reads. Corrections may lag by a few seconds.",
        color=0xFF2E4D,
        timestamp=datetime.now(timezone.utc),
    )
    if not entries:
        embed.add_field(name="No data yet", value="Waiting on the capture agent...", inline=False)
        return embed

    shown = entries[:MAX_EMBED_FIELDS]
    for driver, info in shown:
        pos = info["position"] if info["position"] is not None else "?"
        lap = info["lap"] if info["lap"] else "?"
        pit_flag = " 🔧 IN PIT" if info["pit"] else ""
        source_flag = " (manual)" if info.get("source") == "manual" else ""
        stale_flag = " ⚠ stale" if is_stale(info) else ""
        embed.add_field(
            name=f"P{pos} — {driver}{pit_flag}",
            value=f"Lap {lap}{source_flag}{stale_flag}",
            inline=False,
        )

    if len(entries) > MAX_EMBED_FIELDS:
        embed.set_footer(text=f"+ {len(entries) - MAX_EMBED_FIELDS} more drivers not shown (Discord embed limit)")

    return embed


@tasks.loop(seconds=EMBED_UPDATE_INTERVAL)
async def refresh_embed():
    global standings_message, state_dirty
    # Re-render even if not dirty, on a slower cadence, so stale flags update
    # without needing a fresh OCR read to trigger it.
    if not state_dirty and refresh_embed.current_loop % 5 != 0:
        return
    channel = client.get_channel(STANDINGS_CHANNEL_ID)
    if channel is None:
        log.warning(f"Standings channel {STANDINGS_CHANNEL_ID} not found or not cached yet.")
        return
    embed = build_embed()
    try:
        if standings_message is None:
            standings_message = await channel.send(embed=embed)
        else:
            await standings_message.edit(embed=embed)
    except discord.NotFound:
        # message was deleted out from under us — recreate it
        standings_message = await channel.send(embed=embed)
    except discord.HTTPException as e:
        log.warning(f"Failed to update standings embed: {e}")
    state_dirty = False


@refresh_embed.error
async def refresh_embed_error(error):
    log.exception("Error in refresh_embed loop", exc_info=error)


def admin_only():
    return app_commands.checks.has_permissions(manage_guild=True)


@tree.command(name="correct", description="Manually override a driver's live race data (fixes bad OCR reads). Admin only.")
@app_commands.describe(driver="Driver name as shown in standings", position="Corrected position (1-12)", lap="Corrected lap, e.g. 2/3", pit="Set pit status")
@admin_only()
async def correct(interaction: discord.Interaction, driver: str, position: int = None, lap: str = None, pit: bool = None):
    global state_dirty
    with state_lock:
        entry = race_state.setdefault(driver, {"position": None, "lap": None, "pit": False})
        if position is not None:
            entry["position"] = position
        if lap is not None:
            entry["lap"] = lap
        if pit is not None:
            entry["pit"] = pit
        entry["updated_at"] = datetime.now(timezone.utc)
        entry["source"] = "manual"
        state_dirty = True
    log.info(f"Manual correction by {interaction.user}: {driver} pos={position} lap={lap} pit={pit}")
    await interaction.response.send_message(f"Updated {driver}.", ephemeral=True)


@tree.command(name="reset_standings", description="Clear all live race data (use at the start of a new race). Admin only.")
@admin_only()
async def reset_standings(interaction: discord.Interaction):
    global standings_message, state_dirty
    with state_lock:
        race_state.clear()
        state_dirty = True
    standings_message = None
    log.info(f"Standings reset by {interaction.user}")
    await interaction.response.send_message("Standings cleared for new race.", ephemeral=True)


@correct.error
@reset_standings.error
async def admin_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.MissingPermissions):
        await interaction.response.send_message("You need Manage Server permission to use this command.", ephemeral=True)
    else:
        log.exception("Command error", exc_info=error)
        await interaction.response.send_message("Something went wrong running that command.", ephemeral=True)


@client.event
async def on_ready():
    await tree.sync()
    if not refresh_embed.is_running():
        refresh_embed.start()
    log.info(f"Logged in as {client.user}. Posting standings to channel {STANDINGS_CHANNEL_ID}.")
    if DISCORD_GUILD_ID and client.get_guild(DISCORD_GUILD_ID) is None:
        log.warning(
            "DISCORD_GUILD_ID=%s but the bot isn't a member of that guild — admin login will always fail.",
            DISCORD_GUILD_ID,
        )


def main():
    if not DISCORD_BOT_TOKEN or not STANDINGS_CHANNEL_ID:
        raise SystemExit("Set DISCORD_BOT_TOKEN and STANDINGS_CHANNEL_ID in .env before running.")
    if not SESSION_SECRET:
        log.warning("SESSION_SECRET is not set — admin Discord login will be disabled until you set one.")

    http_thread = threading.Thread(target=run_http_server, daemon=True)
    http_thread.start()
    log.info(f"Local API listening on http://0.0.0.0:{HTTP_PORT} (capture updates + admin login)")

    client.run(DISCORD_BOT_TOKEN, log_handler=None)


if __name__ == "__main__":
    main()
