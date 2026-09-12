# 任务产物规范

每个逆向任务建议对应一个目录：

`artifacts/tasks/<task-id>/`

## 最小元数据

`task.json` 至少包含：

```json
{
  "task_id": "",
  "title": "",
  "target_type": "web|app|protocol|js|other",
  "target": "",
  "target_version": "",
  "started_at": "",
  "status": "active|blocked|verified|archived",
  "success_criteria": "",
  "evidence_root": ""
}
```

推荐最少包含：

- `task.json`
- `network.jsonl`
- `runtime-evidence.jsonl`
- `scripts.jsonl`
- `report.md`
- `env/entry.js`
- `env/env.js`
- `env/polyfills.js`
- `run/run-local.mjs`
- `run/verify-once.mjs`

作用：

- 交接给下一轮 AI 或人继续做
- 回放页面证据和本地补环境状态
- 固化 patch 历史和当前阻塞点

## 文件约定

- `network.jsonl`：一行一个请求或响应摘要，必须带时间、方法、URL、状态和触发动作。为保证登录态、签名和设备态可复现，原始 Cookie、Authorization、请求体等字段默认保留在受控任务目录；不要把它们重复复制到报告或模型上下文。
- `runtime-evidence.jsonl`：一行一个 Hook、断点或页面状态事件，必须带来源、调用点和摘要。
- `scripts.jsonl`：一行一个脚本/模块线索，必须带 URL 或文件哈希、范围和用途。
- `report.md`：按“事实、推断、假设、验证、未决问题”组织，不能只写成功结论。
- `env/`：只放隔离运行时补丁，不覆盖原始脚本。
- `run/`：入口脚本必须支持重复运行，并返回非零退出码表示验证失败。

## 归档前检查

- 原始文件和派生产物已分离；
- 证据和摘要能互相定位；
- 当前版本和环境已记录；
- 有成功样本、失败样本或明确说明没有；
- 有回滚动作和下一步动作；
- 原始 Cookie、Token、账号和私密请求字段只保留在受控任务目录；报告、摘要和对外交接材料按需引用或单独处理，不要求破坏原始复现证据。
