#!/usr/bin/env bash
# Render one real MP4 per studio skill from the examples in ../examples and verify each.
#   tests/run-all.sh [OUT_DIR] [--skip-story]     (the painted story takes 10-40 min on CPU)
# Exit code is non-zero if any render or check fails. A summary table is printed at the end.
set -uo pipefail
HERE="$(cd "$(dirname "$0")/.." && pwd)"
OUT="$(cd "${1:-$HERE/samples-out}" 2>/dev/null && pwd || (mkdir -p "${1:-$HERE/samples-out}" && cd "${1:-$HERE/samples-out}" && pwd))"
SKIP_STORY=0; for a in "$@"; do [ "$a" = --skip-story ] && SKIP_STORY=1; done
source "${VS_HOME:-$HOME/.video-studio}/env.sh"
SK="$VS_SKILLS"; AV="$SK/arabic-voiceover/scripts"; SUB="$SK/auto-subtitles/scripts/subtitle.py"; ED="$SK/video-editing/scripts/edit.py"
WORK="$(mktemp -d)"; RESULTS=(); FAIL=0
step() { local name="$1" file="$2"; shift 2
  echo; echo "=== $name"
  if "$@" && [ -s "$file" ] && vs-verify "$file" "${file%.mp4}.sheet.jpg"; then RESULTS+=("PASS  $name  $file")
  else RESULTS+=("FAIL  $name"); FAIL=1; fi; }
fit_audio() {  # set each <audio id="voN"> data-duration to its file length
  python3 - "$1" <<'PY'
import re,subprocess,sys,os
p=os.path.join(sys.argv[1],'index.html'); s=open(p,encoding='utf-8').read()
def d(f): return float(subprocess.run(['ffprobe','-v','error','-show_entries','format=duration','-of','csv=p=0',os.path.join(sys.argv[1],f)],capture_output=True,text=True).stdout)
s=re.sub(r'(<audio id="(vo\d)"[^>]*src="([^"]+)"[^>]*data-duration=")[0-9.]+', lambda m: m.group(1)+f"{d(m.group(3))-0.05:.2f}", s)
open(p,'w',encoding='utf-8').write(s)
PY
}
hf_project() {  # example dir → work dir with local gsap + fonts
  cp -R "$HERE/examples/$1" "$WORK/$1"; mkdir -p "$WORK/$1/assets/fonts"
  cp "$VS_HOME/vendor/gsap.min.js" "$WORK/$1/assets/"; cp "$VS_HOME/vendor/Cairo.ttf" "$WORK/$1/assets/fonts/"; }

# 1 motion graphics (HyperFrames)
hf_project promo-16x9
step "motion-graphics (hyperframes)" "$OUT/01-motion-graphics-promo.mp4" \
  bash -c "cd '$WORK/promo-16x9' && \$HF_CLI render -o '$OUT/01-motion-graphics-promo.mp4' >/dev/null"

# 2 Arabic voiceover (Piper) + 3 Arabic RTL social reel (HyperFrames 9:16)
hf_project arabic-reel-9x16; R="$WORK/arabic-reel-9x16"
python3 "$AV/piper_tts_lines.py" "$R/voice-lines.json" "$R/voiceover/raw" >/dev/null && bash "$AV/prep_voice.sh" "$R/voiceover/raw" "$R/voiceover" 1.0 >/dev/null \
  && python3 "$AV/tighten_pauses.py" "$R/voiceover/assets/voice" >/dev/null && cp "$R"/voiceover/assets/voice/vo*.mp3 "$R/assets/" && fit_audio "$R"
step "arabic-motion-graphics + social 9:16 + arabic-voiceover" "$OUT/02-arabic-social-reel.mp4" \
  bash -c "cd '$R' && \$HF_CLI render -o '$OUT/02-arabic-social-reel.mp4' >/dev/null"

# 4 automatic subtitles (Whisper → burned Arabic captions)
step "auto-subtitles (ar, reel style)" "$OUT/03-arabic-reel-subtitled.mp4" \
  "$VS_PY" "$SUB" "$OUT/02-arabic-social-reel.mp4" --lang ar --style reel --out-dir "$WORK/subs" --burn "$OUT/03-arabic-reel-subtitled.mp4"

# 5 educational (Manim + Arabic narration mixed with mix_voiceover.py)
L="$WORK/lesson"; cp -R "$HERE/examples/lesson-pythagoras-ar" "$L"
python3 "$AV/piper_tts_lines.py" "$L/voice-lines.json" "$L/raw" --length-scale 1.05 >/dev/null && bash "$AV/prep_voice.sh" "$L/raw" "$L/vo" 1.0 >/dev/null \
  && python3 "$AV/tighten_pauses.py" "$L/vo/assets/voice" >/dev/null
step "educational (manim + arabic narration)" "$OUT/04-educational-lesson-ar.mp4" \
  bash -c "cd '$L' && \$VS_MANIM -qh --fps 30 --disable_caching pythagoras.py Pythagoras >/dev/null 2>&1 && python3 '$AV/mix_voiceover.py' --video media/videos/pythagoras/1080p30/Pythagoras.mp4 --voice-dir vo/assets/voice --starts 0.5,7.8,11.4,18.3 --original mute --out '$OUT/04-educational-lesson-ar.mp4' >/dev/null"

