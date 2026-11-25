---
name: character-bible
description: Keep characters consistent across every scene of a video or series — a written character bible (look, outfit, palette, age, canonical prompt, seed), a reference sheet generated once and approved, keyframes generated from it, image-to-video from those keyframes, and automatic similarity checks (DINOv2) that flag off-model shots. Use whenever a person, mascot or animal appears in more than one shot, for "same character", "consistent character", "شخصية ثابتة", "series", "mascot".
---

# Character bible

Consistency comes from **one fixed description + references + image-to-video**, checked automatically.

1. **Write the bible** in `production.json → characters.<name>`:
   ```json
   "omar": {"prompt": "Omar, 28, Egyptian courier, short black hair, trimmed beard, warm brown eyes, orange jacket with one white stripe, navy jeans, white sneakers",
            "refs": ["characters/omar/front.png", "characters/omar/three-quarter.png"], "seed": 4242}
   ```
   Concrete, visual, unchanging attributes only (no moods, no actions). Same wording every time.
2. **Reference sheet** — one `image_zimage.py` job with 3–4 items using the bible prompt + "character
   reference sheet, neutral grey background, full body / three-quarter / close-up portrait", same seed.
   Look at them, pick the best, save under `characters/<name>/`. Show the person if the series matters.
3. **Every shot with the character:** `"characters": ["omar"]` — `vs-produce` appends the bible prompt to
   the shot prompt. For motion shots use `ai-video` **from a keyframe** (image-to-video), never pure
   text-to-video.
4. **QC:** `vs-qc` compares a frame of each tagged shot with the refs (DINOv2-small, cosine). Below 0.55 →
   regenerate that keyframe (new seed, same prompt) — max 2 tries, then pick the closest.
5. **2D / code-drawn characters** (animated-stories, HyperFrames) are consistent by construction: keep their
   drawing function in one file and reuse it across shots and episodes.

Series: keep `characters/` and the bible JSON in the repo so later episodes reuse them.
Never design characters that copy existing IP or a real person's likeness.
