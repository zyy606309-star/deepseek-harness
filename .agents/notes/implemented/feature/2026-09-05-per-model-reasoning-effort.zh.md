# Agent Note：模型级默认思考强度

Status: implemented

[English](2026-09-05-per-model-reasoning-effort.md) | 中文

## Problem

模型目录条目能定义模型规模（`contextWindow`、`maxTokens`），但不能选择它思考到什么程度。思考强度只能是路由级旋钮：`llm-deepseek` 只有一个 provider 级 `reasoningEffort`，`llm-pi-ai` 只有一个 provider 级 `reasoning`。模型选择器按模型提供强度等级（经 `reasoning.efforts`），并把 `reasoning.defaultEffort` 作为选中默认值，但该默认值总是路由级的，因此同一 provider 下两个应当不同思考强度的模型无法这样配置。想让 `gpt-5.6-luna` 用 `max`、同一路由下另一个模型用 `low` 的部署没有对应设置。

## Decision

向模型目录新增可选的 per-model `reasoningEffort`（取值 `off`/`low`/`high`/`max`），作为该模型的默认思考强度：选中该模型且没有会话级强度覆盖时生效。该值沿用现有 `reasoning.defaultEffort` 接缝，因此模型选择弹窗与请求路径无需新接线即可应用它。

- **`llm-deepseek`**（DeepSeek 官方）：`DeepSeekCatalogModel` 增 `reasoningEffort`；`modelInfoFor` 以它作为该模型的 `defaultEffort`，否则回退路由默认。`thinking: 'disabled'` 部署策略仍强制 `off` —— per-model 非 off 强度不能覆盖禁用策略，因为该策略由适配器持有，host 无法把它与普通默认区分开。
- **`llm-pi-ai`**（声明的 OpenAI 兼容路由）：`PiAiModelProfile` 增 `reasoningEffort`；解析时把它放进 `configuredReasoningEffort` map（与现有 `configuredMaxTokens` 并列），`modelInfo` 以它作为模型默认，否则回退 `profile.reasoning`。只有当模型自己的 `reasoningEfforts` 提供该等级时才成为默认（否则 `describableReasoningLevel` 得到空），因此命中了不支持等级时描述为「无默认」而非隐藏整条路由。

该设置作为每个模型行的 `思考强度` 下拉出现在两个目录编辑器（`DeepSeekModelsEditor` 与 `ModelListEditor`）；留空继承 provider 默认。共享的 `validateDeepSeekModels` 拒绝四个等级之外的值。

## Testing

`packages/llm/llm-deepseek/tests/adapter.spec.ts` 断言：设置了 per-model 强度的模型以它作为默认，而未设置的同路由模型保留路由默认；并在解析边界拒绝非法强度。`packages/llm/llm-pi-ai/tests/adapter.spec.ts` 断言：声明了 per-model 强度的模型以它覆盖路由默认，而未声明的继承路由默认。`packages/client/ui-settings-models/tests/components.client.spec.tsx` 断言集合外取值的校验失败。

TODO(keyless-snapshot, optional)：本次改动没有新增模型可见的请求结构或输入——它只是给既有的、已被测试覆盖的 `reasoning.defaultEffort` 选择接缝提供一个配置来源（`deepseek-defaults` 快照已断言 effort 到达 wire；模型选择路径由 `ui-model-selection` 测试覆盖）。一条覆盖完整链路——目录 per-model 强度 → `session.models` 的 `defaultEffort` → `selectModel` → wire 请求——的装配级 web 快照会是加分项，但需要真实主机的模型选择场景（headless 快照装配只以 `provider`/`model` 创建 agent，无法走选择路径）；上述适配器级单测与既有模型选择 default-effort 测试分别覆盖了两半。

## Alternatives considered

- **在 `buildModelCatalog` 做 host 层注入**（读各 provider 的 settings 段并覆写 `reasoning.defaultEffort`）。否决：它无法区分适配器强制 `off`（部署 `thinking: 'disabled'`）与普通默认，会覆盖禁用策略；并且把 host 与各 provider 的 settings 布局（`models` 数组 vs `providers.<route>` 加 `modelOverrides`）耦合起来。
- **在 `modelInfo` 里直接从原始 profile 读 per-model 默认。** 对 pi-ai 不可行：`ResolvedPiAiProviderProfile` 剔除了 `models`/`modelOverrides`，原始 per-model 字段在此不可达；改为用解析后的 map（采纳的方案），与 `configuredMaxTokens` 一致。

## Consequences

- 部署可为每个模型设置思考强度，并在下次选中该模型时生效，无需重启。
- 模型选择弹窗仍提供适配器拥有的等级；per-model 值仅决定预选哪一个。
- `verify-package-invariants` 不受影响：本次只新增配置解析与模型信息元数据，没有新事件或可变运行时关系。