# 6 educational explainer (explainroo, English, Kokoro voice)
X="$WORK/explainer"; mkdir -p "$X/videos"
step "educational explainer (explainroo)" "$OUT/05-explainer-en.mp4" bash -c "cd '$X' && npx --yes explainroo@0.6.2 init videos/ex --size 16:9 >/dev/null 2>&1 \
  && cp '$HERE'/examples/explainer-subtitles-en/* videos/ex/ && npx --yes explainroo@0.6.2 voice videos/ex >/dev/null 2>&1 \
  && npx --yes explainroo@0.6.2 render videos/ex >/dev/null 2>&1 && npx --yes explainroo@0.6.2 verify videos/ex 2>/dev/null | tail -1 && cp videos/ex/out/video.mp4 '$OUT/05-explainer-en.mp4'"

# 7 video editing (silence cut, trim, join with crossfades, reframe 9:16, loudness)
step "video-editing" "$OUT/06-edited-9x16.mp4" bash -c "
  '$VS_PY' '$ED' silence '$OUT/04-educational-lesson-ar.mp4' '$WORK/e/tight.mp4' >/dev/null &&
  '$VS_PY' '$ED' trim '$OUT/01-motion-graphics-promo.mp4' '$WORK/e/promo.mp4' --start 0 --end 9 >/dev/null &&
  '$VS_PY' '$ED' join '$WORK/e/joined.mp4' '$WORK/e/promo.mp4' '$WORK/e/tight.mp4' --xfade 0.6 >/dev/null &&
  '$VS_PY' '$ED' reframe '$WORK/e/joined.mp4' '$WORK/e/vertical.mp4' --to 9:16 >/dev/null &&
  '$VS_PY' '$ED' loudness '$WORK/e/vertical.mp4' '$OUT/06-edited-9x16.mp4' >/dev/null"

# 8 animated story (p5.brush kit, original character)
if [ "$SKIP_STORY" = 0 ]; then
  S="$WORK/story"; cp -R "$SK/animated-stories/kit" "$S"; cp "$HERE/examples/story-little-seed/seed.js" "$S/src/scenes/story.js"
  cp "$HERE/examples/story-little-seed/config.js" "$S/src/config.js"
  step "animated-stories (p5.brush)" "$OUT/07-animated-story.mp4" bash -c "cd '$S' && npm ci --ignore-scripts --silent >/dev/null 2>&1 \
    && node render.mjs --frames --workers=4 --soft-gl >/dev/null && node render.mjs --encode --out='$OUT/07-animated-story.mp4' >/dev/null"
fi

# 9 camera moves + parallax (CPU)
step "cinematic-camera (parallax dolly-in)" "$OUT/09-parallax.mp4" bash -c "ffmpeg -v error -y -ss 5 -i '$HERE/samples/07-animated-story.mp4' -frames:v 1 '$WORK/still.png' && vs-camera parallax '$WORK/still.png' '$OUT/09-parallax.mp4' --move dolly-in --dur 4 --size 1280x720 >/dev/null"
# 10 2D lip sync cues (Rhubarb) — checked, not rendered
echo; echo "=== lip-sync 2D (rhubarb)"
if echo "مَرْحَبًا بِكُمْ" | "$VS_PY" -m piper -m "$PIPER_VOICES/ar_JO-kareem-medium.onnx" -f "$WORK/l.wav" >/dev/null 2>&1 && vs-lipsync2d "$WORK/l.wav" "$WORK/m.json"; then
  RESULTS+=("PASS  lip-sync 2D (rhubarb)"); else RESULTS+=("FAIL  lip-sync 2D (rhubarb)"); FAIL=1; fi
# 11 one-prompt production (video-producer path, CPU route) + QC gate
cp -R "$HERE/examples/qari-ad-e2e" "$WORK/qari"; rm -rf "$WORK/qari/build" "$WORK/qari/out"
step "video-producer one-prompt ad (vs-produce + vs-qc)" "$OUT/11-qari-ad.mp4" bash -c "vs-produce '$WORK/qari' --gpu off >/dev/null 2>&1 && cp '$WORK/qari/out/qari-ad.mp4' '$OUT/11-qari-ad.mp4'"
# 12 GPU job runtime (packing, 2-GPU fan-out) and vs-produce --async, both on CPU with stubs
for t in test_gpu_runtime test_gpu_resubmit test_video_job_mock test_produce_async test_colab test_produce_colab; do
  echo; echo "=== $t"
  if bash "$HERE/tests/$t.sh" | tail -1 | grep -q '^PASS'; then RESULTS+=("PASS  $t"); else RESULTS+=("FAIL  $t"); FAIL=1; fi
done
# Wan2.2-TI2V image-to-video wiring on CPU (tiny models); SKIP unless VS_TORCH_PY has torch + diffusers 0.43
echo; echo "=== test_i2v_tiny"
r="$(bash "$HERE/tests/test_i2v_tiny.sh" 2>&1 | tail -1)"; echo "$r"
case "$r" in PASS*) RESULTS+=("PASS  test_i2v_tiny");; SKIP*) RESULTS+=("SKIP  test_i2v_tiny (no VS_TORCH_PY)");; *) RESULTS+=("FAIL  test_i2v_tiny"); FAIL=1;; esac
# 13 cloud GPU backend reachable (no GPU time used)
echo; echo "=== cloud GPU backend (Kaggle API)"
if vs-gpu quota; then RESULTS+=("PASS  Kaggle API (quota)"); else RESULTS+=("FAIL  Kaggle API (quota)"); FAIL=1; fi

echo; echo "================ summary"; printf '%s\n' "${RESULTS[@]}"; rm -rf "$WORK"; exit $FAIL
