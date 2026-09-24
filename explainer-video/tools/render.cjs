#!/usr/bin/env node
/**
 * tools/render.cjs — Frame-exact renderer for src/index.html.
 *
 * The page exposes window.__seek(t); we step through time at a fixed FPS,
 * screenshot each frame with headless Chromium and pipe the frames to ffmpeg.
 *
 *   node tools/render.cjs video  <out.mp4> [fps]             (video-only, near-lossless master)
 *   node tools/render.cjs stills <outDir> <t1> <t2> …      (PNG snapshots for review)
 *
 * Env: FFMPEG (path to ffmpeg with libx264), NODE_PATH (to find playwright).
 */
const path = require("path");
const fs = require("fs");
const { spawn } = require("child_process");
const { chromium } = require("playwright");

const ROOT = path.resolve(__dirname, "..");
const PAGE = "file://" + path.join(ROOT, "src", "index.html") + "?render=1";

async function openPage() {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1920, height: 1080 }, deviceScaleFactor: 1 });
  page.on("pageerror", e => { console.error("[page]", e.message); process.exitCode = 1; });
  await page.goto(PAGE);
  await page.waitForFunction(() => window.__ready === true, null, { timeout: 30000 });
  const cdp = await page.context().newCDPSession(page);
  return { browser, page, cdp };
}

async function shot(page, cdp, t, format = "jpeg") {
  await page.evaluate(x => window.__seek(x), t);
  const opts = format === "png" ? { format: "png" } : { format: "jpeg", quality: 94, optimizeForSpeed: true };
  const { data } = await cdp.send("Page.captureScreenshot", opts);
  return Buffer.from(data, "base64");
}

async function stills(outDir, times) {
  fs.mkdirSync(outDir, { recursive: true });
  const { browser, page, cdp } = await openPage();
  for (const t of times) {
    const buf = await shot(page, cdp, t, "png");
    const f = path.join(outDir, `t${String(t).padStart(6, "0")}.png`);
    fs.writeFileSync(f, buf);
    console.log(f);
  }
  await browser.close();
}

async function video(out, fps) {
  const { browser, page, cdp } = await openPage();
  const duration = await page.evaluate(() => window.__duration);
  const frames = Math.ceil(duration * fps);
  const ffmpeg = process.env.FFMPEG || "ffmpeg";
  const args = [
    "-y", "-loglevel", "error",
    "-f", "image2pipe", "-framerate", String(fps), "-c:v", "mjpeg", "-i", "-",
    "-c:v", "libx264", "-preset", "medium", "-crf", "12", "-pix_fmt", "yuv420p",
    out,
  ];
  const ff = spawn(ffmpeg, args, { stdio: ["pipe", "inherit", "inherit"] });
  const done = new Promise((res, rej) => ff.on("close", c => (c === 0 ? res() : rej(new Error("ffmpeg exit " + c)))));

  const t0 = Date.now();
  for (let i = 0; i < frames; i++) {
    const buf = await shot(page, cdp, i / fps);
    if (!ff.stdin.write(buf)) await new Promise(r => ff.stdin.once("drain", r));
    if (i % (fps * 10) === 0) {
      const el = (Date.now() - t0) / 1000;
      console.log(`[render] ${(i / fps).toFixed(0)}s / ${duration.toFixed(0)}s  (${el.toFixed(0)}s elapsed)`);
    }
  }
  ff.stdin.end();
  await done;
  await browser.close();
  console.log(`[render] ${frames} frames → ${out}`);
}

(async () => {
  const [mode, ...rest] = process.argv.slice(2);
  if (mode === "stills") await stills(rest[0], rest.slice(1).map(Number));
  else if (mode === "video") await video(rest[0], Number(rest[1] || 30));
  else { console.error("usage: render.cjs video <out> [fps] | stills <dir> <t…>"); process.exit(2); }
})().catch(e => { console.error(e); process.exit(1); });
