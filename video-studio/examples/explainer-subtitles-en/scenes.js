export default {
  intro(s) {
    const { left, top, w, h } = s.safe;
    const u = Math.min(w, h) / 100;
    s.title('How automatic subtitles work', { y: top + h * 0.22, size: u * 9, at: -1 });
    s.icon('smartphone', { id: 'phone', x: left + w * 0.3, y: top + h * 0.62, size: u * 30, at: 'videos' });
    s.icon('volume-x', { x: left + w * 0.3, y: top + h * 0.62, size: u * 10, color: 'accent', at: 'off' });
    s.box('Subtitles', { id: 'subs', x: left + w * 0.72, y: top + h * 0.62, size: u * 7, icon: 'captions', at: '#need' });
    s.arrow('phone', 'subs', { label: 'keeps viewers', at: 'keep' });
  },

  listen(s) {
    const { left, top, w, h } = s.safe;
    const u = Math.min(w, h) / 100;
    const [x1, x2, x3] = s.row(3);
    s.box('Voice', { id: 'voice', x: x1, y: s.cy, size: u * 6, icon: 'mic', at: 0 });
    s.box('Whisper', { id: 'model', x: x2, y: s.cy, size: u * 6, icon: 'brain', at: '#whisper' });
    s.box('Words + times', { id: 'words', x: x3, y: s.cy, size: u * 6, icon: 'list', at: '#words' });
    s.arrow('voice', 'model', { at: 'listens' });
    s.arrow('model', 'words', { at: '#words' });
    s.note('"sound"  2.10 s → 2.45 s', { x: x2, y: s.cy + u * 18, at: 'moment', font: 'mono' });
  },

  timing(s) {
    const { left, top, w, h } = s.safe;
    const u = Math.min(w, h) / 100;
    s.text('Words become *lines*', { y: top + h * 0.15, size: u * 8, at: 0 });
    const ys = s.col(3, { height: h * 0.55, y: top + h * 0.6 });
    s.text('Most videos are watched', { y: ys[0], size: u * 6, bg: true, at: '#lines' });
    s.text('with the sound off.', { y: ys[1], size: u * 6, bg: true, at: 'starts' });
    s.text('⏸ pause → new line', { y: ys[2], size: u * 5, color: 'accent', at: '#pause' });
  },

  outro(s) {
    const { top, h } = s.safe;
    const u = Math.min(s.safe.w, h) / 100;
    s.icon('film', { y: top + h * 0.35, size: u * 22, at: 0 });
    s.text('Free · Local · Private', { y: top + h * 0.72, size: u * 8, at: 'computer', mark: 'accent' });
  },
};
