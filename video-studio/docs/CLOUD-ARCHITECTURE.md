# Cloud-first architecture: Codex Cloud + free cloud GPUs

> **Superseded (2026-11-25):** the owner chose Claude as the only agent and no OpenAI/Codex services. Current design and test status: [ARCHITECTURE.md](ARCHITECTURE.md).

Status: **proposal for approval** (2026-11-25). It replaces the local-GPU parts of
[GAP-ANALYSIS.md](GAP-ANALYSIS.md). The component choices there still stand; this file
decides **where each component runs**.

Each claim below is tagged with how it was checked:

- **[docs]**: read on the provider's official page today.
- **[code]**: read in the provider's own published client code.
- **[api]**: read from the Hugging Face model API.
- **[reported]**: from secondary sources only.
- **[test]**: unknown until it is run once in your Codex Cloud account (Phase A′).

---

## 1. Phases B, C and C′

| | Phase B: CPU core | Phase C: local GPU | Phase C′: cloud GPU |
|---|---|---|---|
| What it is | everything that needs no GPU: script and storyboard, Arabic and English TTS on CPU (Piper, SILMA), code-drawn animation (HyperFrames, Manim, p5), camera moves and parallax, editing, subtitles, automated QC, and the one-prompt orchestrator | AI models (Wan2.2, Z-Image, MuseTalk, Chatterbox…) on **your own** NVIDIA or Apple GPU | the same AI models on **free cloud GPUs** (Kaggle, Hugging Face ZeroGPU), submitted and collected **by Codex** |
| Runs in | the Codex Cloud task VM | your computer | Kaggle / HF, driven from Codex Cloud |
| Fits your requirements? | **required**: it is the backbone, and every video passes through it | **no**: it depends on local hardware | **yes**: it is the only free way to get GPU generation without local hardware |

**Recommendation: Phase B + Phase C′ (automated), orchestrated from Codex Cloud. Drop
Phase C.**

C′ changes from the earlier plan. Earlier it meant "Codex writes a notebook, you press Run".
Now it means a **fully automated Kaggle backend**: Codex submits the GPU job, waits for it
and downloads the result, with no clicks. Colab stays as a manual fallback only, for the
reasons in §3.

---

## 2. What Codex Cloud gives us (verified)

| Fact | Source |
|---|---|
| Each task is a VM. **Plus: 2 vCPU / 8 GiB RAM / 8 GiB disk. Pro, Business, Enterprise: 4 vCPU / 16 GiB / 32 GiB.** No GPU is listed; larger VMs are Enterprise only | [docs] Cloud environments → VM specifications |
| **Skills stored in the repository are available in cloud tasks; personal skills from your computer are not synced.** So the studio's skills must move into the repo under `.agents/skills/` | [docs] Cloud environments → Current limitations; Build skills → `$REPO_ROOT/.agents/skills` |
| Environments: Codex writes and tests an **install script** and a **start skill**; the prepared filesystem is published and reused by new tasks | [docs] |
| Internet: full access, or an allowlist of exact hosts; package-manager preset available | [docs] |
| **Network secrets**: the program sees a placeholder and the proxy substitutes the real value, HTTPS on port 443 only, for allowed domains, during setup and tasks. Environment variables are passed raw | [docs] |
| A task keeps working while your computer is asleep; its VM state is recoverable for 7 days | [docs] |
| HTTP Previews: a private HTTPS link to a port in the task (useful to watch or download the MP4). Availability "varies by app version and workspace" | [docs] → [test] |
| Built-in image generation uses `gpt-image-2` and counts toward Codex usage limits, consuming them **3–5× faster** per turn. **Not available on the Free plan.** It is documented for the app, CLI and IDE; **for cloud tasks it is not stated** | [docs] → **[test]** |
| Cloud tasks may use more of the plan allowance than local messages; Pro has no five-hour limit | [docs] pricing |
| Maximum length of one cloud task or turn: **not documented** | **[test]** |
| Scheduled tasks exist (web and desktop app) and can use skills, so a finished GPU job can be collected later | [docs] |

