#!/usr/bin/env python3
"""
generate_story.py
Generates a 6-scene Fenrion-style military history / espionage script, visual prompts,
and Facebook Reels caption using Google AI Studio with retries, dynamic model discovery,
and an automatic fallback so 503 traffic spikes never break the build.
"""

import os
import sys
import json
import time
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


FALLBACK_STORY = {
    "title": "The Ghost Signal UVB-76",
    "facebook_caption": (
        "Since nineteen eighty-two, a bunker deep in the Russian marshes has broadcast a relentless "
        "buzzing signal that nobody outside Moscow can explain.\n\n"
        "#coldwar #espionage #militaryhistory #declassified #fenrion"
    ),
    "scenes": [
        {
            "narration": "There is a shortwave frequency at four six two five kilohertz that anyone with an analog receiver can hear tonight.",
            "image_prompt": "Dark gritty 1980s Soviet military radio room, glowing vacuum tubes, heavy shadows, 35mm archival film grain, chiaroscuro lighting, vertical 9:16, no text"
        },
        {
            "narration": "It is not encrypted. What you hear is a harsh mechanical buzzing tone, repeated twenty-five times a minute, every hour since nineteen eighty-two.",
            "image_prompt": "Extreme close up of vintage analog oscilloscope showing sharp audio waveform in a dark concrete bunker, high contrast noir photography, vertical 9:16, no text"
        },
        {
            "narration": "Western intelligence calls it the Buzzer. Its Soviet military designation is U V B seventy-six, transmitting from a guarded compound deep in the Russian marshes.",
            "image_prompt": "Abandoned overgrown military radio tower in a foggy pine forest at dusk, rusted barbed wire fence, bleak Cold War atmosphere, 35mm archival photo, vertical 9:16, no text"
        },
        {
            "narration": "Every few years, without warning, the buzzing stops. A heavy microphone clicks open, and a cold voice reads a sequence of Russian names and numbers.",
            "image_prompt": "Silhouette of a Soviet intelligence officer speaking into an old iron microphone in a dimly lit bunker room, dramatic rim lighting, archival documentary style, vertical 9:16, no text"
        },
        {
            "narration": "In two thousand ten, civilian listeners heard footsteps and muffled voices scrambling behind the microphone. Somebody is still manning that room.",
            "image_prompt": "Long dark concrete corridor inside an underground Soviet command bunker, single flickering fluorescent tube, eerie suspense, photorealistic 35mm film grain, vertical 9:16, no text"
        },
        {
            "narration": "Nobody outside the Kremlin knows what protocol activates if that signal ever goes dead. Wars. Commanders. Secrets. Follow for the stories nobody finished telling.",
            "image_prompt": "High contrast moody aerial shot of a hidden forest bunker entrance under heavy storm clouds, cinematic cold war noir grading, archival style, vertical 9:16, no text"
        }
    ]
}


def select_and_mark_topic(custom_topic: str = "") -> str:
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

    return (
        "Select a real, obscure, declassified Cold War espionage operation, mysterious military signal, "
        "or forgotten wartime operative that sounds like an espionage thriller."
    )


def get_candidate_models(client: genai.Client) -> List[str]:
    priority = [
        "gemini-3.8-flash",
        "gemini-3.8-flash-lite",
        "gemini-3.1-pro-preview",
        "gemini-3.1-flash",
        "gemini-flash-latest",
    ]
    try:
        for m in client.models.list():
            name = m.name.replace("models/", "")
            if "gemini" in name and ("flash" in name or "pro" in name) and "embedding" not in name and "vision" not in name:
                if name not in priority:
                    priority.append(name)
    except Exception as exc:
        print(f"[WARN] Could not list models dynamically: {exc}")
    return priority


def generate_story(topic: str, output_path: str = "build/story.json") -> None:
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    api_key = os.environ.get("GEMINI_API_KEY")

    story_dict = None

    if api_key:
        client = genai.Client(api_key=api_key)
        candidate_models = get_candidate_models(client)
        print(f"[INFO] Candidate models queue: {candidate_models[:8]}")

        for model_name in candidate_models:
            for attempt in range(1, 4):
                try:
                    print(f"[INFO] Requesting script from {model_name} (Attempt {attempt}/3)...")
                    response = client.models.generate_content(
                        model=model_name,
                        contents=f"Write a 6-scene Fenrion documentary script about: {topic}",
                        config=types.GenerateContentConfig(
                            system_instruction=SYSTEM_PROMPT,
                            response_mime_type="application/json",
                            response_schema=FenrionStory,
                            temperature=0.7,
                        ),
                    )
                    story_dict = json.loads(response.text)
                    print(f"[INFO] Successfully generated script with {model_name}!")
                    break
                except Exception as exc:
                    err_str = str(exc)
                    print(f"[WARN] {model_name} attempt {attempt} failed: {err_str[:220]}")
                    if "503" in err_str or "UNAVAILABLE" in err_str or "429" in err_str:
                        wait_s = 6 * attempt
                        print(f"[INFO] Waiting {wait_s}s for demand spike to clear...")
                        time.sleep(wait_s)
                    else:
                        break
            if story_dict is not None:
                break

    if story_dict is None:
        print("[WARN] All live Gemini endpoints were busy. Using built-in Fenrion production script so build continues!")
        story_dict = FALLBACK_STORY

    scenes = story_dict.get("scenes", [])
    sign_off = "Wars. Commanders. Secrets. Follow for the stories nobody finished telling."
    if scenes and sign_off.lower() not in scenes[-1]["narration"].lower():
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
