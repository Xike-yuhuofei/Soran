import fs from 'node:fs';
import path from 'node:path';
const root = 'brand/product-management';
const required = [
  "README.md",
  ".gitignore",
  "00｜管理规范与模板/产品开发SOP.md",
  "00｜管理规范与模板/文件命名与编号规则.md",
  "00｜管理规范与模板/模板/单品立项书.md",
  "00｜管理规范与模板/模板/供应商询价单.md",
  "00｜管理规范与模板/模板/供应商报价比选.csv",
  "00｜管理规范与模板/模板/样品评审记录.csv",
  "00｜管理规范与模板/模板/变更记录.csv",
  "00｜管理规范与模板/模板/产品规格确认书.md",
  "00｜管理规范与模板/模板/采购与验收清单.md",
  "00｜管理规范与模板/模板/产品复盘.md",
  "01｜产品规划/README.md",
  "01｜产品规划/SORAN 产品矩阵总表.csv",
  "01｜产品规划/市场与竞品研究.csv",
  "01｜产品规划/年度产品路线规划.csv",
  "02｜单品开发/README.md",
  "02｜单品开发/女士内裤/README.md",
  "02｜单品开发/男士内裤/README.md",
  "02｜单品开发/袜子/README.md",
  "02｜单品开发/文胸/README.md",
  "02｜单品开发/其他品类/README.md",
  "03｜供应商管理/README.md",
  "03｜供应商管理/供应商档案总表.csv",
  "03｜供应商管理/供应商档案模板.md",
  "04｜采购与质量管理/README.md",
  "04｜采购与质量管理/采购订单台账.csv",
  "04｜采购与质量管理/质量异常与售后追踪.csv",
  "04｜采购与质量管理/采购订单与合同/README.md",
  "04｜采购与质量管理/检验与验收记录/README.md",
  "05｜产品复盘/README.md",
  "05｜产品复盘/产品上市表现.csv",
  "05｜产品复盘/消费者反馈与改进记录.csv"
];
let issues = [];
for (const name of required) {
  const full = path.join(root, name);
  if (!fs.existsSync(full)) { issues.push('Missing: '+name); continue; }
  const text = fs.readFileSync(full, 'utf8');
  if (!text.trim()) issues.push('Empty: '+name);
  if (name.endsWith('.csv')) {
    const h = text.replace(/^\uFEFF/, '').split(/\r?\n/,1)[0];
    const columns = h.split(',').map(s=>s.trim().replace(/^"|"$/g,''));
    if (columns.length < 5 || new Set(columns).size !== columns.length || columns.some(c=>!c)) issues.push('Bad CSV header: '+name);
  }
}
if (issues.length) { console.error(issues.join('\n')); process.exit(1); }
console.log('SORAN product-management templates validated: '+required.length+' files');
