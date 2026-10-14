#!/usr/bin/env node
/**
 * 治理体检 —— **只读**
 *
 * 政策（2026-10-14 用户指示，覆盖此前的"群自治 / 方案 B"）：
 *   · 每群必须有管理员，且**应为 Chief**（他是群管理员兼最终责任人）
 *   · Chief 岗位卡：五段齐全 + 明确「对最终产物负责」+「不陪跑过程」
 *   · 执行负责人（项目经理）岗位卡：交付「可验收的产物包」、对外结论以 Chief 为准
 *   · 群公告：写明角色与责任、四要素升级、上下文纪律
 *
 * 用法：node check-governance.mjs [--home <DSH_HOME>] [--chief Chief] [--lead 项目经理]
 * 退出码：0 通过；1 有不合规项；2 读不到状态文件。
 */
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';

const pick = (flag, fallback) => {
  const i = process.argv.indexOf(flag);
  return i !== -1 && process.argv[i + 1] ? process.argv[i + 1] : fallback;
};

const home = path.resolve(pick('--home', process.env.DSH_HOME || path.join(os.homedir(), '.dsh')));
const chiefName = pick('--chief', 'Chief');
const leadName = pick('--lead', '项目经理');
const statePath = path.join(home, 'bot', 'state.json');

if (!fs.existsSync(statePath)) {
  console.error(`找不到团队状态文件：${statePath}\n用 --home <DSH_HOME> 指定。`);
  process.exit(2);
}
const S = JSON.parse(fs.readFileSync(statePath, 'utf8'));
const nameOf = (id) => S.bots?.[id]?.name ?? id ?? '(无)';
const botNamed = (n) => Object.values(S.bots ?? {}).find((b) => b.name === n);
const rooms = Object.values(S.rooms ?? {});
const problems = [];
const warnings = [];

console.log(`团队状态：${statePath}\n`);

console.log('=== 1. 群级：每群有管理员，且应为 Chief（最终责任人）===');
if (rooms.length === 0) console.log('  （没有群）');
let chiefAdminCount = 0;
for (const r of rooms) {
  const adminName = r.admin ? nameOf(r.admin) : '';
  if (adminName === chiefName) chiefAdminCount += 1;
  const wd = r.workDir ?? r.workdir ?? null;
  console.log(`  群「${r.name}」admin=${adminName || '(无)'} 成员=${(r.members ?? []).length} work_dir=${wd ?? '(未设)'}`);
  if (!r.admin) problems.push(`群「${r.name}」没有管理员`);
  else if (adminName !== chiefName) warnings.push(`群「${r.name}」的 admin 是 ${adminName}（当前政策应为本群管理员=${chiefName}；若为用户特意指定则忽略）`);
}
console.log(`  Chief 任管理员数 = ${chiefAdminCount}/${rooms.length}\n`);

console.log(`=== 2. Chief 岗位卡（${chiefName}）===`);
const chief = botNamed(chiefName);
const chiefIns = chief?.instructions ?? '';
if (!chief) {
  problems.push(`找不到名为 ${chiefName} 的 Bot`);
} else if (!chiefIns.trim()) {
  problems.push(`${chiefName} 未写入岗位卡（instructions 为空）`);
  console.log('  ✗ instructions 为空');
} else {
  for (const seg of ['# 身份', '# 职责', '# 边界', '# 汇报与升级', '# 记忆纪律']) {
    const ok = chiefIns.includes(seg);
    console.log(`  ${ok ? '✓' : '✗'} ${seg}`);
    if (!ok) problems.push(`${chiefName} 岗位卡缺段：${seg}`);
  }
  for (const [label, re] of [
    ['对最终产物负责', /最终责任人|对最终产物负责|对交付产物.{0,8}负责/],
    ['不陪跑过程', /不陪跑过程|不逐句参与|陪跑/],
    ['明确群管理员身份', /群管理员|管理员/],
  ]) {
    const ok = re.test(chiefIns);
    console.log(`  ${ok ? '✓' : '✗'} ${label}`);
    if (!ok) problems.push(`${chiefName} 岗位卡缺：${label}`);
  }
}
console.log('');

console.log(`=== 3. 执行负责人岗位卡（${leadName}）===`);
const lead = botNamed(leadName);
const li = lead?.instructions ?? '';
if (!lead) {
  problems.push(`找不到名为 ${leadName} 的 Bot`);
} else {
  for (const [label, re] of [
    ['执行负责人', /执行负责人/],
    ['交可验收的产物包', /可验收的产物包|产物包/],
    ['对外结论以 Chief 为准', /对外结论.{0,10}Chief|Chief 汇总为准/],
    ['四要素升级', /四要素|问题\s*\/\s*选项\s*\/\s*建议\s*\/\s*(时限|截止)/],
  ]) {
    const ok = re.test(li);
    console.log(`  ${ok ? '✓' : '✗'} ${label}`);
    if (!ok) problems.push(`执行负责人「${leadName}」岗位卡缺：${label}`);
  }
}
console.log('');

console.log('=== 4. 群公告：角色与责任 / 升级 / 上下文纪律 ===');
for (const r of rooms) {
  const notice = String(r.notice ?? '');
  console.log(`  群「${r.name}」公告 ${notice.length} 字`);
  for (const [label, re] of [
    ['角色与责任', /角色与责任|最终责任人/],
    ['四要素升级', /四要素|问题\s*\/\s*选项\s*\/\s*建议\s*\/\s*(时限|截止)/],
    ['上下文纪律', /上下文纪律|过程不留对话|work_dir/],
  ]) {
    const ok = re.test(notice);
    console.log(`    ${ok ? '✓' : '✗'} ${label}`);
    if (!ok) problems.push(`群「${r.name}」公告缺：${label}`);
  }
}

console.log(`\n结论：${problems.length === 0 ? '全部通过' : `${problems.length} 项不合规`}`);
for (const p of problems) console.log(`  → ${p}`);
for (const w of warnings) console.log(`  ⚠ ${w}`);
process.exit(problems.length === 0 ? 0 : 1);
