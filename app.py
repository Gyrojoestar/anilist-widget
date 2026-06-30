import os
import json
import time
from pathlib import Path
from urllib.parse import urlencode

import requests
from flask import Flask, request, redirect

app = Flask(__name__)

CLIENT_ID = os.environ["DISCORD_CLIENT_ID"]
CLIENT_SECRET = os.environ["DISCORD_CLIENT_SECRET"]
REDIRECT_URI = os.environ["DISCORD_REDIRECT_URI"]  # e.g. https://your-app.onrender.com/verify-user

API_BASE = "https://discord.com/api/v10"
TOKENS_FILE = Path("tokens.json")


def load_tokens():
    if TOKENS_FILE.exists():
        return json.loads(TOKENS_FILE.read_text())
    return {}


def save_tokens(tokens):
    TOKENS_FILE.write_text(json.dumps(tokens))


def store_user_tokens(user_id, token_data):
    tokens = load_tokens()
    token_data["expires_at"] = time.time() + token_data["expires_in"]
    tokens[user_id] = token_data
    save_tokens(tokens)


def get_user_tokens(user_id):
    return load_tokens().get(user_id)


def refresh_token_if_needed(user_id):
    data = get_user_tokens(user_id)
    if not data:
        return None
    if time.time() < data["expires_at"] - 60:
        return data["access_token"]

    resp = requests.post(
        f"{API_BASE}/oauth2/token",
        data={
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "grant_type": "refresh_token",
            "refresh_token": data["refresh_token"],
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    resp.raise_for_status()
    new_data = resp.json()
    store_user_tokens(user_id, new_data)
    return new_data["access_token"]


@app.route("/linked-role")
def linked_role():
    params = {
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": "identify role_connections.write",
        "prompt": "consent",
    }
    return redirect(f"https://discord.com/oauth2/authorize?{urlencode(params)}")


@app.route("/verify-user")
def verify_user():
    code = request.args.get("code")
    if not code:
        return "Missing code", 400

    token_resp = requests.post(
        f"{API_BASE}/oauth2/token",
        data={
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": REDIRECT_URI,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    token_resp.raise_for_status()
    token_data = token_resp.json()

    user_resp = requests.get(
        f"{API_BASE}/users/@me",
        headers={"Authorization": f"Bearer {token_data['access_token']}"},
    )
    user_resp.raise_for_status()
    user_id = user_resp.json()["id"]

    store_user_tokens(user_id, token_data)
    push_metadata_for_user(user_id)

    return f"Linked successfully as Discord user {user_id}. You can close this tab."


def push_metadata_for_user(user_id):
    access_token = refresh_token_if_needed(user_id)
    if not access_token:
        return False

    from anilist_sync import fetch_anilist_data, build_metadata_payload

    stats = fetch_anilist_data()
    if not stats:
        return False
    metadata = build_metadata_payload(stats)

    resp = requests.put(
        f"{API_BASE}/users/@me/applications/{CLIENT_ID}/role-connection",
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        },
        json={
            "platform_name": "AniList",
            "metadata": metadata,
        },
    )
    print(f"Role connection update: {resp.status_code} {resp.text}")
    return resp.status_code in (200, 204)


@app.route("/sync/<user_id>")
def manual_sync(user_id):
    ok = push_metadata_for_user(user_id)
    return ("Synced", 200) if ok else ("Sync failed", 500)


@app.route("/")
def index():
    return "AniList Discord Linked Roles service is running."


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
