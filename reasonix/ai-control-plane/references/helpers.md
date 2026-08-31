# 辅助面（无鉴权，8790 直调）与验证编排 REST

以下端点在 `/api/simcon`、`/api/dict`、`/api` 命名空间，**不经 /api/ai/v1、无需 Bearer**
（局域网可达，见 ADR-28）。适合轻量查询与预检；涉及串口操作与证据链的仍走 /api/ai/v1。

## 协议字典（查语义 / 查规则 id）

```bash
curl http://127.0.0.1:8790/api/dict                    # 四本字典清单（id/名称/条数/来源路径）
curl "http://127.0.0.1:8790/api/dict/oad?q=电压"       # 698.45 OAD
curl "http://127.0.0.1:8790/api/dict/di?q=..."         # 645-2007 DI
curl "http://127.0.0.1:8790/api/dict/afn-fn?q=F230"    # 1376.2 AFN/Fn 语义
curl "http://127.0.0.1:8790/api/dict/rules?q=<事件名>" # loghooks 事件规则
```

- `?q=` 模糊过滤（对条目 JSON 全文做小写包含匹配）。
- **observation 的 `loghook_rule.rule_id` 从 `/api/dict/rules` 查**。
- 数据直接来自 `libs/parser_lib/adapters/*/metadata/*.json` 与 `libs/loghooks/rules/`，改 JSON 即生效。

## 构帧预检 / 应答规则

```bash
# 语义化构帧：只经 scenario_codec 算字节不触串口，下发前预检报文（422=构帧失败）
curl -X POST http://127.0.0.1:8790/api/simcon/build -H "Content-Type: application/json" \
  -d '{"afn":"06","fn":"F230","params":{},"direction":"down","profile":"anhui","seq":1}'
# → {"hex":"...","length":N}

# simcon 当前生效应答规则（内置+覆盖）
curl http://127.0.0.1:8790/api/simcon/responders
```

## 验证编排 REST（无 token / 无 operation / 无审计）

```bash
curl http://127.0.0.1:8790/api/scenarios               # 场景模板清单
curl http://127.0.0.1:8790/api/scenarios/<id>/task     # 场景激励任务原始 JSON
curl -X POST http://127.0.0.1:8790/api/run \
  -H "Content-Type: application/json" -d '<RunRequest，字段见 apps/workbench/orchestration/dto.py>'
# → 立即返回 run 视图（status=running）→ 轮询 GET /api/run/<run_id> 到终态
#   passed / failed / cancelled / error / inconclusive
# 报告 GET /api/run/<id>/report；产物 GET /api/run/<id>/artifacts[/{artifact_id}]；
# 取消 POST /api/run/<id>/cancel；历史 GET /api/runs?limit
```

- 取舍：要**授权审计/证据链/幂等**走 `/api/ai/v1`；只是**直接驱动一次全链路验证拿报告**，`/api/run` 更短。
