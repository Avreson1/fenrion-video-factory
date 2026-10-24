#!/usr/bin/env python3
"""
generate_story.py
Generates a 6-scene Fenrion-style military history / espionage script, visual prompts,
and Facebook Reels caption using Google AI Studio (gemini-2.5-flash) with Pydantic structured outputs.
"""

import os
import sys
import json
import argparse
from typing import List
from pydantic import BaseModel, Field
from google import genai
from google.genai import types


class Scene(BaseModel):
    narration: str = Field(
        description=(
            "1 to 2 gripping, clinical documentary sentences for this scene. "
            "CRITICAL RULE: Write ALL numbers, dates, years, and frequencies phonetically in words "
            "(e.g., 'nineteen eighty-two', 'four six two five kilohertz', 'twenty-eight years'). "
            "Never use digits."
        )
    )
    image_prompt: str = Field(
        description=(
            "Detailed visual prompt for an AI image generator: dark gritty 35mm archival documentary "
            "photograph, chiaroscuro lighting, heavy shadows, cold war noir atmosphere, historical realism, "
            "vertical 9:16 composition, zero text or watermarks."
        )
    )


class FenrionStory(BaseModel):
    title: str = Field(
        description="Punchy, cold 3 to 6 word documentary title for the video."
    )
    facebook_caption: str = Field(
        description=(
            "A gripping 2-sentence Facebook Reels hook caption followed by a blank line and "
            "exactly 5 niche hashtags (#coldwar #espionage #militaryhistory #declassified #fenrion)."
        )
    )
    scenes: List[Scene] = Field(
        description="Exactly 6 chronological scenes totaling 130 to 150 words of narration.",
        min_length=6,
        max_length=6,
    )


SYSTEM_PROMPT = """You are the head documentary writer for 'Fenrion' (@fenrionmind), a viral short-form channel covering declassified military history, Cold War espionage, and vanished operatives.

STRICT PRODUCTION RULES:
1. Total narration across all 6 scenes MUST be between 130 and 150 words.
2. NEVER start with weak hooks like 'Did you know?' or 'In this video'. Start immediately inside the tension (e.g., 'November nineteen seventy-one. A man in a dark raincoat steps onto a tarmac...').
3. PHONETIC NUMBERS RULE: Every single number, year, frequency, unit, or measurement in the narration MUST be spelled out in words so the TTS engine reads with natural documentary cadence (e.g., 'nineteen forty-three', 'twenty-five times a minute', 'four six two five kilohertz'). Do NOT output numerical digits in the narration field.
4. SIGNATURE OUTRO RULE: Scene 6 narration MUST end with the exact signature sign-off:
   'Wars. Commanders. Secrets. Follow for the stories nobody finished telling.'
5. VISUAL CONTINUITY: Each scene's `image_prompt` must describe a moody, dark, high-contrast 35mm archival photograph with dramatic chiaroscuro lighting and zero text."""


def select_and_mark_topic(custom_topic: str = "") -> str:
    """Pulls the first unused topic from topics.json and marks it used, or returns custom_topic."""
    if custom_topic and custom_topic.strip():
        print(f"[INFO] Using custom CLI topic: {custom_topic.strip()}")
        return custom_topic.strip()

    topics_file = "topics.json"
    if os.path.exists(topics_file):
        with open(topics_file, "r", encoding="utf-8") as f:
            topics = json.load(f)

        for entry in topics:
            if not entry.get("used", False):
                chosen = entry["topic"]
                entry["used"] = True
                with open(topics_file, "w", encoding="utf-8") as fw:
                    json.dump(topics, fw, indent=2, ensure_ascii=False)
                print(f"[INFO] Pulled topic from queue: {chosen}")
                return chosen

    print("[INFO] All topics in topics.json are marked used. Instructing Gemini to invent a new topic.")
    return (
        "Select a real, obscure, declassified Cold War espionage operation, mysterious military signal, "
        "or forgotten wartime operative that sounds like an espionage thriller."
    )


def generate_story(topic: str, output_path: str = "build/story.json") -> None:
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    api_key = os.environ.get("GEMINI_API_KEY")

    if not api_key:
        print("[ERROR] GEMINI_API_KEY environment variable is not set.", file=sys.stderr)
        sys.exit(1)

    client = genai.Client(api_key=api_key)
    print(f"[INFO] Requesting structured Fenrion script from gemini-2.5-flash...")

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=f"Write a 6-scene Fenrion documentary script about: {topic}",
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            response_mime_type="application/json",
            response_schema=FenrionStory,
            temperature=0.7,
        ),
    )

    story_dict = json.loads(response.text)

    # Validate scene count & enforce sign-off safety check
    scenes = story_dict.get("scenes", [])
    if len(scenes) != 6:
        raise RuntimeError(f"Expected 6 scenes from Gemini, got {len(scenes)}")

    sign_off = "Wars. Commanders. Secrets. Follow for the stories nobody finished telling."
    if sign_off.lower() not in scenes[-1]["narration"].lower():
        scenes[-1]["narration"] = scenes[-1]["narration"].rstrip() + " " + sign_off

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(story_dict, f, indent=2, ensure_ascii=False)

    word_count = sum(len(s["narration"].split()) for s in scenes)
    print(f"[SUCCESS] Generated '{story_dict['title']}' ({word_count} words) -> {output_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate Fenrion story JSON via Google AI Studio.")
    parser.add_argument("--topic", type=str, default="", help="Optional custom topic override.")
    args = parser.parse_args()

    topic_to_run = select_and_mark_topic(args.topic)
    generate_story(topic_to_run)
