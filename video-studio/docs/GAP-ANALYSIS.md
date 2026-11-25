# Gap analysis and phase-2 plan: from video toolkit to AI production studio

> **Superseded (2026-11-25):** the owner chose Claude as the only agent and no OpenAI/Codex services. Current design and test status: [ARCHITECTURE.md](ARCHITECTURE.md).

Status: **proposal for approval. Nothing new has been installed.** Execution location: see [CLOUD-ARCHITECTURE.md](CLOUD-ARCHITECTURE.md) (cloud-first, chosen 2026-11-25).
Date: 2026-11-25. Base: branch `claude/codex-video-production-setup-w8gi7m` (15 skills, CPU-only).

---

## 0. The verification problem has to be solved first

The studio has only ever run inside a **Claude cloud container**. That container has been
reclaimed. The container this session runs in has no `~/.codex`, no `~/.video-studio`, no
models and no GPU (4 CPU cores, 15 GB RAM). **No machine of yours is connected to this
session**, so I cannot check your Codex environment from here. Anything I said worked there
would be a guess.

The new script `bin/vs-doctor` (read-only; it installs nothing) settles this on your side:

```bash
cd Eslam-Makrm/codex-video-studio
bin/vs-doctor --smoke        # inventory + 1-minute functional tests on your machine
bin/vs-doctor --codex        # the real proof: Codex itself runs the smoke test inside its
                             # own sandbox and lists the skills it can see
```

It checks the following:

- Codex CLI version and that `$skill-installer` is unpacked.
- All 15 skills, in every folder Codex scans, with valid `SKILL.md` frontmatter.
- ffmpeg with libass, fribidi and x264.
- Node 20+ and Chrome.
- The three virtualenvs, the Piper and Whisper models, and the Arabic fonts.
- Your hardware tier: CPU, GPU-8, GPU-16 or GPU-24+, with VRAM, RAM and free disk.

The smoke test encodes a clip, burns Arabic subtitles, speaks an Arabic line with Piper,
transcribes it back with Whisper and renders a Manim scene. Tested here, it correctly reports
the 6 studio skills present and the 9 upstream skills, venvs and models missing.

**Codex skill paths, checked against the Codex CLI 0.172.0 binary (current npm release):**
Codex scans `$CODEX_HOME/skills` (default `~/.codex/skills`, which is where
`$skill-installer` writes), `~/.agents/skills`, `<repo>/.agents/skills` and
`/etc/codex/skills`. So the existing installer's target is still valid.

The same binary ships a built-in **`imagegen`** system skill. It uses the `image_gen` tool,
needs no API key and runs against your ChatGPT plan's limits. That matters for item 3 below.

**Before approving phase 2, please run `bin/vs-doctor --codex` where you use Codex and paste
the summary.** Its `tier=` line decides which GPU components are worth installing.

---

## 1. Gap matrix

Legend: **CPU** = runs on any computer · **GPU** = needs an NVIDIA GPU (VRAM shown) or Apple
Silicon (slower) · **Online** = free service, data leaves your machine.

