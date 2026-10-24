/* ============================================================
   Soran 教材 · 搜索索引构建脚本
   用法：node tools/build-search-index.mjs
   扫描 pages/ 下全部章节页，提取 h2[data-sec] 小节标题与小节
   正文摘要，生成 assets/js/search-index.js（纯离线，file:// 可用）。
   新增/修改章节页后重新运行一次即可。
   ============================================================ */
import { readFileSync, writeFileSync, readdirSync, statSync } from 'fs';
import { join, dirname, relative } from 'path';
import { fileURLToPath } from 'url';

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..');
const PAGES_DIR = join(ROOT, 'pages');

/* ---------- 工具 ---------- */
function stripTags(html) {
  return html
    .replace(/<style[\s\S]*?<\/style>/gi, ' ')
    .replace(/<svg[\s\S]*?<\/svg>/gi, ' ')   // SVG 文字不进索引（figcaption 已含描述）
    .replace(/<script[\s\S]*?<\/script>/gi, ' ')
    .replace(/<[^>]+>/g, ' ')
    .replace(/&nbsp;/g, ' ')
    .replace(/&amp;/g, '&').replace(/&lt;/g, '<').replace(/&gt;/g, '>')
    .replace(/&quot;/g, '"').replace(/&#39;/g, "'")
    .replace(/\s+/g, ' ')
    .trim();
}

function walk(dir, out = []) {
  for (const name of readdirSync(dir)) {
    const p = join(dir, name);
    if (statSync(p).isDirectory()) walk(p, out);
    else if (name.endsWith('.html')) out.push(p);
  }
  return out;
}

/* ---------- 提取 ---------- */
const files = walk(PAGES_DIR).sort();
const index = [];

for (const file of files) {
  const html = readFileSync(file, 'utf8');
  const pageIdMatch = html.match(/data-page-id="([^"]+)"/);
  if (!pageIdMatch) continue;
  const pageId = pageIdMatch[1];

  const titleMatch = html.match(/<h1 class="page-title">([\s\S]*?)<\/h1>/);
  const title = stripTags(titleMatch ? titleMatch[1] : '').slice(0, 40);

  const pathAttr = 'pages/' + relative(PAGES_DIR, file).split('\\').join('/');

  /* 按 h2[data-sec] 切分正文 */
  const bodyMatch = html.match(/<div class="content">([\s\S]*?)<script/);
  if (!bodyMatch) continue;
  const body = bodyMatch[1];

  const secs = [];
  const h2Re = /<h2 class="sec-title"[^>]*data-sec="([^"]+)"[^>]*>([\s\S]*?)<\/h2>/g;
  let m, positions = [];
  while ((m = h2Re.exec(body))) positions.push({ anchor: m[1], titleHtml: m[2], start: m.index + m[0].length });

  for (let i = 0; i < positions.length; i++) {
    const end = i + 1 < positions.length
      ? body.indexOf('<h2 class="sec-title"', positions[i].start)
      : body.indexOf('<script', positions[i].start);
    const chunk = body.slice(positions[i].start, end > 0 ? end : undefined);
    const text = stripTags(chunk);
    const summary = text.length > 160 ? text.slice(0, 160) : text;
    secs.push({ t: stripTags(positions[i].titleHtml).replace(/^\d+/, '').trim(), s: summary, a: positions[i].anchor });
  }

  if (secs.length) index.push({ pageId, title, path: pathAttr, secs });
}

/* ---------- 输出 ---------- */
const banner =
  '/* ============================================================\n' +
  '   Soran 教材搜索索引（由 tools/build-search-index.mjs 生成）\n' +
  '   新增或修改章节页后重新运行：node tools/build-search-index.mjs\n' +
  '   ============================================================ */\n';
writeFileSync(join(ROOT, 'assets/js/search-index.js'),
  banner + 'window.SEARCH_INDEX = ' + JSON.stringify(index, null, 1) + ';\n', 'utf8');

const totalSecs = index.reduce((n, p) => n + p.secs.length, 0);
console.log('已生成 assets/js/search-index.js：' + index.length + ' 页 / ' + totalSecs + ' 个小节');
