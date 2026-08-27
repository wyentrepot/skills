// req-mgmt DECISIONS.md 归档重启脚本
// 规则（DECISIONS.md #5 / SKILL.md 流程 G）：
//   - ADR 记录（### #N 条目，含已被取代的）累计达到 LIMIT=10 条时触发归档重启。
//   - 归档：当前 DECISIONS.md 整份移入 archives/DECISIONS-YYYYMMDD-HHmm.md（全量历史保留）。
//   - 重启（3 缓存 + 7 新增，防失忆）：新文件复制当前文件的末尾 3 条（#8/#9/#10）
//     依次重排为新文件的 #1/#2/#3，之后新增从 #4 起；每个生命周期 = 3 条缓存 + 最多 7 条新增。
//
// 用法:
//   node archive.js            # dry-run：打印当前条数与是否需归档（不改文件）
//   node archive.js --apply    # 实际执行归档重启（当前条数 >= 10 才动）
// 退出码: 0=成功/无需归档, 1=失败（如未达上限时用 --apply）
const fs = require('fs');
const path = require('path');

const LIMIT = 10;
const CACHE = 3;
const skillRoot = path.resolve(__dirname, '..');
const decisionsPath = path.join(skillRoot, 'DECISIONS.md');
const archivesDir = path.join(skillRoot, 'archives');

function pad(n) { return String(n).padStart(2, '0'); }
function timestamp() {
  const d = new Date();
  return `${d.getFullYear()}${pad(d.getMonth() + 1)}${pad(d.getDate())}-${pad(d.getHours())}${pad(d.getMinutes())}`;
}

// 解析 DECISIONS.md 中全部 ### #N 记录块
function parseRecords(content) {
  const lines = content.split(/\r?\n/);
  const records = [];
  let cur = null;
  for (const line of lines) {
    const m = line.match(/^###\s+#(\d+)\s+(.*)$/);
    if (m) {
      if (cur) records.push(cur);
      cur = { num: parseInt(m[1], 10), title: m[2].trim(), lines: [line] };
    } else if (cur) {
      cur.lines.push(line);
    }
  }
  if (cur) records.push(cur);
  return records;
}

// 从记录行中提取单个字段（日期）
function fieldValue(record, key) {
  const prefix = `- **${key}**:`;
  const line = record.lines.find((l) => l.includes(prefix));
  return line ? line.split(prefix)[1].trim() : '';
}

function readOrFail() {
  if (!fs.existsSync(decisionsPath)) {
    console.error('MISSING: ' + decisionsPath);
    process.exit(1);
  }
  return fs.readFileSync(decisionsPath, 'utf8');
}

function headerBlock() {
  return `# DECISIONS.md — 需求/进度管理技能（req-mgmt）

> 本文件遵循「决策只追加、不覆盖」的 ADR 模式（见 AGENTS.md）。已有记录永不修改；新决策取代旧记录时，只在活动决策表把旧记录状态改为「❌ 已取代」，正文不动。累计满 ${LIMIT} 条 ADR（含已被取代的）时归档重启（见 SKILL.md 流程 G），本文件历史完整保存在 archives/。

---

## 活动决策表

| # | 决策标题 | 日期 | 状态 |
|---|----------|------|------|
`;
}

function buildNewDecisions(seedRecords) {
  let out = headerBlock();
  seedRecords.forEach((r, i) => {
    out += `| ${i + 1} | ${r.title} | ${fieldValue(r, '日期')} | ✅ 生效 |\n`;
  });
  out += `\n---\n\n## 逐条记录\n\n`;
  seedRecords.forEach((r, i) => {
    const body = r.lines.slice(1).join('\n').trim();
    out += `### #${i + 1} ${r.title}\n${body}\n\n`;
  });
  return out;
}

const apply = process.argv.includes('--apply');
const content = readOrFail();
const records = parseRecords(content);
const count = records.length;

console.log(`DECISIONS.md 现有 ADR 记录: ${count} 条（含被取代的），上限 ${LIMIT} 条`);

if (count < LIMIT) {
  console.log(`未达上限（还差 ${LIMIT - count} 条），无需归档。`);
  process.exit(0);
}

const archiveName = `DECISIONS-${timestamp()}.md`;
const archivePath = path.join(archivesDir, archiveName);
// 缓存种子：当前文件末尾 CACHE 条（如 #8/#9/#10），原样重排为 #1/#2/#3
const seeds = records.slice(-CACHE);

if (!apply) {
  console.log(`\n已触发归档重启（dry-run，未改动文件）。将执行:`);
  console.log(`  1) 移入 archives/${archiveName}`);
  console.log(`  2) 新建 DECISIONS.md：复制末尾 ${CACHE} 条 (${seeds.map((r) => '#' + r.num).join(', ')}) 重排为新文件的 #1-#${CACHE} 缓存种子`);
  console.log(`  3) 其余 ${count - CACHE} 条仅留在归档中；之后新增从 #${CACHE + 1} 起`);
  console.log(`确认后运行: node ${path.join('scripts', 'archive.js')} --apply`);
  process.exit(0);
}

// --apply: 实际执行
fs.mkdirSync(archivesDir, { recursive: true });
fs.renameSync(decisionsPath, archivePath);
fs.writeFileSync(decisionsPath, buildNewDecisions(seeds), 'utf8');

console.log(`\n[APPLIED] 归档: ${archivePath}`);
console.log(`[APPLIED] 新 DECISIONS.md 已生成：缓存种子 ${seeds.map((r) => '#' + r.num).join(', ')} -> #1-#${CACHE}，之后新增从 #${CACHE + 1} 起。`);
