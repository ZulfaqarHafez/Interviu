// Captures full-page screenshots incl. the expanded "Evaluation cockpit".
import { chromium } from "playwright";
import { join } from "node:path";

const outDir = process.argv[2];
const base = "http://127.0.0.1:3000";
const browser = await chromium.launch();

async function shoot(name, { width, height, theme, expand }) {
  const ctx = await browser.newContext({ viewport: { width, height }, deviceScaleFactor: 1 });
  const page = await ctx.newPage();
  await page.addInitScript((t) => localStorage.setItem("assay-theme", t), theme);
  await page.goto(base, { waitUntil: "networkidle" });
  await page.waitForTimeout(1200);
  if (expand) {
    await page.click("summary:has-text('Evaluation cockpit')").catch(() => {});
    await page.waitForTimeout(1000);
  }
  await page.screenshot({ path: join(outDir, `${name}.png`), fullPage: true });
  await ctx.close();
  console.log("shot", name);
}

await shoot("cockpit-light", { width: 1400, height: 900, theme: "light", expand: true });
await shoot("cockpit-dark", { width: 1400, height: 900, theme: "dark", expand: true });
await browser.close();
console.log("done");
