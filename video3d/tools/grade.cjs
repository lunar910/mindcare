// PS2-cinematic grade: contrast, slight desaturation, bloom, grain, vignette (+ optional reel subtitle).
// usage: node grade.cjs in.png out.png ["subtitle"]  [in2 out2 "sub2" ...]
const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright');

const font = fs.readFileSync(path.join(__dirname, 'node_modules/@fontsource/inter/files/inter-latin-800-normal.woff2')).toString('base64');

(async () => {
  const args = process.argv.slice(2);
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 720, height: 540 }, deviceScaleFactor: 2 });
  for (let i = 0; i < args.length; i += 3) {
    const [inp, out, text] = args.slice(i, i + 3);
    const img = 'data:image/png;base64,' + fs.readFileSync(inp).toString('base64');
    const esc = (text || '').replace(/&/g, '&amp;').replace(/</g, '&lt;');
    await page.setContent(`<!doctype html><html><head><meta charset="utf-8"><style>
      @font-face { font-family: 'InterX'; src: url(data:font/woff2;base64,${font}) format('woff2'); font-weight: 800; }
      html, body { margin: 0; background: #000; }
      #s { position: relative; width: 720px; height: 540px; overflow: hidden; }
      .l { position: absolute; inset: 0; background: url(${img}) center / cover no-repeat; }
      #base { filter: contrast(1.12) saturate(0.9) brightness(0.97); }
      #bloom { filter: blur(7px) brightness(1.35) saturate(1.1); mix-blend-mode: screen; opacity: 0.22; }
      #tint { background: linear-gradient(180deg, rgba(20,40,80,0.10), rgba(60,20,10,0.06)); mix-blend-mode: soft-light; }
      #vig { background: radial-gradient(ellipse at 50% 48%, rgba(0,0,0,0) 55%, rgba(0,0,0,0.45) 100%); }
      #grain { opacity: 0.07; mix-blend-mode: overlay; }
      #t { position: absolute; left: 7%; right: 7%; bottom: 46px; text-align: center; font: 800 24px/1.2 'InterX', sans-serif; color: #fff; letter-spacing: -0.2px;
        text-shadow: -2px -2px 0 #000, 2px -2px 0 #000, -2px 2px 0 #000, 2px 2px 0 #000, 0 -2px 0 #000, 0 2px 0 #000, -2px 0 0 #000, 2px 0 0 #000, 0 3px 6px rgba(0,0,0,.55); }
    </style></head><body><div id="s">
      <div class="l" id="base"></div><div class="l" id="bloom"></div><div class="l" id="tint"></div>
      <svg class="l" id="grain" width="720" height="540"><filter id="n"><feTurbulence type="fractalNoise" baseFrequency="1.4" numOctaves="2" seed="${i + 3}"/><feColorMatrix type="saturate" values="0"/></filter><rect width="100%" height="100%" filter="url(#n)"/></svg>
      <div class="l" id="vig"></div>
      ${esc ? `<div id="t">${esc}</div>` : ''}
    </div></body></html>`);
    await page.evaluate(async () => { await document.fonts.load("800 24px InterX"); await document.fonts.ready; });
    await page.screenshot({ path: out });
    console.log('wrote', out);
  }
  await browser.close();
})().catch((e) => { console.error(e); process.exit(1); });
