// Rasterize every assets/icons/*.svg to a 1024x1024 transparent PNG with headless Chromium.
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');
(async () => {
  const dir = process.argv[2];
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1024, height: 1024 } });
  for (const f of fs.readdirSync(dir).filter(f => f.endsWith('.svg'))) {
    const svg = fs.readFileSync(path.join(dir, f), 'utf8').replace('width="512" height="512"', 'width="1024" height="1024"');
    await page.setContent(`<html><body style="margin:0;background:transparent"><div id="c" style="width:1024px;height:1024px">${svg}</div></body></html>`);
    await page.locator('#c').screenshot({ path: path.join(dir, f.replace('.svg', '.png')), omitBackground: true });
    console.log('icon', f);
  }
  await browser.close();
})();
