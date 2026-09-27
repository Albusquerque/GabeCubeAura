/** Capture the legacy visual template, cropped to its machine and LED preview. */
import { chromium } from "playwright";
import { execFileSync } from "node:child_process";
import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";

const [variantsPath, languagePath, outputPath] = process.argv.slice(2);
if (!variantsPath || !languagePath || !outputPath) {
  throw new Error("Usage: node scripts/capture_readme_gifs.mjs <variants.html> <language.html> <output-dir>");
}
const performanceOnly = process.argv.includes("--performance-only");

const INTERVAL_MS = 125;
const CAPTURE_CSP = "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src data:; font-src data:; connect-src 'none'; frame-src 'none'; object-src 'none'";
const targetDir = path.resolve(outputPath);
await fs.mkdir(targetDir, { recursive: true });
const scratch = await fs.mkdtemp(path.join(os.tmpdir(), "gabecubeaura-readme-capture-"));
const browser = await chromium.launch({ headless: true });

async function loadMockup(source, viewportWidth, staticBase = false) {
  const page = await browser.newPage({ viewport: { width: viewportWidth, height: 760 }, deviceScaleFactor: 1 });
  await page.setContent('<!doctype html><html><body style="margin:0"><iframe sandbox="allow-scripts" style="display:block;border:0;width:100%;height:740px"></iframe></body></html>');
  const sourceHtml = await fs.readFile(source, "utf8");
  const fragment = staticBase ? sourceHtml.replace(/<script>[\s\S]*?<\/script>/g, "") : sourceHtml;
  await page.locator("iframe").evaluate((iframe, { html, csp }) => {
    iframe.srcdoc = `<!doctype html><html><head><meta http-equiv="Content-Security-Policy" content="${csp}"><style>html,body{margin:0}</style></head><body>${html}</body></html>`;
  }, { html: fragment, csp: CAPTURE_CSP });
  // The frame is sandboxed, just like the published original mockup.
  const frame = page.frameLocator("iframe");
  await frame.locator(".sb-machine").waitFor();
  return { page, frame };
}

async function captureFrames(locator, durationMs, folder, startIndex = 0) {
  await fs.mkdir(folder, { recursive: true });
  const count = Math.ceil(durationMs / INTERVAL_MS);
  const started = Date.now();
  for (let i = 0; i < count; i++) {
    const wait = started + i * INTERVAL_MS - Date.now();
    if (wait > 0) await new Promise((resolve) => setTimeout(resolve, wait));
    await locator.screenshot({ path: path.join(folder, `${String(startIndex + i).padStart(4, "0")}.png`) });
  }
  return count;
}

function encode(name, folder) {
  const output = path.join(targetDir, `${name}.gif`);
  execFileSync("python3", [path.join(import.meta.dirname, "encode_readme_gif.py"), folder, output, String(INTERVAL_MS)], { stdio: "inherit" });
  console.log(output);
}

async function captureVariant(source, variant, durationMs, name) {
  const { page, frame } = await loadMockup(source, 1040);
  const folder = path.join(scratch, name);
  await frame.locator(`[data-variant="${variant}"]`).click();
  await frame.locator(".sb-preview-head").evaluate((header) => {
    const [label, state] = header.children;
    label.textContent = "Logical Decky preview · 17 LEDs";
    state.style.fontSize = "0";
    const style = document.createElement("style");
    style.textContent = ".sb-state::after{content:'Playing';font-size:12px}";
    document.head.appendChild(style);
  });
  await captureFrames(frame.locator(".sb-left"), durationMs + 500, folder);
  encode(name, folder);
  await page.close();
}

async function captureRecording(source) {
  const { page, frame } = await loadMockup(source, 1000);
  const folder = path.join(scratch, "recording");
  const crop = frame.locator(".sb-stage-column");
  await frame.locator("#sb-alerts-background").selectOption("off");
  await frame.locator('[data-scene="record-start"]').click();
  let index = await captureFrames(crop, 1350, folder);
  index += await captureFrames(crop, 750, folder, index);
  await frame.locator('[data-scene="record-stop"]').click();
  await captureFrames(crop, 1200, folder, index);
  encode("recording", folder);
  await page.close();
}

function lerp(a, b, t) { return Math.round(a + (b - a) * t); }
function mix(a, b, t) { return a.map((value, i) => lerp(value, b[i], t)); }
function clamp(value, min, max) { return Math.max(min, Math.min(max, value)); }

function temperatureColor(temperature) {
  const cool = [43, 213, 230];
  const warm = [255, 204, 61];
  const hot = [244, 70, 76];
  if (temperature <= 64) return mix(cool, warm, clamp((temperature - 44) / 20, 0, 1));
  return mix(warm, hot, clamp((temperature - 64) / 20, 0, 1));
}

function performanceFrame(t) {
  const phase = 2 * Math.PI * t / 4;
  const cpuHeat = (1 - Math.cos(phase)) / 2;
  const gpuHeat = (1 - Math.cos(phase + 1.45)) / 2;
  const cpuLoad = Math.round(28 + 50 * cpuHeat);
  const gpuLoad = Math.round(42 + 52 * gpuHeat);
  const cpuTemp = Math.round(44 + 38 * cpuHeat);
  const gpuTemp = Math.round(50 + 35 * gpuHeat);
  const cpuLit = Math.round(cpuLoad / 100 * 8);
  const gpuLit = Math.round(gpuLoad / 100 * 8);
  const cpuColor = temperatureColor(cpuTemp);
  const gpuColor = temperatureColor(gpuTemp);
  // Mirrored mixed mode: CPU grows from the left edge, GPU from the right.
  // LED 9 is the unlit separator between the two 8-LED meters.
  const colors = Array.from({ length: 17 }, (_, i) => i === 8 ? [0, 0, 0]
    : i < 8 ? i < cpuLit ? cpuColor : [0, 0, 0]
      : i >= 17 - gpuLit ? gpuColor : [0, 0, 0]);
  return { colors, cpuLoad, gpuLoad, cpuTemp, gpuTemp, cpuColor, gpuColor };
}

