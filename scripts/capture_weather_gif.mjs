/** Capture Weather directly from the published-style concept simulator. */
import { chromium } from "playwright";
import { execFileSync } from "node:child_process";
import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";

const root = path.resolve(import.meta.dirname, "..");
const site = process.argv[2] || "http://127.0.0.1:8765/";
const output = path.join(root, "assets/readme-gifs/weather.gif");
const scratch = await fs.mkdtemp(path.join(os.tmpdir(), "gabecubeaura-weather-gif-"));
const browser = await chromium.launch({ headless: true });
const interval = 125;

try {
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2 });
  await page.goto(site, { waitUntil: "networkidle" });
  await page.locator('[data-tab="weather"]').click();
  await page.waitForFunction(() => document.querySelector("#providerBadge")?.textContent === "WEATHER");
  // Match the other README GIFs: only the machine and logical LED readout.
  await page.locator(".stage-shell .stage-top,.stage-shell .stage-context,.stage-shell .demo-disclaimer").evaluateAll((elements) => {
    for (const element of elements) element.style.display = "none";
  });
  const preview = page.locator(".stage-shell");
  await preview.waitFor();
  let count = 0;
  for (const [condition, variant, duration] of [["clear_day", "0", 5000], ["rain", "0", 4250]]) {
    await page.locator("#weatherCondition").selectOption(condition);
    await page.locator("#weatherVariant").selectOption(variant);
    await page.locator("#weatherReplay").click();
    const started = Date.now();
    for (let elapsed = 0; elapsed < duration; elapsed += interval) {
      const wait = started + elapsed - Date.now();
      if (wait > 0) await new Promise((resolve) => setTimeout(resolve, wait));
      await preview.screenshot({ path: path.join(scratch, `${String(count++).padStart(4, "0")}.png`) });
    }
  }
  execFileSync("python3", [path.join(root, "scripts/encode_readme_gif.py"), scratch, output, String(interval), "500", "96"], { stdio: "inherit" });
  console.log(output);
} finally {
  await browser.close();
  await fs.rm(scratch, { recursive: true, force: true });
}
