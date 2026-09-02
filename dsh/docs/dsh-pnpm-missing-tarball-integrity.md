# DSH Desktop 插件安装失败：ERR_PNPM_MISSING_TARBALL_INTEGRITY 排查与修复

> 记录日期：2026-08-31
> 目的：记录 DSH Desktop `web` profile 因锁文件条目缺 `integrity` 导致 pnpm 拒绝安装的完整根因、修复方案与复发建议。
> 适用版本：DSH Desktop 0.7.1（自带 pnpm 10.34.5）、dshmarket ≥ 1.31.1、`web` profile（国内镜像/gh-proxy 场景）。
> 结论速览：锁文件里 `dsh-billing-balance` 条目 `resolution: {tarball: <gh-proxy URL>}` 既无 `integrity`、又因 `gh-proxy.com` 前缀不被 pnpm 识别为 git-hosted → pnpm 10.34.5 直接报错。最小修复 = 给该条目补 `gitHosted: true`（保留固定 commit）；彻底修复 = 删锁文件重新 `install`（会重解析 `github:` 依赖到最新 commit）。

## 一、现象

`web` profile 安装/启动时 pnpm 失败，错误输出：

```
dsh: pnpm failed in profile directory C:\Users\A24006872\AppData\Roaming\dsh-desktop\harness\profiles\web
ERR_PNPM_MISSING_TARBALL_INTEGRITY: Cannot install package "dsh-billing-balance@https://gh-proxy.com/https://codeload.github.com/YZz-S/dsh-billing-balance/tar.gz/0550c7c76924c56c89f4a8e1756ee680bd4140e0": its lockfile entry has no "integrity" field, so pnpm cannot verify the downloaded tarball.
```

`dsh: pnpm failed …` 来自 DSH 自带插件 `@deepseek-ai/dsh` 的 `dsh plugin` 转发器（`node_modules\@deepseek-ai\dsh\lib\plugin-*.js` 的 `runPlugin`，它只是 `pnpm <args>` 的薄封装）；`ERR_PNPM_MISSING_TARBALL_INTEGRITY` 来自 pnpm 自身。

## 二、环境

| 项 | 值 |
|----|----|
| DSH Desktop | 0.7.1（`package.json`） |
| 自带 pnpm | 10.34.5（`node_modules\pnpm\package.json`） |
| profile 目录 | `C:\Users\A24006872\AppData\Roaming\dsh-desktop\harness\profiles\web` |
| 出问题依赖 | `dsh-billing-balance`（gh-proxy 固定 commit tarball） |
| 同 profile 其它 GitHub 依赖 | `dsh-maid-whale-webUI`（`github:...#path:`）、`dsh-whale-musume`（`github:`）——均正常 |

## 三、根因（源码级证据）

### 3.1 锁文件条目形态

`web\pnpm-lock.yaml` 中（修复前）：

```yaml
dsh-billing-balance@https://gh-proxy.com/https://codeload.github.com/YZz-S/dsh-billing-balance/tar.gz/0550c7c76924c56c89f4a8e1756ee680bd4140e0:
  resolution: {tarball: https://gh-proxy.com/https://codeload.github.com/YZz-S/dsh-billing-balance/tar.gz/0550c7c76924c56c89f4a8e1756ee680bd4140e0}
  version: 0.2.0
  engines: {node: '>=18'}
```

只有 `tarball`，**既没有 `integrity`，也没有 `gitHosted: true`**。

对比同 profile 两个正常的 GitHub 依赖（锁文件里都有 `gitHosted: true`，故无需 integrity）：

```yaml
dsh-whale-musume@https://codeload.github.com/Sutera-Diffusus/dsh-whale-musume/tar.gz/032ff113d75116d573a555bc32eca52f788dbdc9:
  resolution: {gitHosted: true, tarball: https://codeload.github.com/Sutera-Diffusus/dsh-whale-musume/tar.gz/032ff113d75116d573a555bc32eca52f788dbdc9}
```

