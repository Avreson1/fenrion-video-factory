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


def send_video_to_telegram(
    story_path: str = "build/story.json",
    video_path: str = "output/fenrion_short.mp4",
) -> None:
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")

    if not bot_token or not chat_id:
        print(
            "[ERROR] TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID must be set in environment.",
            file=sys.stderr,
        )
        sys.exit(1)

    if not os.path.exists(story_path):
        raise FileNotFoundError(f"Story metadata file missing: {story_path}")
    if not os.path.exists(video_path):
        raise FileNotFoundError(f"Rendered video file missing: {video_path}")

    with open(story_path, "r", encoding="utf-8") as f:
        story = json.load(f)

    title_safe = html.escape(story.get("title", "Fenrion Short"))
    fb_caption_safe = html.escape(story.get("facebook_caption", ""))

    caption_html = (
        f"🎬 <b>{title_safe}</b>

"
        f"📋 <b>Facebook Reels / Page Caption (Tap to Copy):</b>
"
        f"<pre>{fb_caption_safe}</pre>

"
        f"<i>Wars. Commanders. Secrets.</i>"
    )

    # Telegram sendVideo caption limit is 1024 characters
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
        print(f"[ERROR] Telegram API responded with {response.status_code}: {response.text}", file=sys.stderr)
        response.raise_for_status()

    print("[SUCCESS] Video and copy-paste Facebook caption delivered to Telegram!")


if __name__ == "__main__":
    send_video_to_telegram()
