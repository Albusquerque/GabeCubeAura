/** Capture the controller motion mockup's machine and logical LED preview. */
import { chromium } from "playwright";
import { execFileSync } from "node:child_process";
import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";

const root = path.resolve(import.meta.dirname, "..");
const source = await fs.readFile(path.join(root, "assets/controller-motion-demo.html"), "utf8");
const output = path.join(root, "assets/readme-gifs/controller-battery.gif");
const scratch = await fs.mkdtemp(path.join(os.tmpdir(), "gabecubeaura-controller-gif-"));
const browser = await chromium.launch({ headless: true });
const interval = 150;

try {
  const page = await browser.newPage({ viewport: { width: 1024, height: 740 }, deviceScaleFactor: 2 });
  await page.setContent('<!doctype html><html><body style="margin:0"><iframe sandbox="allow-scripts" style="display:block;border:0;width:100%;height:720px"></iframe></body></html>');
  await page.locator("iframe").evaluate((iframe, html) => {
    const csp = "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src data:; connect-src 'none'; frame-src 'none'; object-src 'none'";
    iframe.srcdoc = `<!doctype html><html><head><meta http-equiv="Content-Security-Policy" content="${csp}"><style>html,body{margin:0}#sb-motion-lab .sb-picks,#sb-motion-lab .sb-caption{display:none}#sb-motion-lab .sb-visual{align-self:start}</style></head><body>${html}<style>#sb-motion-lab .sb-light{filter:blur(.8px)}#sb-motion-lab .sb-bloom{top:-5px;height:18px;filter:blur(5px);opacity:.38!important}#sb-motion-lab .sb-reflection{filter:blur(4px);opacity:.12}</style></body></html>`;
  }, source);
  const frame = page.frameLocator("iframe");
  const crop = frame.locator(".sb-visual");
  await crop.waitFor();
  let count = 0;
  const scenes = [
    { scene: "duo", variant: 2, battery: 41, duration: 3900 },
    { scene: "charging", variant: 1, battery: 41, duration: 2700 },
  ];
  for (const { scene, variant, battery, duration } of scenes) {
    await frame.locator("#sb-motion-battery").evaluate((slider, value) => {
      slider.value = String(value);
      slider.dispatchEvent(new Event("input", { bubbles: true }));
    }, battery);
    await frame.locator(`[data-scene="${scene}"]`).click();
    await frame.locator(".sb-choice").nth(variant).evaluate((button) => button.click());
    const started = Date.now();
    for (let elapsed = 0; elapsed < duration; elapsed += interval) {
      const wait = started + elapsed - Date.now();
      if (wait > 0) await new Promise((resolve) => setTimeout(resolve, wait));
      await crop.screenshot({ path: path.join(scratch, `${String(count++).padStart(4, "0")}.png`) });
    }
  }
  execFileSync("python3", [path.join(root, "scripts/encode_readme_gif.py"), scratch, output, String(interval), "500", "96"], { stdio: "inherit" });
  console.log(output);
} finally {
  await browser.close();
  await fs.rm(scratch, { recursive: true, force: true });
}
