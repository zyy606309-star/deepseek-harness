# 补环境规范

补环境默认遵循：

1. 先看页面证据
2. 再看代理 env log
3. 再确认 `first divergence`
4. 最后做一个补丁决策

## 关键口径

### first divergence

本地运行结果和真实环境第一次出现分歧的位置。

### 最小因果单元

一次补丁只针对一个可解释对象，例如：

- 一个值
- 一个函数壳
- 一个返回对象
- 一个最小对象契约
- 一段原型链关系

## 规则

- 不允许没有页面证据就硬补 `window/document/navigator`
- 不允许一次性整包照搬浏览器环境
- `undefined` 只是信号，不是补丁方案本身
- 每次补丁都要可回滚、可复测、可解释
- 每次补丁后都要记录 `first divergence` 是否前移

## 常见优先项

- `navigator`
- `document`
- `location`
- `crypto`
- `TextEncoder`
- `atob/btoa`
- `localStorage/sessionStorage`
- 原型链和描述符
- `safeFunction`

## 停止条件

- 连续多轮补丁没有推进 `first divergence`
- 当前失败点已经回到浏览器取证更划算
- 目标参数已稳定产出