Consequences:

1. **On Plus, 8 GiB of disk is the binding limit.** The phase-1 studio needs about 4 GB of
   models plus Chrome, LaTeX and the venvs. The cloud build has to be slimmed (§5). Pro's 32
   GiB is comfortable.
2. All heavy models live and run **on Kaggle**, never in the Codex VM. The VM only
   orchestrates, edits, encodes, voices on CPU and runs QC.

---

## 3. Free GPU providers (verified limits)

| | **Kaggle** (primary) | **HF ZeroGPU** (secondary) | **Google Colab free** (manual only) |
|---|---|---|---|
| Automatable from Codex? | **Yes.** The official `kaggle` CLI pushes a kernel with GPU and internet on, runs it, reports status and downloads `/kaggle/working` output [docs]. It talks to `api.kaggle.com` with an `Authorization: Bearer` token taken from `KAGGLE_API_TOKEN` [code], which is exactly what Codex network secrets substitute | Yes, through `gradio_client` with an HF token | **No.** The free tier disallows "bypassing the notebook UI to interact primarily via a web UI" and "remote control", and prioritises "users who are actively programming in a notebook" [docs] |
| GPU | T4 ×2 (`NvidiaTeslaT4`, default) or **L4** (`NvidiaL4`) selectable per run [docs] | half or full RTX Pro 6000 Blackwell (48 / 96 GB) [docs] | varies, not published [docs] |
| Quota | ~30 GPU-hours/week, 12 h per session [reported]; phone-verified account needed for GPU and internet [reported] | **free account: 5 min GPU per day**, 60 s default per call [docs]. Free accounts cannot go into paid credits; only PRO can [docs] | not published, fluctuates, max 12 h [docs] |
| Good for | everything heavy: Wan2.2 video, Z-Image and FLUX.2-klein images, MuseTalk/LatentSync lip sync, Chatterbox/Habibi voices, upscaling. Batched per production | a few quick images or TTS lines when the Kaggle queue is slow | rescue when Kaggle quota is used up: Codex prepares the notebook, you press Run |
| Restrictions | Kaggle terms; outputs per run in `/kaggle/working` | per-Space terms; your inputs go to the Space | "creating deepfakes" is disallowed on **all** Colab runtimes [docs] |

The studio rule applies to every provider: **no realistic video of a real person without that
person's consent, and no impersonation.** Colab's deepfake ban is one more reason the
lip-sync path never runs there.

**What the free tier realistically delivers** (estimates, to be measured in Phase A′):

- Wan2.2-TI2V-5B: one 5 s 720p clip per GPU run of several minutes on L4, slower on T4. T4
  has no bf16, so it runs in fp16.
- A 60 s ad built from 10–12 generated shots costs roughly 1.5–3 GPU-hours, so the weekly
  quota covers about 10–20 such videos.
- Images and TTS are cheap; generated video is the scarce resource.

The router therefore mixes engines: generated hero shots, plus images with camera moves,
plus code-drawn motion graphics.

---

## 4. Architecture

```
            ┌──────────────────────── Codex Cloud task (CPU VM, the brain) ────────────────────────┐
 one prompt │ $video-producer                                                                       │
 ──────────►│  1 brief → script (AR/EN, tashkeel, emotion tags) → storyboard → production.json      │
            │  2 router: per shot pick engine + compute (quality × licence × quota × time)          │
            │  3 CPU work here: HyperFrames/Manim/p5, Piper/SILMA voice, camera/parallax, edit, subs │
            │  4 GPU work → job pack (one notebook per production, all shots batched) ─────────────┼──► Kaggle GPU (T4×2 / L4)
            │  5 poll status, download outputs ◄───────────────────────────────────────────────────┼─── /kaggle/working/*.mp4,png,wav
            │  6 assemble, mix, loudness → 7 vs-qc gate (regenerate failed shots, max 2)            │
            │  8 deliver: final MP4 + SRT + cover + QC report                                       │
            └───────────┬───────────────────────────────────────────────────────┬───────────────────┘
                        │ optional quick calls                                  │ manual rescue
                 HF ZeroGPU Space (5 min/day)                         Colab notebook (you press Run)
                 Codex image_gen (if available in cloud)
```

