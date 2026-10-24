#!/usr/bin/env python3
"""
send_telegram.py
Pushes the rendered output/fenrion_short.mp4 and formatted Facebook Reels caption
directly to a Telegram chat or channel via the Telegram Bot HTTP API.
"""

import os
import sys
import html
import json
import requests


def clean_secret(raw_val: str) -> str:
    """Strips all whitespace, newlines, quotes, and accidental 'bot' prefix."""
    cleaned = "".join(raw_val.split()).strip("'\"")
    if cleaned.lower().startswith("bot") and ":" in cleaned:
        cleaned = cleaned[3:]
    return cleaned


def send_video_to_telegram(
    story_path: str = "build/story.json",
    video_path: str = "output/fenrion_short.mp4",
) -> None:
    bot_token = clean_secret(os.environ.get("TELEGRAM_BOT_TOKEN", ""))
    chat_id = "".join(os.environ.get("TELEGRAM_CHAT_ID", "").split()).strip("'\"")

    if not bot_token or not chat_id:
        print(
            "[ERROR] TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID is empty in GitHub Secrets.",
            file=sys.stderr,
        )
        sys.exit(1)

    has_colon = ":" in bot_token
    print(
        f"[DIAGNOSTIC] Token length={len(bot_token)}, contains_colon={has_colon}, "
        f"chat_id_length={len(chat_id)}"
    )

    me_resp = requests.get(f"https://api.telegram.org/bot{bot_token}/getMe", timeout=15)
    if me_resp.status_code != 200:
        print(
            f"[ERROR] Token failed /getMe check ({me_resp.status_code}): {me_resp.text}\n"
            f"[HINT] Go to GitHub -> Settings -> Secrets and variables -> Actions -> "
            f"Update TELEGRAM_BOT_TOKEN with the exact token from @BotFather.",
            file=sys.stderr,
        )
        me_resp.raise_for_status()
    else:
        bot_username = me_resp.json().get("result", {}).get("username", "unknown")
        print(f"[TELEGRAM] Authenticated successfully as @{bot_username}")

    if not os.path.exists(story_path):
        raise FileNotFoundError(f"Story metadata file missing: {story_path}")
    if not os.path.exists(video_path):
        raise FileNotFoundError(f"Rendered video file missing: {video_path}")

    with open(story_path, "r", encoding="utf-8") as f:
        story = json.load(f)

    title_safe = html.escape(story.get("title", "Fenrion Short"))
    fb_caption_safe = html.escape(story.get("facebook_caption", ""))

    caption_html = (
        f"🎬 <b>{title_safe}</b>\n\n"
        f"📋 <b>Facebook Reels / Page Caption (Tap to Copy):</b>\n"
        f"<pre>{fb_caption_safe}</pre>\n\n"
        f"<i>Wars. Commanders. Secrets.</i>"
    )

    if len(caption_html) > 1024:
        caption_html = caption_html[:1010] + "</pre>"

    endpoint = f"https://api.telegram.org/bot{bot_token}/sendVideo"
    print(f"[TELEGRAM] Uploading {video_path} to chat_id={chat_id}...")

    with open(video_path, "rb") as vf:
        response = requests.post(
            endpoint,
            data={
                "chat_id": chat_id,
                "caption": caption_html,
                "parse_mode": "HTML",
                "supports_streaming": "true",
            },
            files={"video": ("fenrion_short.mp4", vf, "video/mp4")},
            timeout=180,
        )

    if response.status_code != 200:
        print(
            f"[ERROR] Telegram API responded with {response.status_code}: {response.text}",
            file=sys.stderr,
        )
        response.raise_for_status()

    print("[SUCCESS] Video and copy-paste Facebook caption delivered to Telegram!")


if __name__ == "__main__":
    send_video_to_telegram()