| # | Capability | Today | Gap | Proposed (free / open) | Runs on |
|---|---|---|---|---|---|
| 1 | Text-to-video | none; all video is code-drawn (HyperFrames, Manim, p5) | **total** | Wan2.2 TI2V-5B; Wan2.2 T2V-A14B at 24 GB | GPU 8 GB+ (5B, GGUF, ≤480p) · 24 GB for 720p |
| 2 | Image-to-video | none | **total** | Wan2.2 TI2V-5B (same model as #1); Wan2.2 I2V-A14B | GPU, as #1 |
| 3 | Image generation | none local; Codex's built-in `image_gen` (online, your plan) is unused | local engine missing | Z-Image-Turbo; FLUX.2 [klein] 4B for multi-reference edits; built-in `image_gen` as the online path | GPU 8–16 GB · Online |
| 4 | Consistent characters | code-drawn characters are consistent by construction (p5 kit) | none for AI images/video | character bible + reference sheet → reference-conditioned images (klein 4B) → I2V from keyframes; Phantom-Wan 1.3B; LoRA via ai-toolkit at 24 GB; DINOv2 similarity QC | CPU (bible, QC) · GPU |
| 5 | Arabic voice with emotion | Piper ar_JO (one flat voice, dataset licence unstated) · edge-tts (online) | emotion, dialects, a commercially clean voice, better diacritization | Chatterbox Multilingual (emotion control); Habibi-TTS MSA/EGY checkpoints (natural MSA and Egyptian); SILMA TTS (small, CPU); CATT diacritizer | CPU (SILMA, CATT) · GPU recommended (Chatterbox, Habibi) |
| 6 | Lip sync | none | **total** | 2D: Rhubarb Lip Sync → mouth shapes in p5/HyperFrames · real faces: MuseTalk 1.5; LatentSync 1.5 at 16 GB | **CPU** (Rhubarb) · GPU 6–8 GB+ |
| 7 | Script + storyboard | rules live inside each skill; no shared format | no structured script → shot list → storyboard step | `storyboard` skill: Codex writes; JSON shot list; storyboard contact sheet from code-drawn frames or AI keyframes | CPU (Codex is the writer) |
| 8 | Camera + transitions | HyperFrames/GSAP, Manim camera, `edit.py join --xfade` | no camera language for stills or AI clips, no grading | `cinematic-camera` skill: shot-size and move library, Ken Burns/zoompan, **2.5D parallax** with Depth-Anything-V2-Small, ffmpeg xfade catalogue, LUT grading, grain, letterbox · optional RIFE interpolation and Real-ESRGAN upscaling | CPU (all core parts) · GPU/Vulkan optional |
| 9 | Automated QC | `vs-verify`: streams, length, motion %, LUFS, contact sheet; manual Whisper check | no defect detection, no scoring, no gate | `video-qc` skill + `vs-qc`: black/freeze/silence/clipping detectors, true peak, Arabic OCR of frames (Tesseract `ara`), ASR word error rate vs script (jiwer), speech quality (DNSMOS), prompt match (open_clip), character consistency (DINOv2), lip-sync offset (SyncNet, GPU) → PASS/FAIL report | CPU (all but SyncNet) |
| 10 | One prompt → finished video | `video-studio` routes, but a person drives every step | no orchestrator, no project format, no resume | `video-producer` skill + `production.json`: brief → script → storyboard (approval) → assets → voice → lip sync → edit → QC gate → deliverables; resumable per stage; picks CPU/GPU/online by `vs-doctor` tier | CPU (orchestration) |

---

## 2. Component review

For each component this records the licence, hardware, risks and decision. Licences below
come from model cards and READMEs as reported in search results. In this session the primary
pages (Hugging Face, GitHub, OpenAI docs) could not be fetched. **Each licence will be
re-checked from the LICENSE file at the pinned commit before anything is installed**, as was
done for phase 1. Where I found conflicting reports, the item is marked ⚠.

### 2.1 Runtime for GPU models: ComfyUI core (recommended) vs. diffusers

| | ComfyUI core | Hugging Face diffusers |
|---|---|---|
| Licence | GPL-3.0 (the program only; your outputs are not GPL) | Apache-2.0 |
| Small GPUs | native offloading: Wan2.2-5B fits **8 GB** (ComfyUI docs) | needs manual CPU offload, slower |
| Model coverage | Wan2.2, Z-Image, FLUX.2, LTX natively | most, with lag |
| How Codex drives it | headless server + `vs-comfy` (submits API-format workflow JSON, waits, collects MP4/PNG) | Python scripts |
| Risk | third-party custom nodes run arbitrary code | lower |

**Proposal:** ComfyUI core pinned to a release tag, headless, bound to 127.0.0.1. **No
ComfyUI-Manager and no custom nodes** except ComfyUI-GGUF (city96, Apache-2.0), and only if
your GPU is under 12 GB. Workflows live in the skill as reviewed JSON. Weights are
`.safetensors`/`.gguf` only. This is one runtime for items 1–4, so nothing is duplicated.

### 2.2 Video generation (#1, #2)

| Model | Licence | VRAM (reported) | Decision |
|---|---|---|---|
| **Wan2.2 TI2V-5B** (Alibaba) | Apache-2.0 | 24 GB native 720p/24 fps; ~8 GB with ComfyUI offload; GGUF Q4 ≈ 3 GB | **Install (GPU-8+).** One model does both text-to-video and image-to-video. |
| **Wan2.2 T2V/I2V-A14B** | Apache-2.0 | 24 GB with fp8 (two 14B experts, ~30 GB disk) | **Install only at GPU-24+.** |
| Wan2.2-Animate(-2) 14B | Apache-2.0 | 24 GB+ | optional at GPU-24+ (character performs a reference motion) |
| LTX-2.x (Lightricks) | community licence, revenue threshold ($10M ARR) — not OSI | 32 GB+ | **reject by default** (licence, VRAM) |
| HunyuanVideo 1.5 (Tencent) | Tencent Hunyuan Community licence: excludes EU/UK/South Korea, MAU cap | ~14 GB with offload | **reject by default** (territorial licence); optional if you ask |
| Mochi, CogVideoX-5B | Apache / custom | 24 GB+ / 16 GB | not needed (Wan covers it) |

Real expectations: about 5 s of 720p per clip. On a 12–16 GB card a clip takes minutes to
tens of minutes. On CPU, video diffusion is **not practical** (hours per second of video),
so for a CPU-only machine the GPU path is the free cloud notebooks in 2.8.

### 2.3 Image generation (#3)

| Option | Licence | Runs on | Decision |
|---|---|---|---|
| Codex built-in `image_gen` (OpenAI) | proprietary; included in your ChatGPT plan; no API key | **Online** | **Already present — use, don't duplicate.** Best quality, and it edits from references. Prompts and images go to OpenAI. |
| **Z-Image-Turbo** (Alibaba Tongyi, 6B, 8 steps) | Apache-2.0 | GPU 16 GB (8 GB fp8, ~6 GB GGUF) | **Install (GPU-8+)** as the local default |
| **FLUX.2 [klein] 4B** (BFL) | Apache-2.0 ⚠ (the **9B is non-commercial**) | GPU ~13 GB (fp8 ~8 GB) | **Install at GPU-16+** for multi-reference character edits |
| Qwen-Image 2.x | Qwen Research licence (non-commercial) ⚠ | 24 GB+ | reject |
| FLUX.1-dev / Kontext-dev, SD-Turbo/SDXL-Turbo | non-commercial | — | reject |
| CPU image generation (stable-diffusion.cpp / FastSD-CPU) | MIT + model licence | CPU, ~0.5–5 min/image | optional, storyboards only — needs a timing test on your CPU first |

### 2.4 Consistent characters (#4)

The method is shared across engines and gets its own skill, `character-bible`:

1. **Character bible** (CPU, Codex writes it): `characters/<name>.json` with face, hair,
   clothes, palette, a fixed seed, a canonical prompt block and negatives.
2. **Reference sheet**: front, three-quarter and profile views plus 3 expressions, made once with
   `image_gen` (online) or Z-Image/klein (local). You approve it.
3. **Every scene keyframe** is made *from* the reference images (klein 4B multi-reference, or
   `image_gen` with the reference images attached), never from text alone.
4. **Video comes from keyframes** (Wan2.2 image-to-video), not from text. This is the main
   consistency lever.
5. **QC**: DINOv2-small (Apache-2.0, CPU) embedding similarity between each keyframe and
   the reference sheet. Below the threshold, the frame is regenerated.
6. At GPU-24+: optional character LoRA with **ostris/ai-toolkit** (MIT) from 15–30 approved
   images; optional Phantom-Wan 1.3B (Apache-2.0, 10–16 GB) subject-to-video.

Rejected: InstantID, PuLID and anything else built on InsightFace face models (the models are
non-commercial).
For animated stories, the p5 kit's code-drawn characters stay the default. They are already
perfectly consistent.

### 2.5 Arabic voice with emotion (#5)

| Engine | Licence | Arabic | Emotion control | Runs on | Decision |
|---|---|---|---|---|---|
| Piper `ar_JO-kareem` (present) | GPL-3.0 program; voice dataset licence **unstated** | MSA, one male voice | none | CPU, real time | keep: fast drafts |
| edge-tts (present) | LGPL; Microsoft service terms | many voices, all dialects | SSML styles are limited | **Online** | keep: opt-in |
| **Chatterbox Multilingual** (Resemble AI, 0.5B) | MIT ⚠ (verify LICENSE in the upstream repo; NVIDIA's packaged copy has other terms) | yes (one of 23 languages) | **yes:** `exaggeration` 0.25–2.0 and `cfg_weight`; zero-shot voice cloning | GPU recommended (~4–6 GB); CPU works but slowly | **Install** as the expressive engine |
| **Habibi-TTS** (SWivid, F5-TTS based) | **split:** MSA, EGY, ALG, IRQ, MAR = Apache-2.0; Unified, SAU, UAE = CC-BY-NC-SA | MSA **and dialects** (Egyptian); works without tashkeel | prosody follows the reference audio, so emotion comes from the reference clip | GPU recommended; CPU slow | **Install the MSA + EGY checkpoints only** |
| **SILMA TTS v1** (150M) | MIT code, Apache-2.0 weights | MSA + English; reads tashkeel | via the reference clip | **CPU-friendly** | **Install** as the CPU-tier quality upgrade over Piper |
| XTTS-v2 and its fine-tunes (e.g. Fasih) · Fish/OpenAudio · MMS-TTS | non-commercial | | | | reject |

The pronunciation layer is CPU and adds the following to `arabic-voiceover`:

- The **CATT** diacritizer (Abjad AI), which adds tashkeel before TTS. ⚠ Its licence was
  reported as changed from CC-BY-NC to Apache-2.0; the LICENSE file gets checked before use.
- A pronunciation lexicon (`lexicon.json`: brand names, numbers, loanwords).
- Codex shows the diacritized script for approval.
- A Whisper round-trip with a word error rate gate.

The voice-cloning rule: clone only your own voice or a voice whose owner has given written
consent. Each clone is recorded in `production.json`.

### 2.6 Lip sync (#6)

| Tool | Licence | Use | Runs on | Decision |
|---|---|---|---|---|
| **Rhubarb Lip Sync** | MIT ⚠ (the repo's LICENSE.md also lists bundled third-party code) | 2D characters: audio → mouth-shape timeline (A–H, X) used by p5 and HyperFrames rigs. The "phonetic" recognizer is language-independent, so it handles Arabic | **CPU**, faster than real time | **Install** |
| **MuseTalk 1.5** (Tencent Lyra) | MIT code; the README says the models may be used commercially; bundled sd-vae and Whisper keep their own licences | real or AI faces: re-mouths an existing video or image from audio. Audio-driven, so it works for Arabic | GPU ~4–6 GB, 30 fps on a V100 | **Install (GPU-8+)** |
| LatentSync 1.5 (ByteDance) | Apache-2.0 code ⚠ (weights reported as Apache or OpenRAIL++) | higher fidelity | 8 GB (1.5), 18 GB (1.6) | optional at GPU-16+ |
| InfiniteTalk / Wan2.2-S2V | Apache-2.0 | full talking-avatar video from image + audio | 24 GB+ | optional at GPU-24+ |
| Wav2Lip, SadTalker (older) | Wav2Lip is non-commercial | | | reject |

The `.pth` checkpoints that MuseTalk and LatentSync ship are loaded with
`torch.load(weights_only=True)`, the default from PyTorch 2.6. Any pickle that needs code
execution is refused.

### 2.7 Camera, transitions, grading (#8): all CPU

- **Shot library** (in the skill): sizes (ECU…EWS), moves (push-in, pull-out, pan, tilt,
  truck, crane, orbit, dolly-zoom, handheld), and when to use each per genre.
- Stills or AI keyframes get ffmpeg `zoompan` moves with easing.
- **2.5D parallax**: a depth map from Depth-Anything-V2-**Small** (Apache-2.0; Base and Large
  are non-commercial and are not used), CPU about 1 s per image, then a displacement camera move.
- AI clips get the move written into the Wan prompt as camera language; if the generated move
  is weak, ffmpeg adds it in post.
- Transitions: an ffmpeg `xfade` catalogue (fade, wipe, slide, circle, zoom, dissolve, whip
  via blur), plus HyperFrames shader transitions already present, plus J-cuts and L-cuts for
  audio.
- Grading: free `.cube` LUTs (CC0, or made in code), `lut3d`, grain, vignette, 2.39:1
  letterbox.
- Optional: RIFE (MIT) frame interpolation and Real-ESRGAN (BSD-3) 2–4× upscaling, both as
  ncnn-Vulkan builds. Vulkan runs on most GPUs including integrated ones; CPU is very slow.

### 2.8 Free online GPU (for a CPU-only Codex machine)

| Service | What you get (reported) | Notes |
|---|---|---|
| Kaggle Notebooks | ~30 GPU-h/week, T4×2 or P100, 12 h sessions, free account | Codex writes the notebook; you press Run; the result is downloaded. The weekly quota varies |
| Google Colab (free) | T4 16 GB when available, session limits | same pattern; availability not guaranteed |
| Hugging Face Spaces (ZeroGPU) | small daily free quota per account | per-Space terms vary; inputs go to the Space owner. Use only official Spaces |

Studio policy stays the same: no paid tiers or credits, everything opt-in, and the data-leaves-
your-machine warning is shown. Codex cloud tasks: I could not confirm the current Codex cloud
container specs (the OpenAI docs site was unreachable from here). Assume **no GPU** there.
Models must also be downloaded in the environment's **setup script**, because agent-phase
internet is off by default.

### 2.9 Automated QC (#9): `vs-qc`, CPU

The **visual** checks:

- `blackdetect` and `freezedetect`: no black frames, no stuck frames.
- `idet` and `cropdetect`: no interlacing, no unwanted borders.
- A safe-area overlay for 9:16 sheets.
- Tesseract OCR with `ara` on sampled frames, compared with the planned on-screen text. This
  catches broken Arabic shaping and wrong word order.
- open_clip ViT-B/32 (MIT): each shot is scored against its storyboard prompt.
- DINOv2-small: character similarity against the reference sheet.
- Frame flicker and exposure statistics (`signalstats`).

The **audio** checks:

- Integrated LUFS and true peak against the preset.
- `astats` clipping.
- `silencedetect` for dead air.
- Whisper on the final audio, then jiwer word error rate against the script, with a gate of
  ≤10% for MSA.
- DNSMOS (Microsoft, MIT, ONNX on CPU) speech-quality score.
- A/V offset, using SyncNet only on lip-synced shots (GPU).

The output is `qc/report.json` and `qc/report.md` with PASS/WARN/FAIL per shot. A FAIL
**blocks delivery** and points the orchestrator at the shot to regenerate (at most 2 retries,
then it asks you). Codex still opens the contact sheets and looks at them, and still tells
you it cannot hear audio.

### 2.10 One prompt → video (#10): `video-producer`

`$video-producer` takes one prompt and runs these stages:

```
"$video-producer  إعلان ٣٠ ثانية لتطبيق توصيل، عامية مصرية، ٩:١٦، شخصية شاب ثابتة"

 brief ─► script ─► storyboard ─► [APPROVAL] ─► assets ─► voice ─► lip-sync ─► edit ─► QC gate ─► deliver
 (Codex)  (Codex,    (shot list +              (per shot:  (Chatterbox/  (Rhubarb/   (ffmpeg,   (vs-qc)   MP4 + SRT +
          tashkeel)   sheet)                    code-drawn, Habibi/SILMA/ MuseTalk)  HyperFr.,            cover + report
                                                Wan, image) Piper)                   camera)
```

- **`production.json`** is the single project file: brief, format preset, characters, the
  script lines with tashkeel and emotion tags, and shots. Each shot records engine, prompt,
  camera, duration, voice line, transition and status. Every stage reads it and writes back
  its outputs, so a run **resumes** where it stopped and a single shot can be redone.
- **Engine per shot is chosen by the `vs-doctor` tier and the licence flags:**
  - CPU tier: code-drawn shots, plus stills (`image_gen` or user images) with parallax camera.
  - GPU tier: Wan image-to-video from consistent keyframes.
  - You can always force an engine.
- **There is one human checkpoint by default:** the script and storyboard are approved before
  anything expensive renders. "Don't ask" skips it.
- Genre templates: educational lesson, animated story, realistic short, advertisement and
  social reel. Each sets pacing, shot mix, caption style and QC thresholds.

---

## 3. Implementation plan (each phase needs your approval)

| Phase | What | Installs | Disk | Needs |
|---|---|---|---|---|
| **A. Prove phase 1** | You run `bin/vs-doctor --codex` where you use Codex. I fix whatever fails | nothing new | — | your machine (or connect it to a session) |
| **B. CPU core** | skills: `video-producer`, `storyboard`, `character-bible`, `cinematic-camera`, `video-qc`, `lip-sync` (Rhubarb part); `arabic-voiceover` + SILMA, CATT, lexicon; `vs-qc`, `vs-produce`; new tests that render one CPU-only end-to-end video per genre | venv-ai-cpu: onnxruntime, open_clip, DINOv2-small, Depth-Anything-V2-Small, jiwer, DNSMOS, SILMA, CATT · Rhubarb binary · tesseract-ocr-ara | ~4 GB | any computer |
| **C. GPU** (only if tier ≥ gpu-8) | ComfyUI core headless + `vs-comfy`, skills `ai-image` / `ai-video`, MuseTalk, Chatterbox, Habibi MSA/EGY; models picked by tier | venv-comfy (PyTorch CUDA or MPS), separate venv-lipsync, venv-tts-gpu | 40 GB (gpu-8) → ~90 GB (gpu-24) | NVIDIA 8 GB+ or Apple Silicon 32 GB+ |
| **C′. Cloud GPU** (CPU-only machine) | Kaggle/Colab notebook generator: Codex writes it, you run it, results are pulled into the project | nothing local | — | free Kaggle/Google account |
| **D. Acceptance** | 5 end-to-end videos from single prompts (lesson, story, realistic, ad, reel) rendered **on your machine through Codex**, each with a QC report | — | — | — |

The safeguards from phase 1 carry over:

- Every repo and model is pinned to a commit or revision hash, with sha256 recorded in
  `install.sh`.
- The LICENSE file at that revision is read before install.
- Install scripts are reviewed, with no `curl | sh`.
- `pip install` only from PyPI with pinned versions, each tool in its own venv, and
  `trust_remote_code` off.
- ComfyUI listens on localhost only, with no Manager and no unreviewed custom nodes.
- Telemetry stays off (`HF_HUB_DISABLE_TELEMETRY`, `DO_NOT_TRACK`, and ComfyUI has none
  by default).
- Nothing paid is configured. Online paths (`image_gen`, edge-tts, Kaggle/Colab/Spaces) are
  opt-in and labelled.

On Codex compatibility:

- The skills stay plain `SKILL.md` + `agents/openai.yaml` + scripts, with no Claude-specific
  tools.
- Long renders run as background processes with a progress file, so Codex is not stuck on one
  command for 30 minutes.
- Model downloads need network, which Codex's default `workspace-write` sandbox blocks. So
  `install.sh` is run once outside the sandbox (or approved in Codex), and renders then work
  offline.
- Windows: use WSL2 (bash scripts, CUDA through the Windows driver). macOS: Apple Silicon
  runs phase C via MPS, slower.

## 4. Licence summary for commercial work (ads, client videos)

| Commercially clean (permissive) | Use with care | Not used |
|---|---|---|
| Wan2.2 (all), Z-Image-Turbo, FLUX.2 klein **4B**, Chatterbox, Habibi **MSA/EGY/ALG/IRQ/MAR**, SILMA, MuseTalk code, Rhubarb, Depth-Anything-V2-**Small**, DINOv2, open_clip, RIFE, Real-ESRGAN, ComfyUI (GPL program, outputs free) | Piper ar_JO voice (dataset licence unstated), edge-tts and `image_gen` (service terms), GSAP (free no-charge licence), LatentSync weights ⚠, CATT ⚠ | LTX-2, HunyuanVideo, FLUX.1-dev/Kontext-dev, FLUX.2 klein 9B, Qwen-Image 2.x, XTTS-v2, F5-TTS base, Habibi Unified/SAU/UAE, Wav2Lip, InsightFace-based ID tools, Depth-Anything Base/Large |

Model licences do not cover the people or brands in a video. Realistic videos of real people
need their consent, and the producer skill refuses impersonation of real people.

## 5. Decisions needed from you

1. **Where does Codex run for you?** Codex CLI or app on your own Windows, macOS or Linux
   computer, or Codex cloud tasks on chatgpt.com. The answer decides whether phase C is
   possible locally.
2. **Your GPU**, or the `vs-doctor` output.
3. **Is it OK for Codex's built-in `image_gen` (online, counts against your ChatGPT plan) to be
   the default image path when no local GPU is available?**
4. **Are Kaggle/Colab notebooks acceptable** as the free GPU route if your machine has no GPU?
5. Approve phases **B** and, depending on 1–2, **C** or **C′**.

## Sources (secondary; licences to be re-verified at the pinned revision)

- Codex skill locations and the built-in imagegen skill: strings in the `@openai/codex` 0.172.0
  linux-x64 binary (npm). [Codex skills docs](https://developers.openai.com/codex/skills),
  [Codex cloud environments](https://developers.openai.com/codex/cloud/environments)
- Video models: [Wan2.2-TI2V-5B card](https://huggingface.co/Wan-AI/Wan2.2-TI2V-5B),
  [ComfyUI Wan2.2 tutorial (8 GB offload)](https://docs.comfy.org/tutorials/video/wan/wan2_2),
  [Wan-Animate-2](https://huggingface.co/Wan-AI/Wan2.2-Animate-2-14B),
  [vdf.ai VRAM and licence overview](https://vdf.ai/blog/best-local-video-generation-models/),
  [LTX-2](https://en.wikipedia.org/wiki/LTX-2)
- Images: [teamday.ai Nov 2026 image model survey](https://www.teamday.ai/blog/best-local-image-generation-models-2026),
  [Z-Image vs klein licences](https://www.criticatv.com/z-image-vs-flux-klein-vs-qwen-image-krea-2-comfyui/),
  [Z-Image-Turbo VRAM](https://runaihome.com/blog/z-image-turbo-16gb-vram-home-lab-image-gen-2026/)
- Characters: [Phantom](https://huggingface.co/qqceqqq/Phantom/blob/main/README.md)
- Arabic TTS: [Chatterbox (Resemble AI)](https://www.resemble.ai/learn/models/chatterbox),
  [Chatterbox model card](https://huggingface.co/ResembleAI/chatterbox),
  [Habibi-TTS card](https://huggingface.co/SWivid/Habibi-TTS/blob/main/README.md),
  [SILMA TTS](https://github.com/silma-ai/silma-tts),
  [catt-tashkeel (licence note)](https://pypi.org/project/catt-tashkeel/),
  [Arabic TTS benchmark 2026](https://arxiv.org/html/2603.01622)
- Lip sync: [open-source lip-sync licence guide](https://tomodahinata.com/en/blog/ai-lip-sync-talking-head-model-selection-guide-2026),
  [MuseTalk guide](https://tomodahinata.com/en/blog/musetalk-realtime-lip-sync-production-guide),
  [LatentSync guide](https://tomodahinata.com/en/blog/latentsync-lip-sync-diffusion-model-production-guide),
  [Rhubarb WASM README](https://unpkg.com/rhubarb-lip-sync-wasm@0.1.8/README.md)
- Free GPU: [Free cloud GPUs in 2026](https://gpuperhour.com/blog/free-cloud-gpus-and-credits)
