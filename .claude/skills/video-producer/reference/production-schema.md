# production.json

One file per video, in `videos/<slug>/production.json`. Paths are relative to that folder.
`vs-produce` reads it, fills in generated `source`/`keyframe` paths and writes `_timeline` /
`_deliverable`; the route taken per shot is logged in `build/route.json`.

```jsonc
{
  "title": "تطبيق توصيل — إعلان ٣٠ ثانية",
  "slug": "delivery-ad",                 // output file name
  "template": "advert",                  // advert | lesson | story | realistic | social
  "lang": "ar",                          // ar | en (narration, QC speech check, subtitles)
  "format": "reel",                      // reel 1080x1920 | youtube 1920x1080 | square 1080x1080 | feed 1080x1350
  "fps": 30,
  "style": "cinematic photo, soft golden light, shallow depth of field",   // appended to every AI prompt
  "voice": {"engine": "chatterbox", "voice": null, "ref": null, "length_scale": 1.0},
  "music": {"track": null, "volume": 0.18},          // person's track or CC0 only; ducked under the voice
  "grade": {"look": "teal-orange", "grain": 3, "vignette": true},
  "subtitles": {"burn": true, "style": "reel", "keep_tashkeel": false},
  "gpu": {"accelerator": "NvidiaTeslaT4", "video_steps": 30},             // or NvidiaL4 (faster, 24 GB)
  "characters": {
    "omar": {"prompt": "Omar, 28, Egyptian courier, short black hair, trimmed beard, orange jacket with white stripe",
             "refs": ["characters/omar/front.png"]}
  },
  "shots": [
    {
      "id": "s01",
      "engine": "ai-video",              // still | clip | ai-image | ai-video
      "prompt": "a courier on a scooter weaves through a busy Cairo street at sunrise, slow tracking shot",
      "keyframe": null,                  // ai-video: generated first when null (Z-Image), then animated (Wan2.2)
      "source": null,                    // still: image · clip: mp4 · filled in by the gen stage
      "seed": 7,
      "camera": {"move": "dolly-in", "parallax": true, "amount": 0.1},       // used for stills / fallbacks
      "vo": "وَصَلَ طَلَبُكَ قَبْلَ أَنْ تَشْتَاقَ إِلَيْهِ.",
      "subtitle": null,                  // optional caption text if different from vo
      "emotion": 0.6,                    // chatterbox exaggeration 0.25 calm … 1.0 dramatic
      "dur": 3.0,                        // minimum; stretched to fit the narration + pad
      "pad": 0.45, "vo_lead": 0.25,
      "transition": "fade",              // into the next shot: cut, fade, fadeblack, dissolve, wipeleft, slideleft,
      "transition_dur": 0.5,             //   smoothleft, circleopen, zoomin, hblur, radial, … (ffmpeg xfade)
      "onscreen_text": "",               // text you expect to be visible (checked by OCR)
      "characters": ["omar"]             // checked against refs (DINOv2)
    }
  ]
}
```

Camera moves: push-in, pull-out, pan-left/right, tilt-up/down, truck-left/right, crane-up/down,
orbit-left/right, dolly-in, dolly-zoom, handheld, static (`parallax: true` adds 2.5D depth).

Stages: `vs-produce DIR --stage gen|voice|shots|edit|qc`; `--gpu off` forces CPU-only fallbacks;
`--force` re-voices and re-renders. Change a shot → rerun; unchanged shots are reused.
