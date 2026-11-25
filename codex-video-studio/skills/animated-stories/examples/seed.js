// seed.js: "The little seed", an original 8-second story for the studio test (no mascot, no text).
//   Shot A (0–3.6 s): night-blue rain over a field. A small seed with a face sleeps in the soil; drops land, it wakes,
//                     wriggles and a first shoot pushes up. Brush wipe.
//   Shot B (3.6–8 s): morning. The sprout stretches tall toward the rising sun, two leaves open, the bud blooms,
//                     the seed-face beams. Iris out on the flower.
(() => {
  const DAWN = [PAL.ochre, PAL.clay];
  const GROUND = 820;

  function soil(t, col) {
    boilSeed('soil');
    paint(rectPts(-200, GROUND, W + 400, 420, 3), { wash: col, fill: mixCol(col, PAL.ink, .25), fillOp: 90, bleed: .04, tex: .5, ink: null });
    inkLine([[-200, GROUND + 2], [W / 2, GROUND - 6], [W + 200, GROUND + 4]], 1, PAL.ink, 'ink', .5);
    for (let i = 0; i < 9; i++) {   // little pebbles in the soil
      boilSeed('peb' + i);
      paint(ellPts(120 + i * 210 + hash(i) * 60, GROUND + 90 + hash(i + 9) * 220, 14 + 8 * hash(i + 3), 9, 10, 1), { wash: mixCol(col, PAL.paper, .35), ink: PAL.ink, sw: .5 });
    }
  }

  // The seed: an almond body with a face. awake 0..1, smile 0..1, wiggle in radians.
  function seed(x, y, r, o = {}) {
    const awake = clamp(o.awake ?? 0), smile = clamp(o.smile ?? 0);
    push(); translate(x, y); rotate(o.wiggle || 0);
    boilSeed('seedbody');
    paint(ellPts(0, 0, r * 1.25, r, 26, 1.2, -.2), { wash: '#B9814F', fill: PAL.clayDk, fillOp: 60, ink: PAL.ink, sw: 1.1 });
    const e = r * .32;
    for (const s of [-1, 1]) {   // eyes: closed arcs while asleep, dots once awake
      if (awake < .5) inkLine([[s * e - e * .45, -e * .1], [s * e, e * .25], [s * e + e * .45, -e * .1]], .8, PAL.ink, 'ink', .6);
      else paint(ellPts(s * e, 0, e * .22, e * .3 * (awake), 10), { wash: PAL.ink, ink: null });
    }
    const m = e * (.2 + .6 * smile);
    inkLine([[-e * .6, e * .9], [0, e * .9 + m], [e * .6, e * .9]], .8, PAL.ink, 'ink', .6);
    if (smile > .3) for (const s of [-1, 1]) paint(ellPts(s * e * 1.7, e * .75, e * .35, e * .2, 10), { fill: PAL.rose, fillOp: 160 * smile, ink: null });
    if (awake < .5 && o.z) {   // sleepy z's float up
      for (let i = 0; i < 2; i++) { const k = frac(T * .6 + i * .5); inkLine([[r + 10 + k * 30, -r - k * 60], [r + 24 + k * 30, -r - k * 60], [r + 10 + k * 30, -r - 14 - k * 60], [r + 24 + k * 30, -r - 14 - k * 60]], .6, PAL.cream, 'inkfine', 0); }
    }
    pop();
  }

  // The plant: a stem from the seed up to `len` px, leaves opening 0..1, a bloom 0..1 at the tip.
  function plant(x, y, len, leaves, bloom, sway, t) {
    if (len < 4) return;
    const tip = [x + sway * len * .25, y - len];
    const P = [[x, y], [x + sway * len * .1 + 6 * wob(t, .5), y - len * .45], tip];
    boilSeed('stem');
    paint(ribbon(through(P, 8), 16, 8), { wash: PAL.sap, ink: PAL.ink, sw: .7 });
    for (const s of [-1, 1]) if (leaves > 0) {
      const k = backOut(clamp(leaves * 1.1 - (s > 0 ? .1 : 0))), base = [x + sway * len * .06, y - len * .42], L = 120 * k;
      const lp = [base, [base[0] + s * L * .55, base[1] - L * .55 - 10], [base[0] + s * L, base[1] - L * .25]];
      boilSeed('leaf' + s);
      paint(through([...lp, [base[0] + s * L * .45, base[1] + 8]], 6), { wash: mixCol(PAL.sap, PAL.cream, .15), fill: PAL.sap, fillOp: 80, ink: PAL.ink, sw: .7 });
    }
    if (bloom > 0) {
      const b = backOut(clamp(bloom));
      glow(tip[0], tip[1], 140 * b, '#FFD96A', .5 * b);
      for (let i = 0; i < 6; i++) {   // petals
        const a = i * TAU / 6 + t * .3;
        boilSeed('petal' + i);
        paint(ellPts(tip[0] + Math.cos(a) * 36 * b, tip[1] + Math.sin(a) * 36 * b, 30 * b, 17 * b, 14, 1, a), { wash: PAL.rose, fill: PAL.cream, fillOp: 70, ink: PAL.ink, sw: .6 });
      }
      boilSeed('core');
      paint(ellPts(tip[0], tip[1], 20 * b, 20 * b, 16, 1), { wash: PAL.ochre, ink: PAL.ink, sw: .7 });
    }
    return tip;
  }

  function rain(t, amt, x0 = 0) {
    for (let i = 0; i < 46; i++) {
      boilSeed('drop' + i);
      const x = x0 + hash(i) * (W + 300) - 150, sp = 900 + 300 * hash(i + 50), y = ((t * sp + hash(i + 7) * 2000) % 1150) - 150;
      if (y < GROUND - 10) inkLine([[x, y], [x - 8, y + 34]], .7 * amt, mixCol(PAL.sky, PAL.cream, .4), 'inkfine', 0);
    }
  }

  // ---------- shot A: rain wakes the seed ----------
  function shotRain(t, lt, dur) {
    camBegin(960, kf(lt, [[0, 640], [dur, 840]]), kf(lt, [[0, 1.15], [dur, 1.9]]));
    boilSeed('sky');
    paint(rectPts(-400, -400, W + 800, GROUND + 420), { wash: PAL.night, ink: null });
    paint(ellPts(W * .65, 200, W * .5, 170, 24, 10), { fill: PAL.indigo, fillOp: 110, bleed: .2, tex: .5, ink: null });
    rain(t, 1);
    soil(t, '#6B4A3A');
    const wake = seg(lt, 1.3, 1.6), wig = lt > 1.6 && lt < 2.6 ? .18 * Math.sin((lt - 1.6) * 22) * Math.exp(-(lt - 1.6) * 2) : 0;
    seed(960, GROUND + 120, 62, { awake: wake, smile: seg(lt, 2.4, 2.9), wiggle: wig, z: lt < 1.3 });
    for (const [tt, dx] of [[.7, -40], [1.15, 30], [1.4, -10]]) {   // three drops soak down to the seed
      const k = seg(lt, tt, tt + .35);
      if (k > 0 && k < 1) paint(ellPts(960 + dx, lerp(GROUND, GROUND + 70, k), 8, 11, 10), { wash: PAL.sky, washOp: 230 * (1 - k), ink: null });
    }
    plant(960, GROUND + 80, 140 * easeOut(seg(lt, 2.7, dur)), 0, 0, 0, t);
    camEnd();
    if (lt < .4) iris(960, 700, lerp(0, 1500, easeIn(lt / .4)));
    boilSeed('transition');
    if (lt > dur - .3) brushWipe((lt - (dur - .3)) / .6, DAWN);
  }

  // ---------- shot B: morning bloom ----------
  function shotBloom(t, lt, dur) {
    camBegin(960, kf(lt, [[0, 640], [2.4, 520]]), kf(lt, [[0, 1.08], [2.4, 1], [dur, 1.03]]));
    boilSeed('sky');
    paint(rectPts(-400, -400, W + 800, GROUND + 420), { wash: mixCol(PAL.sky, PAL.cream, seg(lt, 0, 2) * .5), ink: null });
    const sunY = lerp(820, 260, easeOut(seg(lt, 0, 2.2)));
    glow(1460, sunY, 260, '#FFD96A', .8);
    boilSeed('sun');
    paint(ellPts(1460, sunY, 90, 90, 28, 1.5), { wash: PAL.ochre, fill: PAL.cream, fillOp: 60, ink: PAL.ink, sw: .9 });
    soil(t, '#7A5A44');
    seed(960, GROUND + 120, 62, { awake: 1, smile: .4 + .6 * seg(lt, 2.6, 3.0), wiggle: .05 * Math.sin(lt * 3) });
    const len = lerp(140, 470, easeOut(seg(lt, .3, 1.9))), sway = .25 * ease(seg(lt, .8, 2.2)) + .03 * wob(t, .4);
    const tip = plant(960, GROUND + 80, len, seg(lt, 1.4, 2.1), seg(lt, 2.2, 2.8), sway, t);
    const eye = toScreen(...tip);
    camEnd();
    boilSeed('transition');
    if (lt < .3) brushWipe(.5 + lt / .6, DAWN);
    if (lt > 3.6) iris(...eye, lt < dur - .25 ? lerp(1500, 220, ease(seg(lt, 3.6, 4.0))) : lerp(220, 0, easeIn(seg(lt, dur - .25, dur - .03))));
  }

  shots([[0, shotRain], [3.6, shotBloom]]);
})();
