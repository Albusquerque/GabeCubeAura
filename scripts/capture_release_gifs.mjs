/**
 * Build the GabeCubeAura README GIFs from the local Concept Lab.
 *
 * The Concept Lab is deliberately used as the visual source so the new media
 * keeps the same Steam Machine, logical 17-LED preview and typography as the
 * existing README animations. The page remains a simulator; these captures do
 * not claim physical-hardware validation.
 */
import { chromium } from "playwright";
import { execFileSync } from "node:child_process";
import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { pathToFileURL } from "node:url";

const root = path.resolve(import.meta.dirname, "..");
const conceptRoot = path.resolve(process.argv[2] || path.join(root, "..", "signalbar-concept-site"));
const requestedCaptures = new Set(process.argv.slice(3));
const conceptIndex = path.join(conceptRoot, "index.html");
const outputRoot = path.join(root, "assets", "readme-gifs");
const interval = 125;

await fs.access(conceptIndex);
await fs.mkdir(outputRoot, { recursive: true });
const scratch = await fs.mkdtemp(path.join(os.tmpdir(), "gabecubeaura-release-gifs-"));
const browser = await chromium.launch({ headless: true });

function encode(name, folder, colours = 96) {
  const output = path.join(outputRoot, `${name}.gif`);
  execFileSync(
    "python3",
    [path.join(root, "scripts", "encode_readme_gif.py"), folder, output, String(interval), "500", String(colours)],
    { stdio: "inherit" },
  );
  console.log(output);
}

async function captureFor(locator, durationMs, folder, startIndex = 0) {
  await fs.mkdir(folder, { recursive: true });
  const count = Math.ceil(durationMs / interval);
  const started = Date.now();
  for (let index = 0; index < count; index++) {
    const wait = started + index * interval - Date.now();
    if (wait > 0) await new Promise((resolve) => setTimeout(resolve, wait));
    await locator.screenshot({ path: path.join(folder, `${String(startIndex + index).padStart(4, "0")}.png`) });
  }
  return count;
}

async function openLab() {
  // The published page intentionally forbids inline styles. Bypass that CSP in
  // this isolated capture context only so framing rules never weaken the site.
  const context = await browser.newContext({
    viewport: { width: 1180, height: 900 },
    deviceScaleFactor: 2,
    bypassCSP: true,
  });
  const page = await context.newPage();
  await page.goto(pathToFileURL(conceptIndex).href, { waitUntil: "load" });
  await page.locator(".stage-shell").waitFor();
  await page.addStyleTag({ content: `
    .stage-shell { position: static !important; }
    .stage-top, .stage-explain, .demo-disclaimer { display: none !important; }
    .machine-scene { height: 320px !important; }
    .logical-panel { padding-top: 15px !important; }
    #gif-palette-banner {
      display: grid; grid-template-columns: 142px 1fr; gap: 14px; align-items: center;
      min-height: 82px; padding: 12px 16px; background: #192a35;
      border-bottom: 1px solid #3a5260;
    }
    #gif-palette-banner img { width: 142px; height: 62px; object-fit: cover; border-radius: 5px; }
    #gif-palette-banner strong, #gif-palette-banner small { display: block; }
    #gif-palette-banner strong { color: #edf8f6; font-size: 14px; margin-bottom: 8px; }
    #gif-palette-banner small { color: #9cb5be; font-size: 10px; margin-top: 7px; }
    #gif-palette-swatches { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 6px; }
    #gif-palette-swatches i { height: 15px; border: 1px solid #ffffff2b; border-radius: 3px; }
  ` });
  return page;
}

async function fillHex(page, selector, value) {
  await page.locator(selector).fill(value);
  await page.locator(selector).blur();
}

