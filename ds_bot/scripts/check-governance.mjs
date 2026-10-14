#!/usr/bin/env node
/**
 * 上下文治理 / 方案 B（群自治）落地体检 —— **只读**
 *
 * 检查项（对应 07-上下文治理.md §8）：
 *   1. 群级：每群有 admin；admin 不是 Chief（方案 B：Chief 不当群管理员）；报告群 work_dir（插件 < v0.1.5 无此字段）
 *   2. Chief 岗位卡：五段齐全 + 明确「不进执行链路」
 *   3. 负责人（各群 admin）岗位卡：直接向用户汇报 + 四要素升级 + 不把进度塞给 Chief
 *   4. 群公告：含协作规则关键字（需求直达负责人 / 四要素 / 跨群）
 *
 * 用法：
 *   node check-governance.mjs [--home <DSH_HOME>] [--chief Chief]
 *   默认 home = $DSH_HOME，否则 ~/.dsh
 *
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

console.log(`团队状态：${statePath}\n`);

console.log('=== 1. 群级（负责人 = 群管理员）===');
if (rooms.length === 0) console.log('  （没有群）');
for (const r of rooms) {
  const adminName = r.admin ? nameOf(r.admin) : '';
  const members = (r.members ?? []).length;
  // work_dir 是插件 ≥ v0.1.5 的字段；v0.1.4 读不到属预期，不算失败
  const wd = r.workDir ?? r.workdir ?? null;
  console.log(`  群「${r.name}」admin=${adminName || '(无)'} 成员=${members} work_dir=${wd ?? '(插件不支持/未设)'}`);
  if (!r.admin) problems.push(`群「${r.name}」没有 admin（应指定负责人）`);
  if (adminName === chiefName) problems.push(`群「${r.name}」的 admin 是 ${chiefName}（方案 B 要求 Chief 不当群管理员）`);
}
console.log(`  Chief 任群管理员数 = ${rooms.filter((r) => nameOf(r.admin) === chiefName).length}（要求 0）\n`);

console.log('=== 2. Chief 岗位卡 ===');
const chief = botNamed(chiefName);
const chiefIns = chief?.instructions ?? '';
if (!chief) {
  problems.push(`找不到名为 ${chiefName} 的 Bot`);
  console.log('  ✗ 找不到该 Bot');
} else {
  if (!chiefIns.trim()) {
    console.log('  ⚠ 无自定义 instructions（身份来自插件内置 MAIN_RULES；方案 B 要求写入总师岗位卡）');
    problems.push(`${chiefName} 未写入总师岗位卡（instructions 为空）`);
  } else {
    for (const seg of ['# 身份', '# 职责', '# 边界', '# 汇报与升级', '# 记忆纪律']) {
      const ok = chiefIns.includes(seg);
      console.log(`  ${ok ? '✓' : '✗'} ${seg}`);
      if (!ok) problems.push(`${chiefName} 岗位卡缺段：${seg}`);
    }
    const noChain = /不进执行链路/.test(chiefIns);
    console.log(`  ${noChain ? '✓' : '✗'} 明确「不进执行链路」`);
    if (!noChain) problems.push(`${chiefName} 岗位卡未写明「不进执行链路」`);
    const noAdmin = /不当群管理员/.test(chiefIns);
    console.log(`  ${noAdmin ? '✓' : '✗'} 明确「不当群管理员」`);
    if (!noAdmin) problems.push(`${chiefName} 岗位卡未写明「不当群管理员」`);
  }
}
console.log('');

console.log('=== 3. 负责人岗位卡（各群 admin）===');
const leads = [...new Set(rooms.map((r) => r.admin).filter(Boolean))];
if (leads.length === 0) console.log('  （没有群管理员）');
for (const id of leads) {
  const b = S.bots?.[id];
  const ins = b?.instructions ?? '';
  const checks = [
    ['直接向用户汇报', /直接向用户汇报|直接对用户负责/],
    ['四要素升级', /四要素|问题\s*\/\s*选项\s*\/\s*建议\s*\/\s*(时限|截止)/],
    ['不把进度塞给 Chief', /不把.{0,8}进度.{0,8}(塞|转|交).{0,8}Chief|进度.{0,6}不进.{0,6}Chief|不转述/],
  ];
  console.log(`  负责人「${b?.name ?? id}」`);
  for (const [label, re] of checks) {
    const ok = re.test(ins);
    console.log(`    ${ok ? '✓' : '✗'} ${label}`);
    if (!ok) problems.push(`负责人「${b?.name ?? id}」岗位卡缺：${label}`);
  }
}
console.log('');

console.log('=== 4. 群公告协作规则 ===');
for (const r of rooms) {
  const notice = String(r.notice ?? '');
  const checks = [
    ['需求直达负责人', /需求直达负责人|需求.{0,10}直接.{0,10}负责人|负责人（群管理员）/],
    ['四要素', /四要素|问题\s*\/\s*选项\s*\/\s*建议\s*\/\s*(时限|截止)/],
    ['跨群协作/冲突升级', /跨群/],
  ];
  console.log(`  群「${r.name}」公告 ${notice.length} 字`);
  for (const [label, re] of checks) {
    const ok = re.test(notice);
    console.log(`    ${ok ? '✓' : '✗'} ${label}`);
    if (!ok) problems.push(`群「${r.name}」公告缺：${label}`);
  }
}

console.log(`\n结论：${problems.length === 0 ? '全部通过' : `${problems.length} 项不合规`}`);
for (const p of problems) console.log(`  → ${p}`);
process.exit(problems.length === 0 ? 0 : 1);
