const fs=require('fs'),path=require('path');
const {chromium}=require('C:/Program Files/WindowsApps/OpenAI.CodexPrimaryRuntime.v26-1105-1297-0_26.1105.1297.0_x64__3k8sg7r9htsxt/dependencies/node/node_modules/playwright');
(async()=>{
 const root=path.resolve(__dirname,'..'),src=path.join(root,'设计源稿'),out=path.join(root,'UI界面');
 const list=JSON.parse(fs.readFileSync(path.join(src,'ui_manifest.json'),'utf8'));
 const b=await chromium.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true});
 for(const p of list){let page=await b.newPage({viewport:{width:p.width,height:p.height},deviceScaleFactor:2});await page.goto('file:///'+path.join(src,p.name+'.svg').replaceAll('\\','/'));await page.screenshot({path:path.join(out,p.name+'.png')});await page.close();}
 await b.close();console.log('Rendered',list.length,'screens');
})();
