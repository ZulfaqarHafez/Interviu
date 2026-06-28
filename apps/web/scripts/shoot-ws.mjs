import { chromium } from "playwright";
import { join } from "node:path";
const out = process.argv[2];
const b = await chromium.launch();
async function shot(name, path, full=false){
  const ctx = await b.newContext({viewport:{width:1280,height:860}});
  const p = await ctx.newPage();
  await p.addInitScript(()=>localStorage.setItem("assay-theme","light"));
  const errs=[]; p.on("pageerror",e=>errs.push(e.message));
  await p.goto("http://127.0.0.1:3000"+path,{waitUntil:"domcontentloaded"});
  await p.waitForTimeout(2500);
  await p.screenshot({path:join(out,name+".png"), fullPage:full});
  if(errs.length) console.log(name,"ERRORS:",errs.slice(0,2));
  await ctx.close(); console.log("shot",name);
}
await shot("ws-home","/");
await shot("ws-runs","/runs");
await shot("ws-suites","/suites");
await shot("ws-agents","/agents");
await b.close(); console.log("done");
