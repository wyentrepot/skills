// Regression contract: req-mgmt keeps requirement status locally while
// writing-plans owns the detailed, baseline-bound execution plan.
const assert = require('assert');
const fs = require('fs');
const path = require('path');

const skillRoot = path.resolve(__dirname, '..');
const read = (relativePath) => fs.readFileSync(path.join(skillRoot, relativePath), 'utf8');

const skill = read('SKILL.md');
const todo = read('templates/reqs/0001-slug/TODO.md');
const index = read('templates/REQS-INDEX.md');
const planPath = path.join(skillRoot, 'templates/reqs/0001-slug/PLAN.md');

assert.ok(fs.existsSync(planPath), 'each requirement template must include a local PLAN.md');
assert.match(skill, /writing-plans/, 'req-mgmt must delegate detailed planning to writing-plans');
assert.match(skill, /PLAN\.md/, 'req-mgmt must define the local plan location');
assert.match(skill, /基线版本/, 'req-mgmt must bind a plan to the REQS baseline');
assert.match(skill, /若本需求存在 `PLAN\.md`/, 'small requirements without a plan must remain executable');
assert.match(todo, /PLAN\.md/, 'TODO.md must link to the execution plan');
assert.match(todo, /交付/, 'TODO.md must track deliverables rather than implementation substeps');
assert.match(index, /PLAN\.md/, 'the index must document the complete requirement artifact set');

console.log('req-mgmt plan-source contract passed');
