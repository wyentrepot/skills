# 模块串口会话（cco/sta）与烧录

> v2 门面（免 token，local_full）：`POST /api/ai/v2/module-actions`，action=ensure/send/stop，
> 202 + job → `GET /api/ai/v2/jobs/{id}`。**实测坑（2026-09-10）**：普通 stop 遇活跃观察任务
> 返回 409（非故障）→ `force:true`；v2 stop job 可能停在 `waiting/running`（已知状态不收敛点），
> 物理串口已释放则以串口状态为准。本文件以下为 v1 专家/兼容写法（需 Bearer token）。

## ensure（幂等，创建或复用并打开）

```bash
curl -X POST http://127.0.0.1:8790/api/ai/v1/module-sessions/ensure \
  -H "Authorization: Bearer <token>" -H "Content-Type: application/json" \
  -d '{"module":"cco","mapping_id":"cco-main"}'
```

- **优先 `mapping_id`**（`cco-main`/`sta-main`，波特率等串口参数按
  `config/serial_ports.json` 映射自动走；实际 COM 号随接线变化，**别硬编码 COM 号**）。
  也可直接传 `port`。
- 返回 `session_id`（形如 `ms-xxxx`），state=running 表示串口已开。
- 409 = 串口被占用（前端或另一会话占着），等释放或改口——这是物理独占规则，不是 bug。

## 发送

```bash
curl -X POST http://127.0.0.1:8790/api/ai/v1/module-sessions/<session_id>/send \
  -H "Authorization: Bearer <token>" -H "Content-Type: application/json" \
  -d '{"text":"你的字符串","append_newline":true,"client_request_id":"<幂等ID>"}'
# 或十六进制：{"data_hex":"68 00 ..."}
```

- 200 + state=succeeded 即成功；`result.sent` 是字节数。

## 停止

```bash
curl -X POST http://127.0.0.1:8790/api/ai/v1/module-sessions/<session_id>/stop \
  -H "Authorization: Bearer <token>" -H "Content-Type: application/json" \
  -d '{"force": false}'
```

- 409 + 提示需 force：会话有活跃依赖（如观察任务）时普通 stop 拒绝；
  确认后 `{"force":true}`。

## 烧录固件（异步，不可取消）

> **⚠️ 烧录文件选择（铁律，2026-09-10 实测教训）**：
> - **升级/烧录用 `iap_{cco|ecu}_*.bin`**（IAP 升级镜像，~几百 KB，走 bootloader XMODEM 串口升级）。
> - **不要用 `flash_{cco|ecu}_*.bin` 当升级文件**：那是**生产烧录**文件（整片 flash 镜像，~2MB），
>   产线烧录器/专用工具用；bootloader 升级路径不认它——实测烧 flash.bin 会在 ~24%
>   （约 503KB，超出 iap 镜像范围）后模块停止 ACK 并中止（"timeout"→"cancel"→退回 shell）。
> - `upgrade_{cco|ecu}_*.dat` 是另一条串口升级格式（`upgrade` 文件），与 bootloader XMODEM 路径无关。
> - 不确定时先读 `firmware/readme.txt`（文件1=生产烧录 flash / 文件2=iap串口升级 / 文件3=upgrade串口升级）。

```bash
curl -X POST http://127.0.0.1:8790/api/ai/v1/flash-operations \
  -H "Authorization: Bearer <token>" -H "Content-Type: application/json" \
  -d '{"session_id":"<session_id>","bin_path":"<WORKBENCH_ROOT>/../firmware/iap_cco_*.bin","slot":0,"client_request_id":"<id>"}'
```

- 授权里的 `firmware_roots` 必须包含 `bin_path`，否则 403「未配置允许烧录目录」。
- 返回 202 + `operation_id`；轮询 `GET /operations/<operation_id>/wait?timeout_seconds=30`
  → `succeeded`（含 flash 结果）/ `error` / `timed_out`。
- 烧录期间不并发重试；等终态。
