# 01 · ds-bot 插件作者的设计意图

状态：已建档（2026-10-13）· 证据等级：**源码检查 + 文档调研**（本机安装的插件源码）
对象：`ds-bot` v0.1.4，Apache-2.0，仓库 `github.com/Fei2411/DeepSeek-Bot`
源码位置：`<DSH_HOME>\profiles\desktop\node_modules\ds-bot\`

> 本文是**新建 Bot 与调整团队结构时的第一依据**。以下每条结论都附可核对的源码位置，不引用记忆。

---

## 1. 一句话结论

**他做的不是"项目组编排器"，而是"一家公司"**——常驻的同事（Bots）、房间（Rooms）、消息（Exchanges）、长期记忆（每人一份 + 团队一份）、以及一套很轻的权限（Main Bot / 群管理员 / 成员）。
**"项目"在他的模型里不是一个对象，而是一批文件。**

---

## 2. 一等公民只有五类（硬证据）

`src/host/store.js:14-15` 明确定义了持久化的团队状态：

```js
{ version, workspaceId, mainBotIds[], bots{}, rooms{}, agents{},
  capabilities: { items }, exchanges[], exchangeTurns{}, questions{}, prefs{}, revision }
```

- **没有 `project` / `projectId` / `projects`。**
- 有的是：人（`bots`）、房间（`rooms`）、群内隐藏会话（`agents`）、Bot 间消息（`exchanges`）、提问（`questions`）、偏好（`prefs`）。
- `agents` 是"每个成员在每个群里一个隐藏 Session"的映射——隔离做在会话层，不是在项目层。

## 3. 一个 Bot 由什么构成（硬证据）

`src/host/roster.js:69-82`：

```js
state.bots[id] = {
  id, name,                       // name ≤ 40 字符
  role,                           // ≤ 24 字符，就是界面上的角色标签
  color?, avatar?, model?, effort?,
  instructions: String(...).trim(),  // 自由文本
  createdAt, createdBy, capabilities: [],
}
```

- **同样没有项目字段。**
- "岗位"= `role`（≤24 字符的标签）+ `instructions`（自由文本）。**是给人看的身份，不是可复用的岗位目录。**
- 模型在创建时固定（`roster.js:64` 注释："The model is fixed at creation"），之后由 `update_bot` 改。

## 4. 全团队只有一个工作目录（硬证据）

`src/host/roster.js:14-22` 的 `ensureWorkspace()`：

```js
const path = config.workspace ?? join(home, 'workspace')
...
state.workspaceId = workspace.id       // 单例，团队级
```

- 不是"每个 Bot 一个工作目录"，也不是"每个项目一个工作目录"。
- 一个团队 = 一个 workspace；项目就是 workspace 里的目录/文件。

## 5. 记忆只有两个作用域，"项目"被降级为 topic（硬证据）

README:96：**Two scopes** —— 每个 Bot 自己一份 + 团队共享一份。

`src/host/memory.js:775 / 779`（`remember` 工具的 `topic` 参数说明）：

> `'A topic for details not every conversation needs, such as "travel" or "project-x"'`
> `'"${...}" cannot be a topic name: use a short word or two, such as "travel" or "project-x".'`

- **设计者对"项目知识放哪"的答案是：起一个 topic 装它**（他甚至把 `project-x` 当范例）。
- 更关键的两句（`memory.js:303`、`memory.js:353`）：
  > "Instructions from the user's **project files (such as AGENTS.md) are not memories** either: every Session reads those files again."
- 即：**项目事实属于"每次重读的文件"，不属于记忆，更不属于身份。**

## 6. 身份段为"提示词缓存"刻意解耦（最关键的一条）

`src/host/prompt.js:1-2` 的模块注释：

> "Prompt: one section whose text depends **only on the rendering Session's own Bot record**, so the prefix stays **byte-stable across turns and roster changes**."

`prompt.js:42-52` 的实现：身份段 = `# Your identity` + `You are <name>, a Bot on the user's team` + `role` + `instructions` +（Main Bot 额外追加 `MAIN_RULES`，否则只有 `TEAM_RULES`）。

- 设计者**刻意**让身份提示词与团队构成、其他 Bot、项目都无关，只为让前缀逐字节稳定、命中 provider 的 prompt cache。
- 推论（对我们是硬约束）：**往 `instructions` 里塞项目事实，既会腐烂，又会让该 Bot 的整个前缀缓存失效。**

## 7. 权限是治理设计，不是实现限制

README:14-21 的能力表：

| 角色 | 能做 |
| --- | --- |
| 用户 | 一切 |
| Main Bot（可多个） | 管理所有群；**改和删 Bot** |
| 群管理员 | 只管自己的群（名称、公告、成员、回复模式） |
| 成员 | 在群里发言、`@` 别人 |

`prompt.js:25-36` 的 `MAIN_RULES` 标题就是 **"You are the Main Bot (Chief of Staff)"**；README:54：团队首次打开时，插件自动创建的第一个 Main Bot 就叫 **Chief**。

- 所以"建人/改名/换模型只有 Main Bot 能做"是**权限设计**，不是做不到。
- 这同时解释了为什么"专职运维 Bot 不能自救"：它天然没有改组织的权限。

## 8. 为什么没有"Bot 探活"接口

README:11：**"each Bot is a dsh Session"**。Bot 是会话，不是进程；插件层只有 turn 的 running / idle 语义，没有心跳。

- 因此"探活"只能探**它挂载的模型路由**或看**它的产物新鲜度**，不能探"Bot 是否活着"。

## 9. 他有没有考虑"岗位与项目分离"？

**有考虑，而且是有意留白。** 三条证据并列时结论很清楚：

1. 数据模型里没有项目对象（§2、§3）；
2. 项目知识被显式降级为文件与 topic（§5）；
3. 身份提示词被刻意做成与项目无关（§6）。

他的抽象边界是**协作底座**，不是项目管理器。代价是：跨项目复用要靠文件约定和人的自觉，插件不会帮你——所以我们补的 `PROJECT-CARD.md` 是**在他留白处加约定**，不是跟他对抗。

## 10. 推导出的四条硬约束（团队规则）

1. **岗位＝公司级，项目＝按需加载。** 岗位卡只写职责与规则；项目事实写在项目档案卡里，派工时指明项目根目录，由成员加载。
2. **身份段字节稳定。** 不为了"让 Bot 多知道点项目"去改 `instructions`；项目细节进文件。改 `instructions` 属于会失效缓存的操作，要显式说明。
3. **项目知识用 `topic` 承载**（`bot-mgmt` / `<项目名>` / …），并做项目间隔离，禁止把 A 项目的口径带到 B 项目。
4. **组织变更只能由 Main Bot 做**（建人、改名、换模型、管群）。任何"自治运维"的设想都要先过这一条。

## 11. 可变性

README:5 自述："Early release (v0.1). Features, tools and **the saved data format can still change**."
→ 版本升级后需复核本文的证据位置；本文结论若与新版冲突，以新版源码为准，并把差异记进本文件。

## 12. 可回馈上游的点

我们对"项目层"的补法是纯文件约定（PROJECT-CARD.md + 项目注册表 + 派工携带项目根目录），不依赖插件改动。如果作者愿意，这是一个可以提的建议：**在 `instructions` 之外提供一个"项目档案"槽位**，既保住身份段缓存，又让项目加载标准化。
