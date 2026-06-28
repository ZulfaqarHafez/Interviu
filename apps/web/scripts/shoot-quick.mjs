import { chromium } from "playwright";
import { join } from "node:path";
const outDir = process.argv[2];
const b = await chromium.launch();
async function shot(name, w, h, theme){
  const ctx = await b.newContext({viewport:{width:w,height:h}});
  const p = await ctx.newPage();
  await p.addInitScript((t)=>localStorage.setItem("assay-theme",t), theme);
  await p.goto("http://127.0.0.1:3000/",{waitUntil:"networkidle"});
  await p.waitForTimeout(900);
  await p.screenshot({path:join(outDir,`${name}.png`)});
  await ctx.close(); console.log("shot",name);
}
await shot("calm-light",1280,860,"light");
await shot("calm-dark",1280,860,"dark");
await shot("calm-mobile",390,844,"light");
await b.close(); console.log("done");
