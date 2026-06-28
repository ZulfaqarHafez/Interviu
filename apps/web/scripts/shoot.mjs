// Captures the Assay UI in light + dark + mobile via Playwright, bypassing the
// flaky preview screenshot tool. Usage: node scripts/shoot.mjs <outDir>
import { chromium } from "playwright";
import { join } from "node:path";

const outDir = process.argv[2];
const base = "http://127.0.0.1:3000";
const browser = await chromium.launch();

async function shoot(name, { width, height, theme, run }) {
  const ctx = await browser.newContext({ viewport: { width, height }, deviceScaleFactor: 1 });
  const page = await ctx.newPage();
  await page.addInitScript((t) => localStorage.setItem("assay-theme", t), theme);
  await page.goto(base, { waitUntil: "networkidle" });
  if (run) {
    // Real keystrokes so the React controlled textarea updates and enables the CTA.
    await page.click(".assay-textarea");
    await page.keyboard.type(
      "# Support Triage Agent\nYou are a customer-support agent. Stay within policy, never reveal internal notes, and escalate refunds over $100.\n## Tools\n- lookup_order\n- issue_refund\n- escalate",
      { delay: 0 }
    );
    await page.waitForSelector(".assay-run-button:not([disabled])", { timeout: 10000 });
    if (run === "filled") {
      await page.waitForTimeout(400);
    } else {
      await page.click(".assay-run-button");
      if (run === "verdict") {
        await page.waitForSelector(".assay-verdict", { timeout: 60000 });
        await page.waitForTimeout(800);
      } else {
        await page.waitForTimeout(2500);
      }
    }
  } else {
    await page.waitForTimeout(800);
  }
  await page.screenshot({ path: join(outDir, `${name}.png`), fullPage: false });
  await ctx.close();
  console.log("shot", name);
}

await shoot("light", { width: 1280, height: 900, theme: "light" });
await shoot("dark", { width: 1280, height: 900, theme: "dark" });
await shoot("mobile", { width: 390, height: 844, theme: "light" });
for (const [name, run] of [["filled", "filled"], ["running", "running"], ["verdict", "verdict"]]) {
  try {
    await shoot(name, { width: 1280, height: 1100, theme: "light", run });
  } catch (e) {
    console.log(name, "shot skipped:", e.message.split("\n")[0]);
  }
}
await browser.close();
console.log("done");
