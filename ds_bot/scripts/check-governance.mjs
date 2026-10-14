#!/usr/bin/env node
// 上下文治理落地体检（对应 07-上下文治理.md §8 体检项）
// 只读 state.json，不写任何东西。用法: node tools/check-governance.mjs
import fs from 'node:fs';
const S = JSON.parse(fs.readFileSync('/root/.dsh/bot/state.json', 'utf8'));
const nameOf = (id) => S.bots[id]?.name ?? id;
const rooms = Object.values(S.rooms ?? {});
const problems = [];

console.log('=== 群级检查 ===');
for (const r of rooms) {
  const admin = nameOf(r.admin);
  const chiefIsAdmin = admin === 'Chief';
  const hasAdmin = !!r.admin;
  const wd = r.workDir ?? r.workdir ?? null;
  console.log(`  群「${r.name}」admin=${admin || '(无)'} work_dir=${wd || '(未设)'}`);
  if (chiefIsAdmin) problems.push(`群「${r.name}」的 admin 是 Chief（方案 B 要求 Chief 不做群管理员）`);
  if (!hasAdmin) problems.push(`群「${r.name}」没有 admin（应指定负责人）`);
  if (!wd) problems.push(`群「${r.name}」未设 work_dir（应指向项目目录）`);
}
console.log(`  群 admin 合规：Chief 任群管理员数 = ${rooms.filter(r => nameOf(r.admin) === 'Chief').length}（要求 0）`);

console.log('\n=== Chief 岗位卡检查（§7 五段）===');
const chief = Object.values(S.bots ?? {}).find(b => b.name === 'Chief');
const ins = chief?.instructions ?? '';
for (const seg of ['# 身份', '# 职责', '# 边界', '# 汇报与升级', '# 记忆纪律']) {
  const ok = ins.includes(seg);
  console.log(`  ${ok ? '✅' : '⚠ '} ${seg}`);
  if (!ok) problems.push(`Chief 岗位卡缺段：${seg}`);
}
const noDispatch = /不接任务派工|不进执行链路/.test(ins);
console.log(`  ${noDispatch ? '✅' : '⚠ '} 明确"不进执行链路"`);
if (!noDispatch) problems.push('Chief 岗位卡未写明"不进执行链路"');

console.log('\n=== 负责人岗位卡检查（研发组长）===');
const lead = Object.values(S.bots ?? {}).find(b => b.name === '研发组长');
const li = lead?.instructions ?? '';
for (const [k, re] of [['四要素升级', /问题\s*\/\s*选项\s*\/\s*建议\s*\/\s*时限|四要素/], ['直接向用户汇报', /直接向用户汇报|直接对用户负责/], ['不塞给 Chief 转达', /不把.{0,6}进度.{0,6}(塞|交)给\s*Chief|不把进度塞给/]]) {
  const ok = re.test(li);
  console.log(`  ${ok ? '✅' : '⚠ '} ${k}`);
  if (!ok) problems.push(`研发组长岗位卡缺：${k}`);
}

console.log('\n结论：' + (problems.length ? `${problems.length} 项不合规` : '全部通过'));
for (const p of problems) console.log('  ↳ ' + p);
process.exit(problems.length ? 1 : 0);
