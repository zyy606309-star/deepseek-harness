# JS 逆向标准流程

本仓库默认按以下顺序执行：

1. Observe
2. Capture
3. Rebuild
4. Patch
5. DeepDive

## 1. Observe

目标：

- 确认目标请求
- 确认触发动作
- 缩小脚本范围
- 找到候选函数或调用链

要求：

- 先在真实浏览器取证
- 没有页面证据，不进入本地补环境

## 2. Capture

目标：

- 最小侵入采样目标参数和运行时证据

优先级：

- Hook 优先
- preload 次之
- 断点最后

要求：

- 先看摘要，再看原始数据
- 只抓与当前目标直接相关的证据

## 3. Rebuild

目标：

- 导出本地最小复现材料
- 在 Node 中跑通目标参数链路

要求：

- 不追求完整模拟浏览器
- 先跑通目标函数或目标请求参数

## 4. Patch

目标：

- 根据页面证据和代理日志补环境

要求：

- 先确认 `first divergence`
- 一次只做一个补丁决策
- 一个补丁决策对应一个最小因果单元
- 每次补丁后立即复测

## 5. DeepDive

目标：

- 去混淆
- 提纯算法链路
- 还原长期可复用实现

要求：

- 如果当前任务只要求“出参数”，这一阶段可以降级
- 如果要沉淀长期复用脚本，这一阶段必须做

## 核心原则

- Observe-first
- Hook-preferred
- Breakpoint-last
- Rebuild-oriented
- Evidence-first
