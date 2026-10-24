import fs from 'node:fs';
import path from 'node:path';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {fileURLToPath} from 'node:url';
const root=path.dirname(fileURLToPath(import.meta.url));
const require=createRequire(import.meta.url);
const {chromium}=require(process.env.PLAYWRIGHT_PATH||'C:/Users/18010/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe'});
try{
 const page=await browser.newPage({viewport:{width:1440,height:1000}});
 const errors=[],failed=[];
 page.on('pageerror',e=>errors.push(e.message));
 page.on('response',r=>{if(r.status()>=500)failed.push({url:r.url(),status:r.status()})});
 const response=await page.goto('http://localhost/',{waitUntil:'networkidle',timeout:60000});
 assert.equal(response.status(),200);
 await page.locator('input').first().waitFor();
 await page.screenshot({path:path.join(root,'login.png'),fullPage:true});
 assert.equal(errors.length,0,errors.join('\n'));
 assert.equal(failed.length,0,JSON.stringify(failed));
 const report={status:'pass',url:page.url(),title:await page.title(),formInputs:await page.locator('input').count(),browserErrors:errors,serverErrors:failed,generated:new Date().toISOString()};
 fs.writeFileSync(path.join(root,'frontend-verification.json'),JSON.stringify(report,null,2));
 console.log(JSON.stringify(report));
}finally{await browser.close()}
