# 查看日志（logs）

适用：查模块状态、版本、原始帧、日志类帧、prim 解析行、prim 结构树、拓扑。

## 1. 状态与版本

```bash
CTL="python3 $BASE/scripts/fcctl.py"   # $BASE = hs-dw31-base 技能目录（先读 hs-dw31-base 拿到）
$CTL doctor
$CTL status
$CTL version
```

`status` 重点字段：`logged_in`、`port_open`、`start_running`、`mode`、`module_ver`、`error`、`rx`、`tx`。
`start_running=true` = Start.exe/MaintenanceKits 占用，端口已让出，停止设备命令。

## 2. 原始帧

```bash
$CTL frames --since 0 --limit 50
```

- `since` 用上一批 `last_id`；`limit` 上限 2000；
- 返回最新 `limit` 条；
- 字段：`id/ts/dir/type/secure/cmd_id/cmd_name/psize/size/param_hex/crc_ok/decrypted/decoded`。

## 3. 日志类帧

```bash
$CTL logs --since 0 --limit 100
```

只保留 `0x5304/0x5314/0x5315/0x5316`。

## 4. prim 解析行与结构树

```bash
$CTL prim --since 0 --limit 100
$CTL prim-frame --id <frame_id>
```

prim 行字段：`id/ts/category/no/tick/prim_id/prim_hex/prim_name/structure/source_hex/dest_hex/data_len/has_struct`。
`has_struct=false` 或 `note` 非空时不要硬解。

## 5. 事件

```bash
$CTL events --seconds 10
```

- 8765 无 SSE，CLI 轮询 `/api/logs`；
- 只报启动后的**新**事件；历史用 `logs --since`。

## 6. 证据口径

- 结论带帧 `id` + `ts`；
- 引用 `param_hex` 或 `decoded` 时原样引用，不二次编造；
- 统计类结论说明 `since`/`limit` 时间窗。

## 7. 导出与落盘（唯一约定）

- 目录优先级：`REQ_DIR/logs/` → `PROJECT/logs/` → 会话工作区 `logs/`（见 `SKILL.md` §5）。
- 取样并落盘：

```bash
LOG_DIR="${REQ_DIR:-$PROJECT}/logs"; mkdir -p "$LOG_DIR"   # 两个变量按 SKILL.md §1 解析
STAMP=$(date +%Y%m%d-%H%M)
$CTL frames --since 0 --limit 2000 > "$LOG_DIR/$STAMP-frames.json"
$CTL logs   --since 0 --limit 1000 > "$LOG_DIR/$STAMP-logs.json"
$CTL prim   --since 0 --limit 1000 > "$LOG_DIR/$STAMP-prim.json"
```

- 服务自有的 `service_frames.jsonl`、`audit.jsonl` 是**只读源**（实际路径看 `status.logfile`）；
  要长期留存就导出到 `REQ_DIR/logs/`，不要把它们当工作区。
- 结论写成一份 `REQ_DIR/logs/<STAMP>-report.md`（或追加到 `REQ_DIR/DONE.md`），引用帧 `id`/`ts` 与导出文件名；不要在多处留半份结论。
