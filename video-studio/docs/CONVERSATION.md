# سجل المحادثة: بناء استوديو فيديو مجاني داخل Codex

**التاريخ:** 25 نوفمبر 2026
**الفرع:** `claude/codex-video-production-setup-w8gi7m` في `Eslam-Makrm/Eslam-Makrm`
**النتيجة:** 15 مهارة (skill) لـ Codex، ومُثبِّت، واختبارات، و7 فيديوهات MP4 حقيقية تم التحقق منها.

> هذا ملخص مرتّب للمحادثة: رسائل المستخدم كما هي، وردود Claude وخطواته باختصار.
> الأوامر التفصيلية ومخرجاتها الكاملة موجودة في ملفات المشروع نفسها.

---

## 1. الطلب الأول (المستخدم)

> Review the following GitHub repository:
> https://github.com/zhuyansen/awesome-claude-video-skills
>
> I want to build a professional video production environment within OpenAI Codex.
> Use the built-in $skill-installer where applicable.
>
> 1. Analyze the listed video skills and repositories.
> 2. Identify the best open-source tools compatible with Codex.
> 3. Prioritize free tools that support local video generation.
> 4. Select the best tools for: Educational videos · Animated stories · Motion graphics ·
>    Arabic voiceovers · Social media videos · Video editing · Automatic subtitles
> 5. Review all installation scripts, dependencies, licenses, and security risks before execution.
> 6. Present the recommended installation plan for my approval.
> 7. After approval, install the selected skills in the appropriate Codex skills directory.
> 8. Adapt Claude-specific instructions to Codex where necessary.
> 9. Install the required dependencies.
> 10. Test each installed skill by generating a real MP4 video.
>
> Do not install duplicate tools or paid services without my approval.
> The final objective is to create a complete, reusable AI video production system operated directly through Codex.

## 2. التحليل وخطة التثبيت (Claude)

- القائمة فيها **548 مستودع** (530 مصنّف "safe" و18 "caution"). تم استنساخ وقراءة **17 مستودع** مرشّح:
  README وملفات SKILL.md وكل سكربتات التثبيت والاعتماديات، مع فحص لأنماط خطرة
  (`curl | sh`، hooks التثبيت، `eval`، كود مُموّه، التعامل مع المفاتيح، التتبّع telemetry).
- **ملاحظات أساسية:**
  - أغلب المستودعات خاصة بـ Claude أو تحتاج خدمات مدفوعة، وكثير منها مبني على Remotion
    (ترخيصه مجاني فقط للأفراد والشركات حتى 3 أشخاص).
  - العربية تكاد تكون غير مدعومة (3 مستودعات صغيرة فقط)، وأصوات Kokoro لا تتكلم عربي.
  - `huggingface.co` كان محجوبًا في بيئة الجلسة، فالنماذج لا تنزل.

**الخطة المقترحة (أداة واحدة لكل وظيفة، بدون تكرار):**

| الاحتياج | الأداة | الترخيص |
|---|---|---|
| المحرّك الأساسي، موشن جرافيك، سوشيال ميديا | HyperFrames | Apache-2.0 |
| فيديوهات تعليمية | Manim + manim_skill | MIT |
| موشن جرافيك عربي (RTL) | sudadom/arabic-motion-graphics-skill (منقول إلى HyperFrames) | MIT |
| تعليق صوتي عربي | Piper (أوفلاين) + قواعد التشكيل من TurkiHassan/arabic-launch-video | GPL-3.0 / MIT |
| قصص متحركة | JohnHeibel/ClaudeAnimationBase (p5.js + p5.brush) | MIT |
| ترجمة تلقائية | faster-whisper ← SRT/ASS ← ffmpeg | MIT |
| مونتاج | ffmpeg + auto-editor | LGPL/GPL، Unlicense |
| التنسيق بينها | مهارة `video-studio` | — |

**المرفوض:** OpenMontage (AGPL و"caution")، HibAI Studio (ترخيص مغلق)، subtle (Apple Silicon فقط)،
stickman-video-director (يحتاج نموذج صور مدفوع)، مهارات Remotion (تكرار + ترخيص مشروط).

## 3. الموافقة (المستخدم)

> Add all free

تمت إضافة كل الخيارات المجانية: **explainroo** و**LaTeX** و**edge-tts**
(مجاني بلا مفتاح، لكنه يرسل النص لخدمة Microsoft أونلاين). Remotion لم يُضَف لأنه تكرار وترخيصه مشروط.

## 4. التنفيذ (Claude)

### البيئة والشبكة
- إنشاء بيئة سحابية شخصية باسم **"Eslam-Makrm video studio"** تسمح بـ Hugging Face و CDN الخاص به
  و`speech.platform.bing.com` (edge-tts) و`codeload.github.com`.

### التثبيت
- تثبيت **Codex CLI** للحصول على `$skill-installer` الرسمي، واستخدامه لتثبيت 9 مهارات مثبّتة على إصدارات محددة:
  - HyperFrames v0.9.93 (6 مهارات): `hyperframes`, `hyperframes-cli`, `hyperframes-registry`, `media-use`, `reverse-any-video`, `style-sampling`
  - manim_skill: `manim-composer`, `manimce-best-practices`
  - explainroo
- كتابة 6 مهارات للاستوديو: `video-studio`, `arabic-voiceover`, `arabic-motion-graphics`,
  `animated-stories`, `auto-subtitles`, `video-editing`.