### 4.1 Automatic selection of model and compute

`vs-route` reads `production.json`, the licence policy and live state:

- `vs-doctor` for the VM size.
- Kaggle quota left: tracked locally from run times, because Kaggle has no quota API
  [reported].
- Whether `image_gen` works in this task.
- Queue time of the last job.

For each shot it picks the best available option in this order:

| Need | 1st choice | then | last resort (always works) |
|---|---|---|---|
| Hero video shot | Kaggle **L4** → Wan2.2-TI2V-5B 720p from a keyframe | Kaggle T4 → Wan2.2-5B 480p, upscaled | keyframe + parallax and camera move (CPU) |
| Keyframe / image | Codex `image_gen` (best quality; uses plan allowance) | Kaggle Z-Image-Turbo / FLUX.2-klein-4B (reference-consistent) | code-drawn illustration |
| Arabic voice, expressive | Kaggle Chatterbox Multilingual (emotion control) or Habibi MSA/EGY | SILMA on CPU | Piper on CPU (and edge-tts, online, if allowed) |
| English voice | Kaggle Chatterbox | Kokoro on CPU (explainroo) | Piper |
| Lip sync, real face | Kaggle MuseTalk 1.5 | LatentSync 1.5 | no lip sync: a cutaway or narrator off-screen |
| Lip sync, 2D character | Rhubarb on CPU | — | — |
| Motion graphics, lessons | CPU (HyperFrames, Manim) | — | — |

Every choice is written into `production.json` with its reason, so any shot can be re-run
on a different engine.

### 4.2 Reusable workflows

Five genre templates (`.agents/skills/video-producer/templates/*.json`): **educational
lesson, animated story, realistic short, advertisement, social reel**. Each fixes:

- aspect ratio and length;
- shot mix (generated / image + camera / motion graphics);
- voice style and emotion range;
- caption style;
- transition set;
- music bed rules;
- QC thresholds.

A new video is one prompt plus, optionally, a template name.

### 4.3 Manual steps that remain

| When | What you do | Why it can't be automated |
|---|---|---|
| once | create a Kaggle account, verify your phone, create an API token, save it in Codex as a network secret | account security (done in the Kaggle and Codex UIs) |
| once | create the Codex Cloud environment from this repo (Codex writes the install script itself) and publish it | done in ChatGPT settings, not from here |
| optional per video | approve the script and storyboard (skippable with "don't ask") | the cheapest point to correct course |
| per video | download the MP4 (§4.4) | — |
| rare | press Run on a Colab notebook when Kaggle quota is exhausted | Colab's free-tier rules |

### 4.4 Getting the MP4 out of Codex Cloud

To be confirmed in Phase A′ [test]:

1. **Commit to an output branch.** A typical 1080p 60 s file is 20–60 MB, under GitHub's
   100 MB per-file limit. Codex Cloud already commits and opens PRs. Whether binary files
   survive its diff/PR flow is **[test]**.
2. **HTTP Preview link** from the task (private), if your app/workspace offers it.
3. **Private Kaggle dataset version** (`kaggle datasets version`): the file downloads from
   Kaggle's site or app.

---

## 5. Changes needed to the existing studio for the cloud

- Move the 15 skills into the repo at `.agents/skills/`. The upstream skills are vendored at
  their pinned commits with their LICENSE files (Apache-2.0 and MIT allow this). `install.sh
  --cloud` then installs only tools and models, not skills.
