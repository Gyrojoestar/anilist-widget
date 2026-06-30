import os
import json
import threading
from pathlib import Path

import discord
from discord.ext import tasks
from flask import Flask

from anilist_sync import fetch_anilist_data

BOT_TOKEN = os.environ["DISCORD_BOT_TOKEN"]
CHANNEL_ID = int(os.environ["DISCORD_CHANNEL_ID"])
POLL_SECONDS = int(os.environ.get("POLL_SECONDS", "600"))

STATE_FILE = Path("widget_state.json")

intents = discord.Intents.default()
client = discord.Client(intents=intents)

# --- tiny Flask app, only exists so Render treats this as a Web Service ---
web = Flask(__name__)


@web.route("/")
def health():
    return "AniList Discord bot is running."


def run_web():
    port = int(os.environ.get("PORT", 5000))
    web.run(host="0.0.0.0", port=port)


# --- bot logic ---
def load_state():
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {"last_message_id": None, "last_stats": None}


def save_state(state):
    STATE_FILE.write_text(json.dumps(state))


def build_embed(stats):
    embed = discord.Embed(title="AniList Stats", color=discord.Color.blue())
    embed.set_thumbnail(url=stats["avatar_url"])
    embed.add_field(name="User", value=stats["username"], inline=True)
    embed.add_field(name="Total Anime", value=str(stats["total_anime"]), inline=True)
    embed.add_field(name="Mean Score", value=str(stats["mean_score"]), inline=True)
    embed.add_field(name="Days Watched", value=str(stats["days_watched"]), inline=True)
    embed.add_field(name="Recently Watched", value=stats["recently_watched_anime"], inline=False)
    embed.add_field(name="Recently Read (Manga)", value=stats["recently_read_manga"], inline=False)
    return embed


@tasks.loop(seconds=POLL_SECONDS)
async def sync_loop():
    state = load_state()
    stats = fetch_anilist_data()
    if not stats:
        print("AniList fetch failed, skipping this cycle.")
        return

    if stats == state.get("last_stats"):
        print("No change in stats, skipping update.")
        return

    channel = client.get_channel(CHANNEL_ID)
    if channel is None:
        channel = await client.fetch_channel(CHANNEL_ID)

    if state.get("last_message_id"):
        try:
            old_message = await channel.fetch_message(state["last_message_id"])
            await old_message.delete()
        except discord.NotFound:
            pass
        except Exception as e:
            print(f"Could not delete previous message: {e}")

    new_message = await channel.send(embed=build_embed(stats))

    state["last_message_id"] = new_message.id
    state["last_stats"] = stats
    save_state(state)
    print("Posted updated AniList stats.")


@client.event
async def on_ready():
    print(f"Logged in as {client.user}")
    if not sync_loop.is_running():
        sync_loop.start()


if __name__ == "__main__":
    threading.Thread(target=run_web, daemon=True).start()
    client.run(BOT_TOKEN)