- **تكييف تعليمات Claude لـ Codex:** إزالة المسارات المدفوعة (Gemini، ElevenLabs، رصيد HeyGen)،
  إيقاف التتبّع، استبدال `CLAUDE.md` بـ `AGENTS.md`، ونقل القوالب العربية من Remotion إلى HyperFrames.
- الاعتماديات: Manim و LaTeX و espeak-ng وخطوط عربية (Cairo، Amiri، Noto)، وثلاث بيئات Python منفصلة
  (بسبب تعارض إصدارات PyAV)، ونماذج Whisper (small و large-v3-turbo)، وصوت Piper العربي `ar_JO-kareem`.

### مشاكل ظهرت أثناء الاختبار وتم حلّها
- **مربعات فارغة بدل الحروف:** مكتبة libass (ترجمة ffmpeg) ترسم «لا» و«أ/إ/آ» كمربعات مع خطوط
  Noto Sans Arabic و Cairo و Kacst. الحل: الافتراضي صار **Noto Naskh Arabic** أو **Amiri** (تم اختبارهما).
- **ترتيب الكلمات المعكوس:** تلوين كلمة في منتصف سطر عربي يعكس الترتيب. الحل: الترجمة العربية تظهر كمقاطع قصيرة كاملة.
- **توقيت الترجمة:** Whisper يمطّ توقيت الكلمات على فترات الصمت. الحل: كسر الأسطر عند الوقفات الحقيقية (`silencedetect`).
- **تداخل الكلمات في العنوان العربي:** الكلمة الداخلة من اليمين كانت تغطي التي قبلها («هلتريد»). الحل: الكلمات تظهر في مكانها.
- **هندسة درس فيثاغورس:** مربع الوتر كان يُرسم للداخل، ثم صُحّح.
- Node لا يستخدم البروكسي تلقائيًا، و Hugging Face يحتاج تعطيل Xet: تمت إضافتهما إلى `env.sh`.

## 5. نتائج الاختبار: 7 فيديوهات حقيقية

| الفيديو | المهارة | المدة | النتيجة |
|---|---|---|---|
| إعلان موشن جرافيك 16:9 | hyperframes | 12 ث | ✅ |
| ريلز عربي 9:16 بصوت Piper | arabic-motion-graphics + arabic-voiceover | 20.5 ث | ✅ ‎−14.4 LUFS |
| نفس الريلز بترجمة عربية تلقائية | auto-subtitles | 20.5 ث | ✅ |
| درس نظرية فيثاغورس بالعربي | Manim + arabic-voiceover | 22.5 ث | ✅ ‎−14.0 LUFS |
| شرح إنجليزي مع تعليق صوتي | explainroo | 29.8 ث | ✅ فهم الكلام 100% |
| مونتاج: حذف صمت + دمج + تحويل لـ 9:16 | video-editing | 58 ث | ✅ ‎−13.9 LUFS |
| قصة متحركة مرسومة بشخصية أصلية | animated-stories | 8 ث | ✅ |

- إعادة تشغيل كل الاختبارات من الصفر (ما عدا القصة) نجحت كلها في **5.5 دقيقة**.
- Codex نفسه يعرض المهارات الـ 15 في الـ prompt، وكلها تجتاز مدقّق المهارات الخاص بـ Codex.
- القصة المرسومة بطيئة على المعالج بدون كارت شاشة: **19 دقيقة لـ 8 ثوانٍ**.

## 6. الرفع إلى GitHub

- محاولات الرفع الأولى فشلت بخطأ **403** لأن تطبيق Claude على GitHub لم يكن مثبتًا على المستودع.
- المستخدم ربط حساب GitHub (لقطة شاشة: "GitHub account connected")، ثم ثبّت التطبيق.
- المستخدم: **«Try again»** ← تم الرفع بنجاح:

```
302b0af Add animated story sample (p5.brush kit, original character)
9ebf35f Add Codex Video Studio: free local video skills, installer, tests and samples
```

## 7. طريقة الاستخدام على جهازك

```bash
git clone https://github.com/Eslam-Makrm/Eslam-Makrm
cd Eslam-Makrm && git checkout claude/codex-video-production-setup-w8gi7m
codex                                  # مرة واحدة لفك $skill-installer
cd codex-video-studio
./install.sh --system                  # أول مرة: ffmpeg و LaTeX والخطوط
tests/run-all.sh                       # اختياري: إعادة إنتاج كل الفيديوهات
```

ثم داخل Codex:

```
$video-studio  اعمل ريلز عربي ٢٠ ثانية عن تطبيقي مع تعليق صوتي وترجمة
```

## 8. ملاحظات مهمة

- **صوت Piper العربي** (`ar_JO-kareem`): بيانات تدريبه بلا ترخيص معلن، مناسب للاستخدام الشخصي والتعليمي، وراجع قبل أي استخدام تجاري.
  الصوت الإنجليزي `lessac` تحت ترخيص Blizzard-2013 (شروط غير تجارية).
- **edge-tts** مجاني لكنه أونلاين: النص يُرسل لخدمة Microsoft.
- لا توجد أي خدمة مدفوعة مثبتة أو مُعدّة.
- التفاصيل الكاملة للاختيار والمراجعة الأمنية والتراخيص: [`docs/REVIEW.md`](REVIEW.md).

## 9. آخر طلب (المستخدم)

> اعمل المحادثة دي md

← هذا الملف.