- **Slim build for the 8 GiB Plus disk:**
  - Whisper `small` only (no large-v3-turbo).
  - LaTeX limited to `texlive-latex-base` + `dvisvgm`.
  - Chrome via the Playwright build that is already in the image, if one is present.
  - Total target ≤ 3 GB.
  - Pro gets the full build.
- Add `KAGGLE_USERNAME` (environment variable) and `KAGGLE_API_TOKEN` (network secret for
  `api.kaggle.com`).
- Hosts to allow in the agent phase:
  - `api.kaggle.com` and `www.kaggle.com`;
  - the storage host Kaggle serves outputs from [test];
  - `huggingface.co` + CDN hosts (model metadata, ZeroGPU);
  - `speech.platform.bing.com` (edge-tts, opt-in).
- Long GPU jobs: `vs-gpu submit` returns at once, and `vs-gpu wait` polls with a timeout. If
  a turn limit exists [test], the task saves state and a Codex **scheduled task** collects
  the outputs later.

---

## 6. Licence check

Re-checked today from each model's Hugging Face card [api]:

| Model | Card licence | Use |
|---|---|---|
| Wan-AI/Wan2.2-TI2V-5B, Wan2.2-I2V-A14B, Wan2.2-Animate-14B | apache-2.0 | ✅ commercial |
| Tongyi-MAI/Z-Image-Turbo | apache-2.0 | ✅ |
| black-forest-labs/FLUX.2-klein-4B | apache-2.0 | ✅ (the 9B is `flux-non-commercial-license` ❌) |
| ResembleAI/chatterbox | mit | ✅ |
| SWivid/Habibi-TTS | card: cc-by-nc-sa-4.0; README: **ALG, EGY, IRQ, MAR, MSA are Apache-2.0**; Unified, SAU, UAE are NC | ✅ MSA and EGY only |
| silma-ai/silma-tts | apache-2.0 | ✅ |
| TMElyralab/MuseTalk | mit | ✅ (bundled sd-vae and Whisper keep their own licences) |
| ByteDance/LatentSync-1.5 | openrail++ | ✅ with use restrictions (no deception or harm) |
| MeiGen-AI/InfiniteTalk | apache-2.0 | ✅ (needs more VRAM than T4 has) |
| depth-anything/Depth-Anything-V2-Small, facebook/dinov2-small | apache-2.0 | ✅ |

Still to check from their repos before install: CATT (tashkeel), Rhubarb, ComfyUI version pin.

---

## 7. Phase A′: verification in your Codex Cloud (before any implementation)

These are the [test] items. Nobody can check them from outside your account. One short
Codex Cloud task settles them, and its output decides the final build. The tools are in
this repo:

- `bin/vs-doctor`: VM size, disk and the skill inventory.
- `bin/vs-kaggle-probe`: one private GPU kernel of about 2 minutes. It reports GPU,
  VRAM, bf16 support, fp16 TFLOPS, disk, RAM, model-download speed and the full round-trip
  time.

The task:

1. `bin/vs-doctor --json`: VM size and disk on your plan.
2. Generate one test image with `$imagegen`: is `image_gen` available in cloud tasks?
3. `bin/vs-kaggle-probe NvidiaTeslaT4`, then `NvidiaL4`: is Kaggle automation working,
   what are the real GPU specs, and what is the queue and boot overhead?
4. Commit a 30 MB test MP4 to a branch, and try an HTTP Preview: which delivery path
   works?
5. Run a 25-minute `sleep` loop with progress output: the practical turn length.

## 8. Decisions needed

1. **Your ChatGPT plan** (Plus or Pro / Business). It decides the VM disk (8 or 32 GiB) and
   how much `image_gen` and cloud-task usage you have.
2. Approve **Phase A′**. You create a Kaggle account (phone-verified) and an API token, and
   a Codex Cloud environment for this repo. I'll prepare the exact task prompt and settings
   text.
3. Optionally, a **Hugging Face** account token for the ZeroGPU fallback (5 GPU-minutes a
   day, free, cannot overspend).
4. After the A′ results: approve **B + C′** as designed above.
