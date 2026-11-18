# 排障（errors）

## 1. 后端与端口

- **主后端**：Windows `127.0.0.1:8765`（fc_service.py，单服务）；
- 8770/8780 是历史/可选，不再要求；
- WSL 直连 Windows 回环会 connection refused；CLI `--transport auto` 自动改用
  `/mnt/c/Windows/System32/curl.exe`，不需要端口转发；
- 强制直连/强制 wincurl：`--transport direct|wincurl`。

## 2. 启动服务

```bat
:: 现场入口，按服务安装位置执行（如 start_web.bat）
```

启动后 `doctor` 应显示 `selected=legacy`、`device_ready=true`。

## 3. 退出码与错误码

| 退出码 | code | 含义 | 处置 |
|---|---|---|---|
| 3 | `NO_BACKEND` | 8765 不可达 | 启动 `start_web.bat` |
| 3 | `WSL_DOWN` | 8770 在但 8780 未就绪（历史） | 用 8765；不用管 8770 |
| 3 | `UNREACHABLE` | Windows curl 失败 | 检查服务/端口；`--transport wincurl` |
| 4 | `NOT_LOGGED_IN` | 会话未登录 | 查 `status`；等重登/重启服务 |
| 4 | `COM_RELEASED` | 端口让出 | 停 Start.exe/MaintenanceKits |
| 4 | `SESSION_MUTED` | 心跳超时，模块静默 | 必须断电重启模块 |
| 1 | `FLASH_*` | 烧录门禁拒绝 | 重新 prepare；不要绕过 |
| 1 | `LEGACY_PREPARE_MISSING` | 旧版 8765 没有 prepare 接口 | 升级服务端到带 prepare 的版本；不要退回 `/api/upg/load`/`start` |
| 2 | `CONFIRM_REQUIRED` | NV 写缺确认 | 用户明确要求后加 `--confirm` |
| 2 | `BACKEND_UNSUPPORTED` | 该后端不支持 | 换 `--backend` 或改用支持的后端 |

### 3.1 `POST /api/relogin` 可能卡死（实测）

`POST http://127.0.0.1:8765/api/relogin`（空 body）在部分版本上**连接建立、请求发出后服务端 0 字节返回**，curl 10 s 超时（`curl: (28)`），且调用后设备命令可能全部变成 `0x5503 无应答` / `COM_RELEASED`。

- **不要反复调 relogin**；一次不返回就改走控制面：`POST http://127.0.0.1:8766/api/v1/services/diag/stop` → `/diag/start`（见 `contract.md` §2.1）；
- 重启服务后 `doctor` 确认 `device_ready=true` 再继续；
- 若重启服务仍不通，按 §3 的 `SESSION_MUTED` 处理（断模块电）。

## 4. 检查顺序

1. `$CTL doctor`：看 selected/device_ready；
2. `$CTL status`：看 `logged_in`、`port_open`、`start_running`、`mode`；
3. 看服务帧日志最新时间（路径取 `status.logfile`，通常是 `service_frames.jsonl`）；
4. 仍不通 → 用 8766 控制面重启诊断服务（`diag/stop` + `diag/start`，见 `contract.md` §2.1），**不要自己改 Windows 服务/串口桥**；
5. 重启后仍不通，再判断是端口/会话问题还是模块侧停摆（模块侧停摆的特征：诊断命令零应答，但串口在线 → 断模块电）。

## 5. 禁止

- 不要为了让命令通过而重启工作台/塞环境变量/改 Windows 绑定；
- 不要绕过 prepare/commit 门禁；
- 不要在 Start.exe/MaintenanceKits 运行时抢串口。
