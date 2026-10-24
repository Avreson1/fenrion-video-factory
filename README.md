# 🎬 Fenrion Automated Video Factory

A 100% free, zero-cost, headless video generation and delivery pipeline designed to run locally or on a schedule via GitHub Actions. 

This repository replicates the narrative, visual, and pacing style of viral short-form documentary and military history channels (like **Fenrion** / `@fenrionmind`): cold clinical hooks, phonetic numbers for clean TTS pacing, dark gritty archival AI visuals, dynamic pop-in captions, and a signature cinematic sign-off.

---

## 🛠️ The 100% Free Tool Stack

1. **Script & Caption Generation:** Google AI Studio (`gemini-3.8-flash` / dynamic fallback) with Pydantic structured outputs for guaranteed valid JSON.
2. **Topic Queue (`topics.json`):** Automatic topic tracking that marks stories as used and commits state back to GitHub so scripts never repeat.
3. **Voiceover (TTS):** `edge-tts` (`en-US-ChristopherNeural`, `-5%` rate, `-5Hz` pitch for a deep documentary cadence).
4. **Visuals:** `Pollinations.ai` free endpoint (`flux` model, `1080x1920`, `nologo=true`) with automated procedural film-noir fallbacks.
5. **Word-Level Subtitles:** `faster-whisper` (`tiny.en`, CPU `int8`) generating animated `.ass` subtitles with yellow/white impact typography and pop-in scale effects.
6. **Video Compositing:** Native `FFmpeg` CLI subprocess calls with Ken Burns `zoompan`, noir contrast grading, vignette, and a synthesized sub-bass dark ambient drone (`aevalsrc`).
7. **Delivery:** Telegram Bot API (`sendVideo`) pushing the finished 9:16 MP4 and copy-paste Facebook Reels caption directly to your phone 3 times daily.

---

## 📁 Repository Architecture

```text
├── .github/
│   └── workflows/
│       └── generate_fenrion_video.yml   # Cron schedule (3x daily) & runner steps
├── build/                               # Temp build assets (.ass, voiceover, raw clips)
├── output/                              # Final rendered MP4 output
├── topics.json                          # Rotating queue of historical/espionage seeds
├── generate_story.py                    # LLM script & social caption generator
├── build_video.py                       # Audio, AI images, whisper & FFmpeg compositor
├── send_telegram.py                     # Telegram delivery script with pre-flight checks
└── requirements.txt                     # Python dependencies
