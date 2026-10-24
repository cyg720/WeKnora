// Authoring utility; generated HTML does not depend on this script or archify.
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawnSync } from 'node:child_process';
import crypto from 'node:crypto';
const root=path.dirname(fileURLToPath(import.meta.url));
const cli=process.env.ARCHIFY_CLI||'C:/Users/18010/.codex/skills/archify/bin/archify.mjs';
const selection=process.argv.slice(2);
const specs=[['architecture','architecture'],['rag','sequence'],['agent','workflow'],['ingest','dataflow'],['lifecycle','lifecycle'],['automation','workflow']].filter(([name])=>!selection.length||selection.includes(name));
let failed=false;
for(const [name,type] of specs){
 // Version the trusted output; keep previous accepted HTML as evidence.
 const specPath=path.join(root,'diagrams',name+'.json');
 const specHash=crypto.createHash('sha256').update(fs.readFileSync(specPath)).digest('hex').slice(0,12);
 const out=path.join(root,'diagrams',name+'.'+specHash+'.archify.html');
 const delivery=spawnSync(process.execPath,[cli,'deliver',type,path.join(root,'diagrams',name+'.json'),out,'--quality','showcase','--json'],{encoding:'utf8',timeout:60000});
 let receipt;try{receipt=JSON.parse(delivery.stdout)}catch{receipt={ok:false,error:delivery.stderr||delivery.stdout}}
 fs.writeFileSync(path.join(root,'diagrams',name+'.delivery.json'),JSON.stringify(receipt,null,2));
 console.log(name, 'delivery',delivery.status,receipt.ok??receipt.status);
 if(delivery.status!==0){failed=true;console.log(JSON.stringify(receipt.diagnostics||receipt.error));continue}
 const browser=spawnSync(process.execPath,[cli,'visual-check',out,'--json'],{encoding:'utf8',timeout:60000});
 let evidence;try{evidence=JSON.parse(browser.stdout)}catch{evidence={error:browser.stderr||browser.stdout}}
 fs.writeFileSync(path.join(root,'diagrams',name+'.browser-run.json'),JSON.stringify({exitCode:browser.status,...evidence},null,2));
 console.log(name,'browser',browser.status,evidence.status);
 if(browser.status===1)failed=true;
 // Keep the accepted artifact immutable. Create a documented derivative for
 // the user's explicit offline requirement and an upstream runtime guard bug.
 const original=fs.readFileSync(out,'utf8');
 const fontLinks=original.match(/<link\b[^>]*href="https:\/\/fonts\.(?:googleapis|gstatic)\.com[^>]*>/g)||[];
 const unsafe='Archify.guidedViews && Archify.guidedViews.isPlaying())';
 const safe='Archify.guidedViews && typeof Archify.guidedViews.isPlaying === "function" && Archify.guidedViews.isPlaying())';
 const adapted=original.replace(/<link\b[^>]*href="https:\/\/fonts\.(?:googleapis|gstatic)\.com[^>]*>/g,'').replaceAll(unsafe,safe);
 const offlinePath=path.join(root,'diagrams',name+'.html');fs.writeFileSync(offlinePath,adapted);
 const derivativeCheck=spawnSync(process.execPath,[cli,'check',offlinePath],{encoding:'utf8',timeout:60000});
 const derivativeBrowser=spawnSync(process.execPath,[cli,'visual-check',offlinePath,'--json'],{encoding:'utf8',timeout:60000});
 let derivativeEvidence;try{derivativeEvidence=JSON.parse(derivativeBrowser.stdout)}catch{derivativeEvidence={error:derivativeBrowser.stderr||derivativeBrowser.stdout}}
 fs.writeFileSync(path.join(root,'diagrams',name+'.offline-adapter.json'),JSON.stringify({originalSha256:crypto.createHash('sha256').update(original).digest('hex'),offlineSha256:crypto.createHash('sha256').update(adapted).digest('hex'),removedExternalFontLinks:fontLinks.length,guardReplacements:original.split(unsafe).length-1,artifactCheckExit:derivativeCheck.status,artifactCheck:derivativeCheck.stdout,browserExit:derivativeBrowser.status,browserEvidence:derivativeEvidence,visualReview:'pending'},null,2));
 console.log(name,'offline check',derivativeCheck.status,'browser',derivativeBrowser.status);
 if(derivativeCheck.status!==0||derivativeBrowser.status===1)failed=true;
}
process.exitCode=failed?1:0;