### 3.2 pnpm 的校验逻辑（pnpm.cjs，编译产物可读）

`pkgSnapshotToResolution` 对每条 tarball 形式依赖做校验，以下条件**同时成立**即抛 `MISSING_TARBALL_INTEGRITY`：

```js
resolution.type == null                      // 无 type
&& resolution.integrity == null              // 无 integrity
&& !resolution.tarball?.startsWith("file:")  // 非本地 file: tarball
&& !(resolution.gitHosted === true
     || isGitHostedTarballUrl(resolution.tarball))  // 不被识别为 git-hosted
```

而 `isGitHostedTarballUrl` 只认这三个前缀：

```js
url.startsWith("https://codeload.github.com/")
|| url.startsWith("https://bitbucket.org/")
|| url.startsWith("https://gitlab.com/")
```

**关键点**：`https://gh-proxy.com/https://codeload.github.com/…` 带 `gh-proxy.com` 前缀，**不匹配** codeload 前缀 → 不被识别为 git-hosted → 又无 integrity → pnpm 10.34.5 读取自己的锁文件时直接拒绝。

同 profile 另外两个 GitHub 依赖是 `gitHosted: true`（codeload 直连 / 带 `#path:`），因此不受影响。

### 3.3 这个条目是怎么来的

来源是 **dshmarket 的国内镜像加速**：

- `node_modules\dshmarket\lib\regions.js`：`GITHUB_PROXY_CHINA = 'https://gh-proxy.com'`。
- `node_modules\dshmarket\lib\accelerate.js`：把裸 `github:YZz-S/dsh-billing-balance` 目标解析出 HEAD commit 后，重写为「固定 commit 的 gh-proxy codeload tarball URL」，再交给 `pnpm add <url>`。
- `node_modules\dshmarket\lib\sources.js` 的 `codeloadTarball()`：`${proxy}/${direct}` 即 `https://gh-proxy.com/https://codeload.github.com/<repo>/tar.gz/<sha>`。

即：市场装 GitHub 插件时把 URL 改写成了 pnpm 无法按 git-hosted 识别的形态。

### 3.4 为什么锁文件里没有 integrity（观察结论）

- 条目里 `version: 0.2.0` 说明写入时读取过 tarball 的 manifest；
- 但 pnpm store（`%LOCALAPPDATA%\pnpm\store\v11`）里 **查不到** `dsh-billing-balance` 的任何内容 → 该条目是一次未真正落地到 store 的畸形残留（写入路径无法完全复原，可能来自早期失败的 `add`/旧版本 pnpm/手工写入）。
- 无论历史成因如何，**当前 pnpm 10.34.5 拒绝它的逻辑是确定的**，修复不依赖历史成因。

## 四、修复方案

### 方案 A（已采用，最小改动、保留固定 commit）

给 `dsh-billing-balance` 的锁文件条目补上 `gitHosted: true`（与另两个 GitHub 依赖写法一致）：

```yaml
resolution: {gitHosted: true, tarball: https://gh-proxy.com/https://codeload.github.com/YZz-S/dsh-billing-balance/tar.gz/0550c7c76924c56c89f4a8e1756ee680bd4140e0}
```

- 能通过 `assertRegistryShapedResolution`（URL 形态 depPath 的 `nonSemverVersion` 非空，直接提前返回）与 `pkgSnapshotToResolution`（`gitHosted === true` 跳过 integrity 校验）两道检查；
- 安装时 pnpm 走 `gitHostedTarballFetcher`，从 `resolution.tarball`（同一 gh-proxy URL，已实测可达，返回 `application/x-gzip`）下载，**提取时即计算并写回 integrity，锁文件自愈**；
- 其余所有固定 commit、`dsh.profile.bundles` 等一律不动。
- 修改前已备份：`web\pnpm-lock.yaml.bak`（可随时还原）。

