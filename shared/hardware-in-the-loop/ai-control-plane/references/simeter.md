# 模拟电表（sim_meter）：645 从站仿真调测（REQS-0035/0036）

> service 固定 `simeter`；AI 平面**只读**（v2 能力 `simeter_frames.read`，scope `simeter:read`）。
> 写操作（open/close/config/handle_hex…）**直连 `/api/simeter/*`**，不经 `/api/ai/v1`、免 token；
> 端点全集与错误语义以自描述小抄 `GET /api/simeter/_meta` 为准（响应内即契约，省 token 防迷路）。

## 最小调用链（只读观察）

```bash
# 1) 自描述小抄：端点清单 + open_sequence + 错误码语义（REQS-0035）
curl http://127.0.0.1:8790/api/simeter/_meta
# 2) 电表脑 + 串口 + 会话状态
curl http://127.0.0.1:8790/api/simeter/status
# 3) 会话帧日志
curl "http://127.0.0.1:8790/api/simeter/frames?limit=50"      # dir=rx|tx|event, after_seq, limit
# 4) v2 门面观察（随 capabilities 的 simeter_frames.read 一起用）
curl -X POST http://127.0.0.1:8790/api/ai/v2/investigations \
  -H "Content-Type: application/json" \
  -d '{"observations":[{"source":"simeter"}],"client_request_id":"<id>"}'
```

## 调测典型序列（_meta.open_sequence）

```bash
curl -X POST http://127.0.0.1:8790/api/simeter/open \
  -H "Content-Type: application/json" -d '{"mapping_id":"listener"}'
# 或显式端口：{"port":"/dev/pts/N","baudrate":2400,"parity":"E"}

# 无串口调测：直接喂 645 请求帧 hex，返回应答帧 hex（不开串口也能验证表逻辑）
curl -X POST http://127.0.0.1:8790/api/simeter/handle_hex \
  -H "Content-Type: application/json" \
  -d '{"hex":"68999999999999681104333334334816"}'
```

## 与模拟集中器对档联调（易踩点）

- **地址**：出厂地址 `000000000001`；对档前先 `POST /config {"addr":"999999999999"}`
  设为 simcon 档案地址，否则读数据得到「非本表地址，不响应」**静默无应答**。
- **645 记法**：地址 12 位 BCD；DI 用显示序（00010000=正向有功总电能）；版本 07/97 可切。
- **波特率**：17H 特征字单字节 +33H 传输；热切换 `POST /baud {"baudrate":9600}`。
- **WSL pts 不接受 PARENB**：经虚拟串口/桥接环境开口一律 `parity="N"`
  （pts 是透明管道，线参由 Windows 侧对端决定）。
- 13H 读地址支持 FE×6 / 99×6 / AA×6 三种广播（对齐 STA 绑表扫掠节奏）。