function countdownFrame(t) {
  const progress = Math.min(1, t / 4.8);
  const lit = Math.max(1, 17 - Math.round(progress * 16));
  const base = progress < .65 ? mix([69, 211, 226], [253, 176, 61], progress / .65)
    : mix([253, 176, 61], [235, 49, 64], (progress - .65) / .35);
  const comet = Math.round(16 - (t * 5.5) % 17);
  return Array.from({ length: 17 }, (_, i) => i < lit
    ? i === comet ? mix(base, [255, 245, 224], .32) : base
    : [0, 0, 0]);
}

async function captureBase(source, name, makeFrame, durationMs) {
  const { page, frame } = await loadMockup(source, 1000, true);
  // Preserve the mockup's exact HTML/CSS scene; pause its own alert loop, which
  // has no animated Performance or Countdown state, and drive only its 17 LEDs.
  await frame.locator(".sb-machine").waitFor();
  await frame.locator(".sb-center-marker").evaluate((marker) => { marker.style.display = "none"; });
  if (name === "performance") {
    await frame.locator(".sb-stage-column").evaluate((column) => {
      column.querySelector(".sb-stage-label").textContent = "CPU + GPU · MIRRORED";
      const head = column.querySelector(".sb-readout-head");
      head.innerHTML = '<span class="sb-perf-stat"><span class="sb-perf-tag">CPU</span><strong class="sb-cpu-value"></strong></span><span class="sb-perf-stat"><span class="sb-perf-tag">GPU</span><strong class="sb-gpu-value"></strong></span>';
      const guide = column.querySelector(".sb-center-marker");
      guide.textContent = "LENGTH = LOAD  ·  COLOUR = TEMPERATURE";
      guide.style.display = "block";
      const style = document.createElement("style");
      style.textContent = `
        #sb-alerts-concept .sb-readout-head { align-items: center; margin-bottom: 12px; }
        #sb-alerts-concept .sb-perf-stat { display: flex; align-items: baseline; gap: 7px; white-space: nowrap; }
        #sb-alerts-concept .sb-perf-tag { color: #e9f0f6; font-size: 15px; font-weight: 800; letter-spacing: .04em; }
        #sb-alerts-concept .sb-perf-stat strong { font-size: 15px; font-variant-numeric: tabular-nums; font-weight: 750; }
        #sb-alerts-concept .sb-center-marker { margin-top: 10px; font-size: 10px; letter-spacing: .08em; }
      `;
      document.head.appendChild(style);
    });
  }
  const folder = path.join(scratch, name);
  await fs.mkdir(folder, { recursive: true });
  const count = Math.ceil(durationMs / INTERVAL_MS);
  for (let i = 0; i < count; i++) {
    const sample = makeFrame(i * INTERVAL_MS / 1000);
    await frame.locator(".sb-stage-column").evaluate((column, data) => {
      const rgb = Array.isArray(data) ? data : data.colors;
      const cellsHost = column.querySelector(".sb-logic");
      if (!cellsHost.children.length) for (let index = 0; index < 17; index++) cellsHost.appendChild(document.createElement("span"));
      const gradient = `linear-gradient(90deg, ${rgb.map((color, index) => `rgb(${color.join(",")}) ${((index + .5) / 17 * 100).toFixed(2)}%`).join(",")})`;
      column.querySelector(".sb-light-core").style.background = gradient;
      column.querySelector(".sb-light-bloom").style.background = gradient;
      [...cellsHost.children].forEach((cell, index) => { cell.style.background = `rgb(${rgb[index].join(",")})`; });
      if (!Array.isArray(data)) {
        const cpu = column.querySelector(".sb-cpu-value");
        const gpu = column.querySelector(".sb-gpu-value");
        cpu.textContent = `${data.cpuLoad}% · ${data.cpuTemp}°C`;
        gpu.textContent = `${data.gpuLoad}% · ${data.gpuTemp}°C`;
        cpu.style.color = `rgb(${data.cpuColor.join(",")})`;
        gpu.style.color = `rgb(${data.gpuColor.join(",")})`;
      } else {
        column.querySelector("#sb-alerts-status").textContent = "";
      }
    }, sample);
    await frame.locator(".sb-stage-column").screenshot({ path: path.join(folder, `${String(i).padStart(4, "0")}.png`) });
  }
  encode(name, folder);
  await page.close();
}

try {
  if (!performanceOnly) {
    await captureVariant(variantsPath, "notification-ample", 3600, "notification");
    await captureVariant(variantsPath, "screenshot-bloom", 3250, "screenshot");
    await captureVariant(variantsPath, "achievement-twoway", 4850, "achievement");
    await captureRecording(languagePath);
  }
  await captureBase(languagePath, "performance", performanceFrame, 4000);
  if (!performanceOnly) await captureBase(languagePath, "countdown", countdownFrame, 4800);
} finally {
  await browser.close();
  await fs.rm(scratch, { recursive: true, force: true });
}
