// req-mgmt 技能完整性校验脚本
// 运行: node <req-mgmt>/scripts/validate.js
// 校验: 技能自身所有产物文件存在、非空、含关键内容。退出码 0=通过, 1=失败。
// 说明: 本脚本校验的是 req-mgmt 技能目录自身（与 Skill 所在位置无关），
//       可在任意 clone 位置运行，不依赖绝对路径。
const fs = require('fs');
const path = require('path');

// skillRoot = req-mgmt 技能根目录（scripts 的上一级）
const skillRoot = path.resolve(__dirname, '..');

const files = [
  ['SKILL.md', ['name: req-mgmt', '多需求切换', '开发前对齐', '只追加，不覆盖']],
  ['examples/README.md', ['在隔离临时 git 仓库实测通过']],
  ['templates/REQS-INDEX.md', ['需求索引']],
  ['templates/reqs/0001-slug/REQS.md', ['变更记录（只追加，禁止覆盖）']],
  ['templates/reqs/0001-slug/TODO.md', ['## 阶段 1']],
  ['templates/reqs/0001-slug/DONE.md', ['完成日志']],
];

let pass = true;
for (const [rel, must] of files) {
  const full = path.join(skillRoot, rel);
  if (!fs.existsSync(full)) { console.log('MISSING: ' + rel); pass = false; continue; }
  const content = fs.readFileSync(full, 'utf8');
  if (!content.trim()) { console.log('EMPTY: ' + rel); pass = false; continue; }
  for (const m of must) {
    if (!content.includes(m)) { console.log('MISSING CONTENT [' + m + '] in ' + rel); pass = false; }
  }
  console.log('OK: ' + rel + ' (' + content.length + ' bytes)');
}
console.log(pass ? '\nALL CHECKS PASSED' : '\nCHECKS FAILED');
process.exit(pass ? 0 : 1);
