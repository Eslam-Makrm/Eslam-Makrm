// story.js: your film. Replace this with your shots (see ANIMATION_GUIDE.md and ../examples/seed.js).
// shots([[t0, fn], ...]) — each fn(t, lt, dur) paints the WHOLE frame and is a pure function of time.
(() => {
  function opening(t, lt, dur) {
    paint(rectPts(-60, -60, W + 120, H + 120), { wash: PAL.paper, ink: null });
    paint(ellPts(960, 560, 300 + 20 * wob(t, .5), 300, 30, 6), { wash: PAL.sky, fill: PAL.teal, fillOp: 60, ink: PAL.ink });
  }
  shots([[0, opening]]);
})();
