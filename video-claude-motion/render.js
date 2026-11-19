// Render scene HTML -> MP4 (frame demi frame, tiada rakaman skrin).
// Guna: node render.js <scene.html> [output.mp4]
const { chromium } = require('playwright');
const { spawn } = require('node:child_process');
const path = require('node:path');
const { pathToFileURL } = require('node:url');

(async () => {

const scene = process.argv[2];
if (!scene) { console.error('Guna: node render.js <scene.html> [output.mp4]'); process.exit(1); }
const out = process.argv[3] || path.join(path.dirname(scene), 'output.mp4');

const browser = await chromium.launch();
const size = { width: 1920, height: 1080 };
let page = await browser.newPage({ viewport: size });
await page.goto(pathToFileURL(path.resolve(scene)).href + '?render=1');
// Saiz kanvas ikut scene (window.WIDTH/HEIGHT), cth 1080x1920 untuk Reels/TikTok
const dim = await page.evaluate(() => ({ w: window.WIDTH || 1920, h: window.HEIGHT || 1080 }));
if (dim.w !== 1920 || dim.h !== 1080) { await page.setViewportSize({ width: dim.w, height: dim.h }); }
await page.evaluate(() => document.fonts.ready);
const { DURATION, FPS } = await page.evaluate(() => ({ DURATION: window.DURATION, FPS: window.FPS }));
const total = Math.round(DURATION * FPS);

const ff = spawn('ffmpeg', ['-y', '-f', 'image2pipe', '-framerate', String(FPS), '-i', '-',
  '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', '23', '-maxrate', '10M', '-bufsize', '20M', '-preset', 'medium', '-movflags', '+faststart', out],
  { stdio: ['pipe', 'ignore', 'inherit'] });

for (let i = 0; i < total; i++) {
  await page.evaluate(t => window.seek(t), i / FPS);
  ff.stdin.write(await page.screenshot({ type: 'png' }));
  if (i % FPS === 0) process.stdout.write(`\rFrame ${i}/${total}`);
}
ff.stdin.end();
await new Promise(r => ff.on('close', r));
await browser.close();
console.log(`\nSiap: ${out}`);
})();