修复后重装：

```
dsh plugin --profile web install
```

（或重启 DSH / 在 dshmarket 页面重试安装。）

### 方案 B（pnpm 官方建议，彻底重生成）

若 A 之后仍被其它校验拦住，或想彻底重建锁文件：

```
del C:\Users\A24006872\AppData\Roaming\dsh-desktop\harness\profiles\web\pnpm-lock.yaml
dsh plugin --profile web install --no-frozen-lockfile
```

- pnpm 重新解析整个依赖树，对 gh-proxy tarball 重新下载并写入 `integrity`，产物为标准形态；
- **代价**：两个 `github:` 依赖会重解析到各自最新 commit（当前锁文件里的固定 commit 会变），行为可能有细微变化。

### 方案 C（改 spec 为 github: 形式，不推荐在本场景用）

把 `package.json` 里 `dsh-billing-balance` 的 spec 改成 `github:YZz-S/dsh-billing-balance#0550c7c76924c56c89f4a8e1756ee680bd4140e0`，pnpm 按 git-hosted 解析、无需 integrity。

- 代价：丢失 gh-proxy 代理（国内直连 codeload 慢）；且 dshmarket 再次通过市场安装时 accelerate 仍会把它改写回 gh-proxy URL，问题复现。

## 五、复发风险与建议

**会复发**。触发条件：通过 dshmarket 国内镜像（gh-proxy）安装「带固定 commit 的裸 GitHub 插件」，且产物落进锁文件时未带 `integrity`（当前 `web` profile 即如此）。

- dshmarket 的 `classifyPnpmFailure`（`lib/pnpm-compat.js`）**没有覆盖** `MISSING_TARBALL_INTEGRITY`，所以这类失败不会得到可读的中文提示，只会看到 pnpm 裸错误 + `dsh: pnpm failed …`。
- 建议反馈给 dshmarket 作者：
  1. `accelerate` 产物落锁后补 `gitHosted: true`（或保证 `pnpm add` 后锁条目带 `integrity`）；
  2. 在 `classifyPnpmFailure` 中增加对该错误的识别与中文提示；
  3. 或在加速不可用时回退为 `github:` 形式（避免产生 pnpm 无法校验的 tarball 条目）。
- 用户侧规避：市场里把下载区域切回「直连」，或对裸 GitHub 插件改用 `github:owner/repo` 手动 `dsh plugin add`。

## 六、速查命令

```powershell
# 修复后重装（方案 A 之后）
dsh plugin --profile web install

# 彻底重生成锁文件（方案 B）
del C:\Users\A24006872\AppData\Roaming\dsh-desktop\harness\profiles\web\pnpm-lock.yaml
dsh plugin --profile web install --no-frozen-lockfile

# 还原本次手动修改（若需）
copy C:\Users\A24006872\AppData\Roaming\dsh-desktop\harness\profiles\web\pnpm-lock.yaml.bak `
     C:\Users\A24006872\AppData\Roaming\dsh-desktop\harness\profiles\web\pnpm-lock.yaml
```

## 七、涉及文件

| 文件 | 作用 |
|------|------|
| `…\profiles\web\pnpm-lock.yaml` | 已修复（补 `gitHosted: true`） |
| `…\profiles\web\pnpm-lock.yaml.bak` | 修复前备份 |
| `…\profiles\web\package.json` | 未改动（spec 仍是 gh-proxy URL） |
| `node_modules\@deepseek-ai\dsh\lib\plugin-*.js` | DSH `dsh plugin` 转发器（只是 `pnpm` 薄封装，非根因） |
| `node_modules\dshmarket\lib\{accelerate,regions,sources,pnpm-compat}.js` | 镜像加速来源 + 故障分类（未覆盖本错误） |
| `node_modules\pnpm\dist\pnpm.cjs` | pnpm 校验逻辑所在（`pkgSnapshotToResolution` / `isGitHostedTarballUrl`） |
