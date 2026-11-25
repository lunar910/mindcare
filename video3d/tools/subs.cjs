// Burn reel-style subtitles onto rendered frames.
// usage: node subs.cjs in.png out.png "subtitle text" [in2.png out2.png "text2" ...]
const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright');

const font = fs.readFileSync(path.join(__dirname, 'node_modules/@fontsource/inter/files/inter-latin-800-normal.woff2')).toString('base64');

(async () => {
  const args = process.argv.slice(2);
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 720, height: 540 }, deviceScaleFactor: 2 });
  for (let i = 0; i + 2 < args.length + 1; i += 3) {
    const [inp, out, text] = args.slice(i, i + 3);
    const img = fs.readFileSync(inp).toString('base64');
    const esc = (text || '').replace(/&/g, '&amp;').replace(/</g, '&lt;');
    await page.setContent(`<!doctype html><html><head><meta charset="utf-8"><style>
      @font-face { font-family: 'InterX'; src: url(data:font/woff2;base64,${font}) format('woff2'); font-weight: 800; }
      html, body { margin: 0; background: #000; }
      #s { position: relative; width: 720px; height: 540px; background: url(data:image/png;base64,${img}) center / cover no-repeat; }
      #t { position: absolute; left: 7%; right: 7%; bottom: 46px; text-align: center; font: 800 24px/1.2 'InterX', sans-serif; color: #fff; letter-spacing: -0.2px;
        text-shadow: -2px -2px 0 #000, 2px -2px 0 #000, -2px 2px 0 #000, 2px 2px 0 #000, 0 -2px 0 #000, 0 2px 0 #000, -2px 0 0 #000, 2px 0 0 #000, 0 3px 6px rgba(0,0,0,.55); }
    </style></head><body><div id="s"><div id="t">${esc}</div></div></body></html>`);
    await page.evaluate(async () => { await document.fonts.load("800 24px InterX"); await document.fonts.ready; });
    await page.screenshot({ path: out });
    console.log('wrote', out);
  }
  await browser.close();
})().catch((e) => { console.error(e); process.exit(1); });
