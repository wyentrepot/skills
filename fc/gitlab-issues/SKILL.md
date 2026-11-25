---
name: gitlab-issues
description: 读写公司 GitLab（git.friendcom.com，`dual-mode-communication/*` 等项目）的 issue、MR、评论、标签、指派时用我。凡"看下这个缺陷单""改个 issue""提个 MR""回条评论""查下这个分支的合并请求""#135 什么情况"这类指向 git.friendcom.com 的操作，先加载本技能再动手；我给出可直接跑的 `glapi` 命令、token 位置、以及 443 TLS 只认 Edge 这个坑的绕法。dsh 面板自带的 gitlab_panel_* 工具在本机不可用，不要试图用。
---

# 公司 GitLab（git.friendcom.com）操作

## 一句话

用 `glapi METHOD PATH [JSON]` 走 Edge 无头浏览器打 REST API；token 在 `/root/.dsh/gitlab-token`。

```bash
glapi GET "/api/v4/projects/dual-mode-communication%2Fsta/issues/135"
glapi GET "/api/v4/projects/dual-mode-communication%2Fsta/issues/135/notes?sort=asc&per_page=100"
```

stdout 是响应正文（JSON 自动格式化），stderr 打一行 `HTTP <code>`。判断成败看这个状态码，不要靠输出是否为空。

## 为什么不能直接用 curl

`git.friendcom.com` 解析到 `192.168.1.182`，**443 端口的 TLS 握手只对 Edge 有响应**：

- curl（WSL 与 Windows 自带都试过）、openssl s_client（TLS1.0~1.3、各种 cipher/curve/SNI/PROXY 协议）、node `tls`/`fetch`、python `requests`、`curl_cffi` 的 chrome/safari 指纹 —— 全部在 ClientHello 之后被服务端直接 EOF / ECONNRESET。
- 服务端是 GitLab 15.2.2-ee，`/api/v4/version` 报版本 15.2.2。
- 同机 9000 端口是**另一台** GitLab 实例（也是 15.x EE，走明文 HTTP），它不认公司这台 443 实例的账号和 token，别搞混。

所以 `glapi` 用本地 `file://` 页面 + `fetch` 让 Edge 当传输层，`--dump-dom` 把结果取回来。

## 前置

- `glapi` 在 PATH 上（`/usr/local/bin/glapi` 与 `/root/.dsh/bin/glapi` 均软链到本技能 `scripts/glapi`，真身随本仓库）。
- token：`/root/.dsh/gitlab-token`，一行 `glpat-...`，`api` scope，属于 `wangyu` (#263)。打 curl 直连 443 会 401、打 9000 会 401，这是**实例不对**，不代表 token 失效。
- 换 token：直接覆盖该文件即可，`glapi` 每次运行都重读。
- 可用环境变量覆盖：`GLAPI_ORIGIN`（默认 `https://192.168.1.182`）、`GLAPI_TOKEN_FILE`、`GLAPI_BUDGET`（Edge 虚拟时间预算毫秒，默认 9000，大响应/慢接口可调大）。

## 常用路径

项目路径要 URL 编码（`/` → `%2F`），下面以 `dual-mode-communication/sta` 为例：

| 操作 | 方法与路径 |
|---|---|
| 读 issue | `GET /api/v4/projects/dual-mode-communication%2Fsta/issues/135` |
| issue 全部评论 | `GET /api/v4/projects/dual-mode-communication%2Fsta/issues/135/notes?sort=asc&per_page=100` |
| 搜索 issue | `GET "/api/v4/projects/dual-mode-communication%2Fsta/issues?search=band3&state=opened&per_page=100"` |
| 加评论 | `POST .../issues/135/notes` body `{"body":"..."}` |
| 改字段（标题/描述/标签/关闭） | `PUT .../issues/135` body `{"labels":"bug","state_event":"close"}` |
| 指派 | `PUT .../issues/135` body `{"assignee_ids":[263]}` |
| 新建 issue | `POST /api/v4/projects/dual-mode-communication%2Fsta/issues` body `{"title":"...","description":"..."}` |
| 读 MR | `GET /api/v4/projects/dual-mode-communication%2Fsta/merge_requests/580` |
| MR 改动文件 | `GET .../merge_requests/580/changes` |
| MR 评论 | `POST .../merge_requests/580/notes` body `{"body":"..."}` |
| 我自己 | `GET /api/v4/user` |

`glapi` 的第二个参数带 `?query` 时会自己补 `&`，直接把带参数的完整路径丢进去即可。

## 写操作纪律

评论、改字段、关闭、合并这类动作先跟用户确认再发；用户明确说"直接改"才免确认。发之前把 body 原样给用户看一眼。涉及 `sta` 这类正式仓库的 issue 状态变更，别自发 `state_event`。

## 排查

- `HTTP -` + `helper did not finish` → Edge 第一次跑要建 profile，`GLAPI_BUDGET=15000 glapi ...` 重试。
- `HTTP 0` + `FETCHERR:...` → 网络层不通；确认 `ping 192.168.1.182` 与外网代理是否被强制（Edge 加了 `--no-proxy-server`，正常应直连）。
- `HTTP 401` → token 过期或被 revoke，重新生成 `api` scope 的 PAT 覆盖 token 文件。
- `HTTP 404 Project Not Found` → 项目路径没做 `%2F` 编码，或该账号无此项目权限。
- 面板里的 `gitlab_panel_*` 工具报 `cannot get property "workingDirectory" without inject`：`dsh-gitlab-panel@0.1.0` 的 `inject` 少了 `workingDirectory`，不是凭据问题，本技能不依赖它。
