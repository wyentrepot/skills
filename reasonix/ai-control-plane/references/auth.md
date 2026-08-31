# 授权（人来做，AI 只持有 token）

> 前置：workbench 已在 8790 运行（`curl http://127.0.0.1:8790/api/health` → 200）；
> 人工授权密钥已配置（`tools/scripts/一键生成AI密钥.bat` 一键装好，或环境变量 `WORKBENCH_AI_ADMIN_KEY`）。

## 签发（仅限 workbench 本机 127.0.0.1 + admin key）

```bash
curl -X POST http://127.0.0.1:8790/api/ai/v1/admin/grants \
  -H "X-Workbench-Admin-Key: <WORKBENCH_AI_ADMIN_KEY>" \
  -H "Content-Type: application/json" \
  -d '{"scopes":["observation:create","evidence:read"],"resources":["*"],"ttl_seconds":3600,"reason":"监控cco日志"}'
```

- **scope 最小化**：只申请本次任务需要的（见下表），示例即"只监控日志"所需的最小集。
- `resources`：`*` 或具体 mapping_id / session_id；`ttl_seconds` 1–86400；
  `max_operation_seconds` 可选（默认 1800）。
- **要烧录必须给 `firmware_roots`**（允许的固件目录白名单数组），否则 flash 返回
  403「当前授权未配置允许烧录目录」。
- 响应里的 `token` **只返回一次**（服务端只存 SHA-256 摘要）——务必保存，AI 全程只用 token。
- 503 = admin key 未配置/没重启；403 = key 错或非本机发起。

## scope → 能力映射（13 种）

| scope | 能力 | 典型任务 |
| --- | --- | --- |
| status:read | /status、/audit | 探状态、看审计流水 |
| module_session:ensure / module_session:stop | 会话建立 / 停止 | 发指令、烧录前开串口 |
| module_send:execute | send | 发串口指令 |
| module_flash:execute | flash | 烧固件 |
| listener:ensure / listener:stop | 侦听台采集开 / 停 | 盯帧、采集控制 |
| listener:trace | 通信流追踪创建 | 追踪一轮业务 |
| observation:create | 建观察、取消操作 | 监控日志/盯帧 |
| evidence:read | 操作/证据/帧/追踪读取 | 取证、查帧（监控行也必需） |
| simcon:verify / simcon:send / simcon:read | 验证任务 / 单步·开关串口 / 帧日志读 | 跑验证用例 |

## 管理辅助

- `GET /admin/grants` 列出授权、`POST /admin/grants/{grant_id}/revoke` 撤销（均 admin key）。
- `GET /audit`（token，需 status:read）看审计流水（按授权 resources 过滤）。
