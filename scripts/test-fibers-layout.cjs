'use strict';
/**
 * 对真实教材集成页执行 Chromium 排版回归，并输出可复查的截图。
 * 无需外网：Node 静态服务器从本地 textbook/ 提供资源。
 */
const fs = require('node:fs');
const http = require('node:http');
const path = require('node:path');
const assert = require('node:assert/strict');
const { chromium } = require('playwright');

const root = path.resolve(__dirname, '../textbook');
const outDir = path.resolve(__dirname, '../artifacts/fibers-layout');
const mime = { '.html':'text/html; charset=utf-8', '.css':'text/css; charset=utf-8', '.js':'application/javascript; charset=utf-8',
  '.svg':'image/svg+xml', '.png':'image/png', '.jpg':'image/jpeg', '.json':'application/json' };
fs.mkdirSync(outDir, { recursive:true });
const server = http.createServer((req, res) => {
  let requested;
  try { requested = decodeURIComponent(new URL(req.url, 'http://127.0.0.1').pathname); }
  catch (_) { res.writeHead(400).end(); return; }
  const file = path.resolve(root, '.' + requested);
  if (file !== root && !file.startsWith(root + path.sep)) {res.writeHead(403).end();return;}
  fs.readFile(file,(err,buf)=>{
    if(err){res.writeHead(404).end('not found');return;}
    res.writeHead(200,{'Content-Type':mime[path.extname(file)]||'application/octet-stream'});
    res.end(buf);
  });
});

(async()=>{
  await new Promise(resolve => server.listen(0,'127.0.0.1',resolve));
  const port = server.address().port;
  const browser = await chromium.launch({headless:true});
  try {
    for (const width of [390,768,1024,1440,1920]) {
      const page = await browser.newPage({viewport:{width,height:900},deviceScaleFactor:1});
      const pageErrors = [];
      page.on('pageerror',e=>pageErrors.push(e.message));
      await page.goto('http://127.0.0.1:'+port+'/pages/basics/fibers.html',{waitUntil:'domcontentloaded'});
      await page.locator('#soran-v3-root > main.body').waitFor();
      const metric=await page.evaluate(()=>{
        const el=document.querySelector('#soran-v3-root > main.body');
        const computed=getComputedStyle(el), rect=el.getBoundingClientRect();
        const prose=document.querySelector('#soran-v3-root .chapter > .chapter-sub');
        return {
          viewport:window.innerWidth,
          scrollWidth:document.documentElement.scrollWidth,
          bodyWidth:rect.width,
          bodyLeft:rect.left,
          bodyRight:window.innerWidth-rect.right,
          paddingLeft:parseFloat(computed.paddingLeft),
          paddingRight:parseFloat(computed.paddingRight),
          proseWidth:prose?.getBoundingClientRect().width??0,
          fontSize:computed.fontSize
        };
      });
      const expectedPad=width<=600?18:width<=890?28:width<=1200?32:52;
      assert.ok(metric.paddingLeft>=expectedPad-1 && metric.paddingRight>=expectedPad-1,
        '边距不足 '+width+'px: '+JSON.stringify(metric));
      assert.ok(metric.bodyWidth <= 1131,'版心过宽 '+width+'px: '+JSON.stringify(metric));
      assert.ok(metric.scrollWidth <= width+2,'页面横向溢出 '+width+'px: '+JSON.stringify(metric));
      assert.ok(metric.proseWidth > 0 && metric.proseWidth<=821,'正文行宽异常 '+width+'px: '+JSON.stringify(metric));
      assert.deepEqual(pageErrors,[],'浏览器脚本异常 '+width+'px: '+pageErrors.join('; '));
      await page.screenshot({path:path.join(outDir,'fibers-'+width+'.png'),fullPage:false});
      // 取一张中部章节截图，避免回归只检查首屏。
      if(width===390||width===1440){
        await page.locator('#s-natural').scrollIntoViewIfNeeded();
        await page.screenshot({path:path.join(outDir,'fibers-chapter-'+width+'.png'),fullPage:false});
      }
      process.stdout.write('PASS layout '+width+'px '+JSON.stringify(metric)+'\n');
      await page.close();
    }
  } finally {await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1}).finally(()=>server.close());
