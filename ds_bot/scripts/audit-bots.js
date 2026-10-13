#!/usr/bin/env node
/**
 * DS Bot 团队合规体检
 *
 * 读 DS Bot 插件的权威状态（<DSH_HOME>/bot/state.json）与记忆目录，逐个体检：
 * 角色/名称长度、instructions 的五段完整性、项目事实泄漏、模型分布、群成员、记忆 topic 落位。
 *
 * 用法：
 *   node audit-bots.js [--home <DSH_HOME>] [--json <out.json>]
 *   默认 home = $DSH_HOME，否则 ~/.dsh
 *
 * 退出码：0 全部通过；1 存在不合规项（Main Bot 允许没有自定义 instructions）；2 读不到状态文件。
 */
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');

const pick = (flag, fallback) => {
  const i = process.argv.indexOf(flag);
  return i !== -1 && process.argv[i + 1] ? process.argv[i + 1] : fallback;
};

const home = path.resolve(pick('--home', process.env.DSH_HOME || path.join(os.homedir(), '.dsh')));
const botDir = path.join(home, 'bot');
const statePath = path.join(botDir, 'state.json');
const memoryDir = path.join(botDir, 'memory');
const jsonOut = pick('--json', '');

if (!fs.existsSync(statePath)) {
  console.error(`找不到团队状态文件：${statePath}`);
  console.error('用 --home <DSH_HOME> 指定；或确认 DS Bot 插件已在本机使用过。');
  process.exit(2);
}
const state = JSON.parse(fs.readFileSync(statePath, 'utf8'));

// 岗位卡里不该出现的项目事实。按需增删；这些是"例子"，不是穷举。
const LEAK = [
  ['绝对路径', /(^|[^\w])[A-Za-z]:[\\/]/m],
  ['项目目录名', /(^|[^\w])(validation|scripts|reqs|snapshots|deliverables|立项资料)([\\/]|$)/m],
  ['数据源/编排器专名', /(iFinD|同花顺|AKShare|BaoStock|gmtrade|gm\.api|OpenClaw|Hermes)/],
  ['验收编号', /\b(VP|vp)-\d{2}\b/],
  ['虚拟环境', /\.venv/],
  ['测试基线数字', /(\d{2,5}\s*项测试|\b[23]\d{2}\b\s*项)/],
];

const SEGMENTS = {
  加载协议: /项目加载协议/,
  职责: /(职责|通用手艺|调研方法)/,
  边界: /(边界|禁止)/,
  汇报: /汇报/,
  硬约束: /(硬约束|只追加)/,
};

const bots = Object.values(state.bots || {});
const mainIds = state.mainBotIds || [];
const maxtName = 40;
const maxRole = 24;

const rows = bots.map((b) => {
  const ins = String(b.instructions ?? '');
  const leaks = LEAK.filter(([, re]) => re.test(ins)).map(([name]) => name);
  const seg = Object.fromEntries(Object.entries(SEGMENTS).map(([k, re]) => [k, re.test(ins)]));
  const isMain = mainIds.includes(b.id);
  const problems = [];
  if ([...String(b.name ?? '')].length > maxtName) problems.push(`name 超过 ${maxtName} 字符`);
  if ([...String(b.role ?? '')].length > maxRole) problems.push(`role 超过 ${maxRole} 字符`);
  if (leaks.length > 0) problems.push(`instructions 泄漏项目事实：${leaks.join('、')}`);
  if (!isMain && !seg.加载协议) problems.push('缺少标准「项目加载协议」段');
  if (!isMain && ins.trim() === '') problems.push('自定义岗位却没有 instructions');
  return {
    name: b.name,
    role: b.role ?? '',
    model: b.model?.model ?? b.model ?? '(未设置)',
    isMain,
    insLen: ins.length,
    seg,
    leaks,
    problems,
  };
}).sort((a, b) => String(a.name).localeCompare(String(b.name), 'zh'));

const rooms = Object.values(state.rooms || {}).map((r) => ({
  name: r.name,
  mode: r.mode,
  admin: (state.bots[r.admin]?.name) ?? r.admin ?? null,
  members: (r.members || []).map((id) => state.bots[id]?.name ?? id),
  noticeLen: String(r.notice ?? '').length,
}));

const byModel = {};
for (const r of rows) byModel[r.model] = (byModel[r.model] || 0) + 1;

const memory = { bots: [], team: [] };
try {
  const botsMem = path.join(memoryDir, 'bots');
  if (fs.existsSync(botsMem)) {
    for (const id of fs.readdirSync(botsMem)) {
      const files = fs.readdirSync(path.join(botsMem, id));
      memory.bots.push({ bot: state.bots[id]?.name ?? id, files });
    }
  }
  const teamMem = path.join(memoryDir, 'team');
  if (fs.existsSync(teamMem)) memory.team = fs.readdirSync(teamMem);
} catch { /* 记忆目录缺失不是错误 */ }

const failing = rows.filter((r) => r.problems.length > 0);

console.log(`团队状态：${statePath}`);
console.log(`Bot ${rows.length} 个 · 群 ${rooms.length} 个 · Main Bot ${mainIds.length} 个\n`);
for (const r of rows) {
  const mark = r.problems.length === 0 ? '✅' : '❌';
  const seg = Object.entries(r.seg).filter(([, v]) => v).map(([k]) => k).join('/') || '—';
  console.log(`${mark} ${r.name}  [${r.role}]  ${r.model}  ins=${r.insLen}  段=${seg}`);
  for (const p of r.problems) console.log(`     ↳ ${p}`);
}
console.log('\n模型分布：' + JSON.stringify(byModel));
for (const r of rooms) console.log(`群「${r.name}」mode=${r.mode} admin=${r.admin} 成员=${r.members.length} 公告=${r.noticeLen}字`);
if (memory.bots.length || memory.team.length) {
  console.log(`记忆：${memory.bots.length} 个 Bot 有私有记忆；团队记忆文件 ${memory.team.join(', ') || '(无)'}`);
} else {
  console.log('记忆：尚未产生（记忆目录为空）');
}
console.log(`\n结论：${failing.length === 0 ? '全部通过' : `${failing.length} 个不合规 → ${failing.map((r) => r.name).join('、')}`}`);

if (jsonOut) {
  fs.writeFileSync(jsonOut, JSON.stringify({ home, botCount: rows.length, byModel, rooms, memory, bots: rows }, null, 2));
  console.log(`原始结果：${jsonOut}`);
}
process.exit(failing.length === 0 ? 0 : 1);
