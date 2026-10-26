'use strict';
const fs=require('node:fs'),http=require('node:http'),path=require('node:path'),assert=require('node:assert/strict');
const {chromium}=require('playwright');
const root=path.resolve(__dirname,'../textbook'),out=path.resolve(__dirname,'../artifacts/curriculum-v3');
fs.mkdirSync(out,{recursive:true});
const paths=['guide.html','basics/fundamentals.html','basics/fabrics.html','basics/quality.html','basics/supply.html','panties/design.html','panties/craft.html','socks/design.html','socks/craft.html','bras/materials.html','bras/design.html','bras/craft.html','sourcing/supplier.html','sourcing/judgment.html','appendix/standards.html','appendix/glossary.html'];
const mime={'.html':'text/html;charset=utf-8','.css':'text/css;charset=utf-8','.js':'application/javascript;charset=utf-8','.json':'application/json'};
const server=http.createServer((req,res)=>{
 let reqPath;try{reqPath=decodeURIComponent(new URL(req.url,'http://local').pathname);}catch{res.writeHead(400).end();return;}
 const file=path.resolve(root,'.'+reqPath);
 if(file!==root&&!file.startsWith(root+path.sep)){res.writeHead(403).end();return;}
 fs.readFile(file,(err,buf)=>{if(err){res.writeHead(404).end('not found');return;}
 res.writeHead(200,{'Content-Type':mime[path.extname(file)]||'application/octet-stream'});res.end(buf);});
});
(async()=>{
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
 const port=server.address().port,browser=await chromium.launch({headless:true});
 try{
   let tested=0;
   for(const [i,p] of paths.entries()){
     const widths=i===0?[390,768,1024,1440,1920]:[390,1440];
     for(const width of widths){
       const page=await browser.newPage({viewport:{width,height:900}});
       const errors=[];page.on('pageerror',e=>errors.push(e.message));
       await page.goto('http://127.0.0.1:'+port+'/pages/'+p,{waitUntil:'domcontentloaded'});
       await page.locator('.v3-storyboard').waitFor({timeout:12000});
       const metric=await page.evaluate(()=>{
         const root=document.querySelector('.content.v3-curriculum');
         const rect=root.getBoundingClientRect(),style=getComputedStyle(root);
         return {viewport:window.innerWidth,scroll:document.documentElement.scrollWidth,
           body:rect.width,padding:parseFloat(style.paddingLeft),guide:document.querySelectorAll('.v3-section-guide').length,
           modes:document.querySelectorAll('.v3-switch button').length};
       });
       const expectPad=width<=680?18:width<=890?28:width<=1200?32:52;
       assert.ok(metric.padding>=expectPad-1,p+' no left margin '+width+' '+JSON.stringify(metric));
       assert.ok(metric.body<=1131,p+' wide body '+width+' '+JSON.stringify(metric));
       if(metric.scroll>width+2){
        const offenders=await page.evaluate(()=>[...document.querySelectorAll('*')].map(el=>({tag:el.tagName.toLowerCase(),id:el.id,cls:typeof el.className==='string'?el.className.slice(0,90):'',rect:el.getBoundingClientRect().toJSON(),scrollWidth:el.scrollWidth}))
          .filter(x=>x.rect.right>innerWidth+2&&x.rect.width>0).sort((a,b)=>b.rect.right-a.rect.right).slice(0,12));
        console.error('OVERFLOW DIAGNOSTIC '+p+' '+width+' '+JSON.stringify(offenders));
        await page.screenshot({path:path.join(out,'overflow-'+p.replace('/','-')+'-'+width+'.png'),fullPage:false});
      }
      assert.ok(metric.scroll<=width+2,p+' horizontal overflow '+width+' '+JSON.stringify(metric));
       assert.ok(metric.guide>=2,p+' section guides missing '+width);
       assert.equal(metric.modes,2,p+' missing mode controls');
       await page.locator('button[data-v3-mode="expert"]').click();
       assert.equal(await page.locator('.v3-storyboard').getAttribute('data-mode'),'expert');
       await page.locator('button[data-v3-mode="basic"]').click();
       assert.equal(await page.locator('.v3-storyboard').getAttribute('data-mode'),'basic');
       await page.locator('.v3-practice-grid details').first().locator('summary').click();
       assert.ok(await page.locator('.v3-practice-grid details').first().evaluate(el=>el.open),p+' answer reveal');
       assert.deepEqual(errors,[],p+' JS errors '+errors.join(';'));
       if(width===390 || (width===1440 && [0,2,5,9,12,15].includes(i)))
         await page.screenshot({path:path.join(out,p.replace('/','-').replace('.html','')+'-'+width+'.png'),fullPage:false});
       console.log('PASS '+p+' '+width+'px '+JSON.stringify(metric));tested++;
       await page.close();
     }
   }
   console.log('ALL PASS browser layout '+tested+' viewport checks');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;}).finally(()=>server.close());
