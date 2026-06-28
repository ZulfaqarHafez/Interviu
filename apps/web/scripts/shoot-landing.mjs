import { chromium } from "playwright";
import { join } from "node:path";
const out = process.argv[2];
const b = await chromium.launch();
async function shot(name, theme){
  const ctx = await b.newContext({ viewport:{width:1280,height:900} });
  const p = await ctx.newPage();
  await p.addInitScript((t)=>localStorage.setItem("assay-theme",t), theme);
  await p.goto("http://127.0.0.1:3000/",{waitUntil:"networkidle"});
  await p.waitForTimeout(1000);
  const ov = await p.evaluate(()=>document.documentElement.scrollWidth>window.innerWidth+2);
  console.log(name,"overflow:",ov);
  await p.screenshot({path:join(out,`${name}.png`), fullPage:true});
  await ctx.close(); console.log("shot",name);
}
await shot("landing-light","light");
await shot("landing-dark","dark");
await b.close(); console.log("done");
