'use strict';
const fs = require('node:fs');
const vm = require('node:vm');
const file = 'textbook/pages/basics/fibers.html';
const html = fs.readFileSync(file, 'utf8');
const errors = [];
const warn = [];
const assert = (condition, message) => { if (!condition) errors.push(message); };
const attr = (source,name) => { const m=source.match(new RegExp('data-'+name+'="([^"]*)"'));return m?m[1]:null; };
const decode = s => s.replace(/&quot;/g,'"').replace(/&lt;/g,'<').replace(/&gt;/g,'>').replace(/&amp;/g,'&');
const banned = [
 /只(需|用|靠|能|要)/,/仅(需|是|为|限)/,/唯一/,/一定/,/必然/,/永远/,/全部/,/一律/,/任何/,
 /完全/,/无需/,/不用/,/不必/,/即可/,/立刻/,/马上/,/绝对/,/肯定/,/不可能/,/绝不/,/所有/,/均(可|需|为|按|属)/
];
const raw = [...html.matchAll(/<section class="quiz"([^>]*?)>([\s\S]*?)<\/section>/g)];
assert(raw.length === 18, '原生题库必须恰好18道，实际 '+raw.length);
const ids = new Set();
const counts=[0,0,0,0], data=[];
for (let i=0;i<raw.length;i++) {
 const attrs=raw[i][1], body=raw[i][2];
 const id=attr(attrs,'quiz'), kp=attr(attrs,'kp'), level=attr(attrs,'level'), q=decode(attr(attrs,'q')||''), exp=decode(attr(attrs,'exp')||'');
 const answer=Number(attr(attrs,'a'));
 const opts=[...body.matchAll(/<li>([\s\S]*?)<\/li>/g)].map(m=>decode(m[1].replace(/<[^>]+>/g,'').trim()));
 assert(id==='basics-fibers-q'+(i+1),'题号或排序错误: '+id);
 assert(!ids.has(id),'重复题号: '+id); ids.add(id);
 assert(kp&&level&&/^L[1-5]$/.test(level),'缺少知识点/认知层级: '+id);
 assert(q&&opts.length===4,'题干/选项不完整: '+id);
 assert(Number.isInteger(answer)&&answer>=0&&answer<=3,'答案索引异常: '+id);
 if(answer>=0&&answer<=3)counts[answer]++;
 if(opts.length===4){
  const sizes=opts.map(x=>x.replace(/[，。；：、！？（）()「」“”《》\s]/g,'').length);
  assert(Math.min(...sizes)>0 && Math.max(...sizes)/Math.min(...sizes)<=1.15,'选项长度失衡 '+id+' '+sizes);
  for (let j=0;j<4;j++)for(const regex of banned)assert(!regex.test(opts[j]),'泄题词 '+id+' '+String.fromCharCode(65+j)+' '+regex);
  assert(!opts.some(x=>/以上都对|以上都不对|视情况而定/.test(x)),'无效干扰项 '+id);
  for (const letter of ['A','B','C','D'])assert(exp.includes(letter+'：'),'解析未逐项说明 '+id+' '+letter);
  assert(!/因为.{1,35}所以|由于.{1,35}导致/.test(opts[answer]||''),'正确项包含推理链 '+id);
 }
 data.push({q,opts,answer});
}
assert(Math.max(...counts)-Math.min(...counts)<=1,'正确答案位置失衡 '+counts);
for(const id of ['s-map','s-natural','s-regen','s-synth','s-table','s-yarn','s-label','s-lab','s-summary'])
 assert((html.match(new RegExp('data-sec="'+id+'"','g'))||[]).length===1,'章节锚点不唯一 '+id);
for(const token of ['id="soran-v3-root"','id="fiber-v2-template"','id="quiz-reset"','annotations.js','window.__SORAN_PAGE_INIT__','id="legacy-s-summary"'])
 assert(html.includes(token),'教材兼容功能缺失 '+token);
const qmatch=html.match(/const questions=(\[[\s\S]*?\]);\s*let group=0/);
assert(!!qmatch,'互动题库 JSON 缺失');
if(qmatch){
 try{
  const groups=JSON.parse(qmatch[1]),visible=groups.flat();
  assert(groups.length===3&&groups.every(g=>g.length===6),'互动题库分组不为3×6');
  for(let i=0;i<Math.min(18,visible.length);i++){
   assert(visible[i].c===data[i].answer,'互动与原生答案不一致 '+(i+1));
   assert(visible[i].q===data[i].q,'互动与原生题干不一致 '+(i+1));
   assert(JSON.stringify(visible[i].a)===JSON.stringify(data[i].opts),'互动与原生选项不一致 '+(i+1));
  }
 }catch(e){errors.push('互动题库 JSON 解析错误 '+e.message);}
}
for (const m of html.matchAll(/<script(?:\s+[^>]*)?>([\s\S]*?)<\/script>/g)){
 if(!m[1].trim())continue;
 try{new vm.Script(m[1],{filename:file});}catch(e){errors.push('页面 JS 语法错误: '+e.message);}
}
if(warn.length)console.warn(warn.join('\n'));
if(errors.length){console.error('纤维 V3 质量门禁失败 ('+errors.length+')\n'+errors.join('\n'));process.exit(1);}
console.log('PASS V3: '+raw.length+' questions, answer distribution '+counts.join('/'));
console.log('PASS: 4 options, length <= 1.15, banned-word checks, explanations, parity, chapter anchors and inline JS syntax');
