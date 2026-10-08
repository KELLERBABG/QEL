// Run the page's real script against a DOM shim built from the real HTML, exercise the
// scroll handler, and report what the marker and readout do.
//
// Written three times. The first referenced a variable the page does not have; the
// second fabricated its step data with a `\u2014` escape instead of the real em-dash,
// injecting a spurious plot point; the third was patched into incoherence by repeated
// string surgery. The lesson is in the assertions at the bottom: this harness exists to
// check MOTION, which no static check (balanced braces, no undefined identifiers) can see.
const fs = require('fs');
const html = fs.readFileSync(process.argv[2] || 'index.html', 'utf8');
const script = html.slice(html.lastIndexOf('<script'))
  .replace(/^<script>/, '').replace(/<\/script>[\s\S]*$/, '');

const withAttrs = (o) => ({
  getAttribute: (k) => (k in o ? o[k] : null),
  setAttribute: (k, v) => { o[k] = v; },
});
function el(extra = {}) {
  const base = {
    classList: {
      _s: new Set(),
      toggle(c, on) { if (on) this._s.add(c); else this._s.delete(c); },
      add(c) { this._s.add(c); },
      remove(c) { this._s.delete(c); },
      contains(c) { return this._s.has(c); },
    },
    textContent: '',
    ...extra,
  };
  return Object.assign(base, withAttrs(base));
}

// Real steps from the real HTML.
const tags = html.match(/<section class="step"[^>]*>/g) || [];
const STEP_HEIGHT = 2000;
const steps = tags.map((tag, i) => {
  const o = {};
  for (const m of tag.matchAll(/data-([a-z]+)="([^"]*)"/g)) o['data-' + m[1]] = m[2];
  const e = el(o);
  e.getBoundingClientRect = () => ({ top: i * STEP_HEIGHT, height: STEP_HEIGHT });
  return e;
});

const byId = {};
const document = {
  querySelectorAll: (sel) => (sel === '.step' ? steps : []),
  querySelector: () => el(),
  getElementById: (id) => (byId[id] = byId[id] || el({ id })),
};

const listeners = {};
const window = {
  innerHeight: 800,
  scrollY: 0,
  matchMedia: () => ({ matches: false }),
  addEventListener: (t, fn) => { (listeners[t] = listeners[t] || []).push(fn); },
};

// `frame`, `STAGES` and `PLOT` live inside the page's IIFE, so the hook has to be
// injected *inside* it -- appending to the end of the script lands outside the closure.
// The injection is a local copy; the page itself is not modified.
const HOOK = 'if (typeof __expose !== "undefined") { __expose.frame = frame; '
           + '__expose.STAGES = STAGES; __expose.PLOT = PLOT; __expose.steps = steps; '
           + '__expose.dbg = function () { return { scrollY: window.scrollY, vh: window.innerHeight, '
           + 'n: steps.length, firstTop: steps.length ? steps[0].getBoundingClientRect().top : null }; }; }';
const lastBrace = script.lastIndexOf('})();');
if (lastBrace < 0) { console.log('could not find the IIFE close'); process.exit(1); }
const body = script.slice(0, lastBrace) + HOOK + '\n' + script.slice(lastBrace);

const expose = {};
window.__qelTrace = [];
try {
  new Function('document', 'window', 'requestAnimationFrame', '__expose', body)(
    document, window, () => {}, expose);
  console.log('script executed without throwing');
} catch (err) {
  console.log('SCRIPT THREW:', err.message);
  process.exit(1);
}

console.log('steps:', steps.length, '| act one:',
            steps.filter((s) => s['data-act'] === 'one').length);
console.log('page internals: STAGES =', expose.STAGES.length,
            ' PLOT =', expose.PLOT.length);
console.log('scroll listeners registered:', (listeners.scroll || []).length);
console.log('dbg():', JSON.stringify(expose.dbg()));
console.log('same elements?', expose.steps.every((s,i)=>s===steps[i]));
console.log('dbg per element rect[1].top =', expose.steps[1].getBoundingClientRect().top);
const pFrame=(function(){var n=0; return function(){n++; return n;};})();
console.log('');
console.log('scrollY   cx      readout  note');

const seenCx = new Set();
const readings = [];
for (const y of [0, 700, 1000, 1400, 1600, 1700, 2000, 2400, 3000, 3600, 4000,
                 5000, 6000, 8000, 10000, 12000, 14000, 16000, 18000]) {
  window.scrollY = y; window.__qelTrace.length = 0;
  (listeners.scroll || []).forEach((fn) => fn());
  seenCx.add(byId.mark.cx);
  const tr = window.__qelTrace[window.__qelTrace.length-1];
  if (y===2400||y===18000) console.log('   TRACE@'+y+':', JSON.stringify(tr));
  readings.push(byId.fid.textContent);
  console.log(`${String(y).padStart(6)}  ${String(byId.mark.cx).padStart(6)}  ${byId.fid.textContent}  ${byId.fidNote.textContent}`);
}

console.log('');
const distinctCx = [...seenCx].map(Number).filter((n) => !Number.isNaN(n));
const distinctReadouts = [...new Set(readings)];
console.log('distinct cx:', distinctCx.length, ' range', Math.min(...distinctCx), '->', Math.max(...distinctCx));
console.log('distinct readouts:', distinctReadouts.length, '->', distinctReadouts.join(', '));
console.log('');
console.log('ASSERTIONS');
console.log('  marker travels   :', distinctCx.length > 1 ? 'PASS' : 'FAIL');
console.log('  readout animates :', distinctReadouts.length > 1 ? 'PASS' : 'FAIL');
console.log('  curve spans 40-540:', (Math.min(...distinctCx) === 40 && Math.max(...distinctCx) === 540) ? 'PASS' : 'FAIL');
