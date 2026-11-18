# 原始命令（raw）

适用：发单条诊断命令并看 ACK；已知 cmd_id/param 时使用。

## 命令

```bash
CTL="python3 $BASE/scripts/fcctl.py"   # $BASE = hs-dw31-base 技能目录（先读 hs-dw31-base 拿到）
$CTL send --cmd 0x3013 --wait 2
$CTL send --cmd 0x3410 --param-hex 00000000 --wait 2
$CTL send --cmd 0x5503 --param-hex 01040000 --wait 2
```

- 默认加密（需已登录）；`--plain` 只在明确知道明文命令时用；
- `cmd_id` 支持 `0x` 前缀或十进制；
- `param_hex` 必须偶数长度十六进制。

## 返回

`data.ack` 是 RX 帧：`id/ts/cmd_id/cmd_name/param_hex/decoded`。
`data.decoded` 可能为 null。

## 注意

- `0x3410` 的 param 必须 4 字节 `00000000`；空 param 模块不回复；
- 不要用 `send` 发 `0x3412/0x3413/0x3415`（升级流程走 `flash-*`；commit 走 `flash-commit`，必须用户明确允许）；
- 写类命令（NV/升级）不用 `send` 绕过门禁；
- 结论带 `ack.id`/`ts`/`param_hex`。
