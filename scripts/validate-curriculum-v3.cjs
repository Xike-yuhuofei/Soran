'use strict';
const fs=require('node:fs');
const vm=require('node:vm');
const files=[
'guide.html','basics/fundamentals.html','basics/fabrics.html','basics/quality.html','basics/supply.html',
'panties/design.html','panties/craft.html','socks/design.html','socks/craft.html',
'bras/materials.html','bras/design.html','bras/craft.html',
'sourcing/supplier.html','sourcing/judgment.html','appendix/standards.html','appendix/glossary.html'
];
const expected=[3,13,11,15,11,11,11,15,16,13,12,14,9,17,10,3];
const banned=[
/只(需|用|靠|能|要)/,/仅(需|是|为|限)/,/唯一/,/一定/,/必然/,/永远/,
 /全部/,/一律/,/任何/,/完全/,/无需/,/不用/,/不必/,/即可/,/立刻/,/马上/,
 /绝对/,/肯定/,/不可能/,/绝不/,/所有/,/均(可|需|为|按|属)/
];
const errors=[],summary=[];const totals=[0,0,0,0];
const check=(v,s)=>{if(!v)errors.push(s)};
for(const [i,p] of files.entries()){
 const file='textbook/pages/'+p,html=fs.readFileSync(file,'utf8');
 const quizzes=[...html.matchAll(/<section class="quiz"([^>]*?)>([\s\S]*?)<\/section>/g)];
 const heads=[...html.matchAll(/<h2 class="sec-title" id="([^"]+)" data-sec="([^"]+)"[^>]*>/g)];
 const cards=[...html.matchAll(/<div class="v3-section-guide"/g)];
 const responses=[...html.matchAll(/<section class="v3-storyboard"/g)];
 const positions=[0,0,0,0];const ids=new Set();
 check(html.includes('id="page-toc"'),file+' missing page toc');
 check(html.includes('annotations.js'),file+' missing notes');
 check(html.includes('v3-curriculum') && /<body data-v3-curriculum/.test(html),file+' missing beginner layout');
 check(responses.length===1,file+' storyboard duplication/missing');
 check(cards.length===heads.length,file+' guided section count mismatch');
 check(heads.length>=2,file+' sections missing');
 check(heads.every(x=>x[1]===x[2]),file+' section IDs differ');
 check(!html.includes('.:scope{'),file+' invalid CSS .:scope');
 check(html.includes('max-width:1130px')&&html.includes('max-width:820px'),file+' reading width missing');
 check(html.includes('data-v3-mode="basic"')&&html.includes('data-v3-mode="expert"'),file+' beginner/expert mode missing');
 check((html.match(/class="v3-practice-grid"/g)||[]).length===1,file+' missing practice cards');
 check(quizzes.length===expected[i],file+' changed original quiz count '+quizzes.length+' expected '+expected[i]);
 for(const [n,q] of quizzes.entries()){
  const id=q[1].match(/data-quiz="([^"]+)"/)?.[1];
  const ans=Number(q[1].match(/data-a="(\d)"/)?.[1]);
  const opts=[...q[2].matchAll(/<li>([\s\S]*?)<\/li>/g)].map(m=>m[1].replace(/<[^>]*>/g,'').trim());
  check(id && !ids.has(id),file+' duplicate quiz ID '+id);ids.add(id);
  check(opts.length===4,file+' quiz '+n+' missing four options');
  check(ans>=0&&ans<=3,file+' quiz '+n+' invalid correct index');
  if(ans>=0&&ans<4){positions[ans]++;totals[ans]++;}
  if(opts.length===4){
   const sizes=opts.map(x=>x.replace(/[，。；：、！？（）()「」“”《》\s]/g,'').length);
   check(Math.min(...sizes)>0&&Math.max(...sizes)/Math.min(...sizes)<=1.15,file+' quiz '+n+' option length leakage '+sizes);
   for(const [idx,opt] of opts.entries()){
    for(const re of banned) check(!re.test(opt),file+' quiz '+n+' '+idx+' banned '+re);
    check(!/以上都对|以上都不对|视情况而定/.test(opt),file+' quiz '+n+' invalid distractor');
   }
  }
 }
 for(const m of html.matchAll(/<script(?:\s+[^>]*)?>([\s\S]*?)<\/script>/g)){
  if(!m[1].trim())continue;
  try{new vm.Script(m[1],{filename:file});}catch(e){errors.push(file+' inline JS '+e.message);}
 }
 summary.push({file,sections:heads.length,quizzes:quizzes.length,positions});
}
check(summary.reduce((n,x)=>n+x.quizzes,0)===184,'question total differs 184');
check(Math.max(...totals)-Math.min(...totals)<=6,'global answer distribution not balanced: '+totals);
if(errors.length){console.error(errors.join('\n'));process.exit(1);}
console.log('PASS curriculum V3 16/16 pages, sections, script syntax and 184 quizzes');
console.log('Overall correct answer distribution A/B/C/D:',totals.join('/'));
summary.forEach(x=>console.log(x.file+' sections='+x.sections+' quizzes='+x.quizzes+' positions='+x.positions.join('/')));
