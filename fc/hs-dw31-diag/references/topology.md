# 拓扑（topology）

适用：查 CCO/STA 组网、MAC、TEI、角色、相位、版本。

## 命令

```bash
CTL="python3 $BASE/scripts/fcctl.py"   # $BASE = hs-dw31-base 技能目录（先读 hs-dw31-base 拿到）
$CTL topo --timeout 3.5
```

## 字段

`sn/count/is_last/entries[]`，entry：`mac/tei/proxy_tei/level/ability/role/product/online/phase_text/spc_ver/sw_ver/b_ver/version_time`。

## 判读

- `role=CCO`、`product=CCO` 为集中器；
- `online=false` 表示模块不在网；
- `phase_text` 是三相相位文本；
- MAC 用于和 `flash-prepare` 的 `target.module_mac` 对照。

## 注意

- `topo` 会向模块发 `0x1001`，是设备命令；先 `doctor/status` 确认 `device_ready`；
- 不要并发发多条 topo；一次任务查一次即可。
