# v2 契约补充：八条路径 · observation 编排示例 · 找回 job

> 拆自 wb-base/SKILL.md（2026-11-18 拆薄）。八条公开路径与 §3.2 的 422 坑、investigations 完整示例、job_id 丢失时的找回方法。正文 §3.2/§3.3 只留每次必用的骨架。

### §3.2 八条公开路径

| 方法 | 路径 | capability | 说明 |
| --- | --- | --- | --- |
| GET | `/api/ai/v2/capabilities` | `capabilities.read` | 能力、后端健康、逻辑资源别名 |
| POST | `/api/ai/v2/investigations` | `investigations.create` | 最多 **3 个** observation 并行编排模块日志、侦听台、simcon |
| POST | `/api/ai/v2/verification-runs` | `verification_runs.create` | 复用既有 simcon 验证；**不是烧录成功的替代** |
| POST | `/api/ai/v2/module-actions` | `module_actions.*` | 显式 `ensure`/`send`/`stop`，禁止任意 action 透传 |
| POST | `/api/ai/v2/flash-jobs` | `flash_jobs.create` | 复用既有烧录控制；固件路径必须在授权 `firmware_roots` 内 |
| GET | `/api/ai/v2/jobs/{job_id}` | `jobs.read` | `wait_seconds=0..30`，GET 无副作用 |
| POST | `/api/ai/v2/jobs/{job_id}/cancel` | `jobs.cancel` | 观察可取消；**烧录/验证拒绝取消** |
| GET | `/api/ai/v2/jobs/{job_id}/evidence` | `jobs.evidence.read` | `level=L1\|L2\|L3`；L1/L2 有界，L3 只返回稳定引用 |

请求/响应都是命名 Pydantic schema；写任务携带 `client_request_id` 实现幂等（重复提交复用原 job）。

**`verification-runs` 的 body 形状与 422 平铺坑：唯一来源是 wb-base/SKILL.md §3.2，此处不复制。**

> 来源：ai-control-plane/references/api-contract.md；ai-control-plane/references/operation-guide.md
> 来源：validation-20261028/F3（T3 实机：平铺 → 422；包 `task` → 202）


---
### §3.3b 找回最近的 job（2026-10-28 新增）

job_id 丢了不用翻 json 文件：

```bash
curl -s "http://127.0.0.1:8790/api/ai/v2/jobs?kind=flash_job,verification_run&state=error&limit=10"
# → {"jobs":[{operation_id,kind,actor,state,created_at,updated_at,client_request_id,error,job_id}],"count":N,"limit":10}
```

- `kind` 可重复（`?kind=flash_job&kind=verification_run`）或逗号分隔；`state` 精确匹配；`since` 为 ISO 时间（非法值 422）；`limit` 默认 20、**硬上限 100**。
- 每条只含元数据（**不含 payload/result**），另带派生 `job_id`，可直接拿去 `GET /jobs/{job_id}` 或 `/evidence`。
- 已知边界：列表**未按资源收敛**——LAN 侧只要有 `jobs.read` 就能看到全部摘要（单条 `read_job` 才逐条校验 resources）。

> 来源：apps/workbench/ai_store.py list_operations、apps/workbench/ai_v2_api.py GET /jobs（2026-10-28 d5719b7 落地，实机验证通过）

