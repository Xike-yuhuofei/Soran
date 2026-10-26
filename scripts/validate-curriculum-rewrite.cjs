'use strict';
/* Evidence that first two chapters underwent substantive text rewriting
 * without losing navigation, glossary annotations, quizzes or illustration slots. */
const fs=require('node:fs');
const assert=require('node:assert/strict');
const pages=[
{path:'textbook/pages/guide.html',ids:['s-position','s-map','s-path','s-tools','s-method','s-link'],p:[3,1,4,1,4,1],quizzes:3,
 expected:['从“听到一个词”到“作出可验证的产品判断”','从原料走向消费者','整件克重不能直接等同']},
{path:'textbook/pages/basics/fundamentals.html',ids:['s-position','s-science','s-ergo','s-size','s-category','s-summary'],p:[7,8,7,6,3,0],quizzes:13,
 expected:['液态导湿','固定不变的胸部形状','还需结合','三层着装只是理解功能分工']},
];
const forbidden=[
 /日抛型消费品/,
 /汗液离开人体只有一条路径/,
 /不可逆的<\/b>/,
 /中间\s*60%\s*[–-]\s*70%\s*体型/,
 /吸湿速干是「吸收＋扩散」的达标认证/,
 /乳房无肌肉承托→/,
 /穿着系统中容错率最低的一层/,
];
for(const cfg of pages){
 const s=fs.readFileSync(cfg.path,'utf8');
 const parts=[...s.matchAll(/<h2 class="sec-title" id="([^"]+)" data-sec="([^"]+)"[^>]*>/g)];
 assert.deepEqual(parts.map(x=>x[1]),cfg.ids, cfg.path+' section order');
 for(let i=0;i<parts.length;i++){
  const slice=s.slice(parts[i].index,parts[i+1]?.index??s.indexOf('<script src=',parts[i].index));
  const pCount=[...slice.matchAll(/<p(?:\s[^>]*)?>[\s\S]*?<\/p>/g)].length;
  assert.equal(pCount,cfg.p[i],cfg.path+' paragraph count '+cfg.ids[i]);
 }
 for(const phrase of cfg.expected)assert.ok(s.includes(phrase),cfg.path+' rewritten concept missing '+phrase);
 for(const re of forbidden)assert.ok(!re.test(s),cfg.path+' outdated overclaim '+re);
 assert.equal([...s.matchAll(/<section class="quiz" data-quiz="([^"]+)"/g)].length,cfg.quizzes,cfg.path+' quiz preservation');
 assert.ok(s.includes('annotations.js')&&s.includes('glossary.js')&&s.includes('id="page-toc"'),cfg.path+' shared tooling');
 assert.ok(s.includes('data-v3-mode="basic"')&&s.includes('data-v3-mode="expert"'),cfg.path+' depth controls');
 assert.ok(!s.includes('.:scope{'),cfg.path+' invalid CSS');
 console.log('PASS substantive rewrite '+cfg.path+' / '+cfg.p.reduce((a,b)=>a+b,0)+' paragraphs');
}


/* Fabrics is substantively rewritten: text, decision examples and original tools must coexist. */
{
 const path='textbook/pages/basics/fabrics.html',html=fs.readFileSync(path,'utf8');
 const sec=[...html.matchAll(/<h2 class="sec-title" id="([^"]+)" data-sec="\1"[^>]*>/g)];
 const sectionIds=['s-knit','s-weft','s-warp','s-spec','s-dye','s-shade','s-finish','s-owner','s-sum'];
 const chunks=[...html.matchAll(/<h2 class="sec-title" id="(s-[^"]+)" data-sec="[^"]+"[^>]*>/g)];
 assert.deepEqual(chunks.map(x=>x[1]),sectionIds,path+' section order changed');
 const counts=[3,6,1,5,6,2,2,3,1];
 chunks.forEach((x,i)=>{
   const txt=html.slice(x.index,chunks[i+1]?.index??html.indexOf('<script src=',x.index));
   assert.equal([...txt.matchAll(/<p(?:\s[^>]*)?>[\s\S]*?<\/p>/g)].length,counts[i],path+' prose count '+x[1]);
   assert.ok(txt.includes('class="fabrics-judgement"'),path+' section missing practical task '+x[1]);
 });
 assert.equal((html.match(/class="fabrics-judgement"/g)||[]).length,9,path+' practical panels');
 assert.equal((html.match(/<figure\b/g)||[]).length,8,path+' diagrams');
 assert.equal((html.match(/<section class="quiz"/g)||[]).length,11,path+' 11 preserved questions');
 for(const phrase of ['GB/T 250-2008','GB/T 251-2008','机号不等于成品布','同样写“棉＋锦纶＋氨纶”','理论上每延米约有 0.304kg']) {
    assert.ok(html.includes(phrase),path+' missing verified concept '+phrase);
 }
 for(const phrase of ['经编家族：文胸面料的绝对主角','一台 28G 单面机永远','否则按一洗就没','缸间色差（如 &lt;4 级）']) {
    assert.ok(!html.includes(phrase),path+' obsolete text '+phrase);
 }
 console.log('PASS substantive rewrite '+path+' / 9 sections / 29 prose / 9 practice / 8 figures / 11 quizzes');
}
