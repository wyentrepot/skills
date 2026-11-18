# NV 调试（nv）

适用：NV 目录、读 NV、写 NV（写需用户明确指令）。

## 1. 目录

```bash
CTL="python3 $SKILL_DIR/scripts/fcctl.py"   # $SKILL_DIR = 加载技能时给的技能目录（SKILL.md §1）
$CTL nv-list --module app --limit 50
$CTL nv-list --q app_mr --limit 20
$CTL nv-list --cco --limit 50
```

字段：`key_id/key_hex/name/module/structure/status/cco/product_types`。

## 2. 读

```bash
$CTL nv-read 1025
```

返回：`rc/rc_text/crc/crc_ok/data_hex/data_size/decoded/item`。

- `rc=0` 才算成功；
- `crc_ok=false` 或 `data_size` 不符时不要拿 `decoded` 下结论。

### 2.1 `rc=0` 但 `item=null` / `decoded=null` —— 不是 NV 坏了

`data_hex` 有值、`rc=0 成功`，但 `item=null`、`decoded=null`，表示：

- **设备里有这个 key**（值是真的）；
- **宿主侧的 NV 目录没有这个 key 的定义**（`mss_nvi_db.xml` 没这项，或服务还没重新加载）。

处置（按顺序）：

1. 确认构建产物的 `system/hdbcfg/mss_nvi_db.xml` 里是否有该 `key_id`；
2. 有 → 重启诊断服务让它重新加载（8766 控制面 `diag/stop` + `diag/start`，见 `contract.md` §2.1）；注意 `/api/prim/reload` **不重载 NV 目录**；
3. 注意 `mss_nvi_db.xml` 的 `ID` 是**十进制**（`1108` = `0x454`），别用十六进制 grep 误判；
4. 真正的来源是宿主两份产物，按顺序同步（**无 HTTP 上传接口，`prim/reload` 不管 NV**）：
   - `python3 /mnt/c/fc_diag_client/make_nv_catalog.py <固件 mcore_default.json>` → 重写 `data/nv_catalog.json`（93→97 项）
   - `cp <plc-sdk>/out/DW31v100/build/database.etypes /mnt/c/fc_diag_client/data/nv_structs.etypes`（结构体布局）
   - 用 8766 接口重启：`POST /api/v1/services/diag/stop` → `/diag/start`
5. 只同步目录不同步 etypes：`item.name` 有、`decoded.fields` 为空——按上一条补 `database.etypes`。

同理，`nv-list` 项数与固件不符（新增项查不到）也是宿主 NV 目录过期，不是模块问题。

## 3. 写（必须有用户明确指令）

```bash
$CTL nv-write 1025 --hex 0102 --confirm
```

- 缺 `--confirm` 会返回 `CONFIRM_REQUIRED`，不发请求；
- 只在用户明确要求时执行；
- 默认 `verify=true`，看 `verify.match`；
- 写失败/回读不一致：`NV_WRITE_FAILED`；读失败：`NV_READ_FAILED`。

## 4. 常见错误

| code | 含义 | 处置 |
|---|---|---|
| `NOT_LOGGED_IN` | 未登录 | 查 `status`；等重登或重启服务 |
| `COM_RELEASED` | 端口让出 | 停 Start.exe/MaintenanceKits |
| `NV_READ_FAILED` | rc 非 0 | 换 key 或查模块状态 |
| `NV_WRITE_FAILED` | 写/回读失败 | 不要重试风暴；报告 rc 与 data_hex |
