# SSE 事件（暂空）

当前状态：**暂未接入**。

- 8765 没有 `/api/events` SSE；
- 用 `$CTL events --seconds N` 轮询 `/api/logs`（只报新事件），或 `$CTL logs --since` 查历史；
- 不要假设有 `flash.progress`/`session.state` 推送。

等 Windows 侧提供 SSE 后，在此补充事件表。