async function captureCustomization() {
  const page = await openLab();
  const folder = path.join(scratch, "customization-plus");
  const stage = page.locator(".stage-shell");
  await page.locator('[data-tab="customization"]').click();
  let frame = 0;

  await page.locator("#customPattern").selectOption("color-wipe");
  await page.locator("#customPaletteCount").selectOption("2");
  await fillHex(page, "#customHex1", "#FFD000");
  await fillHex(page, "#customHex2", "#00C8FF");
  await page.locator("#customBrightness").fill("220");
  await page.locator("#customSpeed").fill("42");
  await page.locator("#customDirection").selectOption("forward");
  await page.locator("#customPreview").click();
  frame += await captureFor(stage, 2500, folder, frame);

  await page.locator("#customPattern").selectOption("event:achievement-supernova");
  await page.locator("#customPaletteCount").selectOption("3");
  await fillHex(page, "#customHex1", "#7F22EE");
  await fillHex(page, "#customHex2", "#FF3C9D");
  await fillHex(page, "#customHex3", "#00C8FF");
  await page.locator("#customBrightness").fill("190");
  await page.locator("#customSpeed").fill("68");
  await page.locator("#customDirection").selectOption("reverse");
  frame += await captureFor(stage, 3000, folder, frame);

  await page.locator("#customPattern").selectOption("ripple");
  await page.locator("#customPaletteCount").selectOption("2");
  await fillHex(page, "#customHex1", "#FF7A18");
  await fillHex(page, "#customHex2", "#30E3CA");
  await page.locator("#customBrightness").fill("235");
  await page.locator("#customSpeed").fill("82");
  await page.locator("#customDirection").selectOption("forward");
  await captureFor(stage, 2500, folder, frame);

  encode("customization-plus", folder);
  await page.close();
}

async function waitForLaunchPalette(page, game, count) {
  await page.locator(`#launchPalette[data-palette-key="${game}:hero:artwork:${count}"]`).waitFor();
  await page.locator("#launchArtImage").evaluate((image) => image.decode());
}

async function installPaletteBanner(page) {
  await page.locator(".stage-context").evaluate((context) => {
    const banner = document.createElement("div");
    banner.id = "gif-palette-banner";
    banner.innerHTML = '<img alt=""><div><strong></strong><div id="gif-palette-swatches"></div><small></small></div>';
    context.insertAdjacentElement("afterend", banner);
  });
}

async function syncPaletteBanner(page) {
  await page.evaluate(() => {
    const banner = document.querySelector("#gif-palette-banner");
    const source = document.querySelector("#launchArtImage");
    banner.querySelector("img").src = source.src;
    banner.querySelector("img").alt = source.alt;
    banner.querySelector("strong").textContent = document.querySelector("#launchArtTitle").textContent;
    banner.querySelector("small").textContent = document.querySelector("#launchPaletteStatus").textContent;
    banner.querySelector("#gif-palette-swatches").replaceChildren(
      ...[...document.querySelectorAll("#launchPalette span")].map((sourceSwatch) => {
        const swatch = document.createElement("i");
        swatch.style.background = sourceSwatch.style.background;
        return swatch;
      }),
    );
  });
}

async function selectLaunchGame(page, game, count) {
  await page.locator(`[data-launch-game="${game}"]`).click();
  await page.locator("#launchSource").selectOption("hero");
  await page.locator("#launchPaletteMode").selectOption("artwork");
  await page.locator("#launchColourCount").selectOption(String(count));
  await waitForLaunchPalette(page, game, count);
}

async function captureLaunchPalettes() {
  const page = await openLab();
  const folder = path.join(scratch, "game-launch-palettes");
  const stage = page.locator(".stage-shell");
  await page.locator('[data-tab="launches"]').click();
  await installPaletteBanner(page);
  let frame = 0;

  for (const [game, count] of [["drg", 2], ["witcher", 2], ["balatro", 3]]) {
    await selectLaunchGame(page, game, count);
    await syncPaletteBanner(page);
    frame += await captureFor(stage, 2200, folder, frame);
  }

  encode("game-launch-palettes", folder);
  await page.close();
}

async function captureLaunchPatterns() {
  const page = await openLab();
  const folder = path.join(scratch, "game-launch-patterns");
  const stage = page.locator(".stage-shell");
  await page.locator('[data-tab="launches"]').click();
  await selectLaunchGame(page, "balatro", 2);
  await page.locator("#launchDuration").fill("4");
  let frame = 0;

  for (const pattern of ["crescendo", "color-wipe", "scanner"]) {
    await page.locator("#launchPattern").selectOption(pattern);
    await page.locator("#launchPreview").click();
    frame += await captureFor(stage, 4600, folder, frame);
  }

  encode("game-launch-patterns", folder);
  await page.close();
}

try {
  if (!requestedCaptures.size || requestedCaptures.has("customization-plus")) await captureCustomization();
  if (!requestedCaptures.size || requestedCaptures.has("game-launch-palettes")) await captureLaunchPalettes();
  if (!requestedCaptures.size || requestedCaptures.has("game-launch-patterns")) await captureLaunchPatterns();
} finally {
  await browser.close();
  await fs.rm(scratch, { recursive: true, force: true });
}
